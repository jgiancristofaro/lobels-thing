"""Download every series in the universe, compute signals, and write site/data.json.

Runs daily in GitHub Actions (see .github/workflows/update.yml). Needs open
internet access to Yahoo Finance and FRED; no API keys.
"""
import io
import json
import os
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from universe import GROUPS, U  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "data.json"
HISTORY_YEARS = 6
CHART_DAYS = 800  # ~2.2 years of history shipped to the page

# Series quoted in percent (rates, spreads): changes are shown in basis points.
PCT_LEVEL = {"DFF", "SOFR", "DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30", "T10Y2Y", "T10Y3M", "DFII10",
             "T5YIE", "T10YIE", "MORTGAGE30US", "HYOAS", "IGOAS", "CCCOAS", "BBBOAS", "UNRATE", "TCU"}
# Index-point series where absolute (not %) change is meaningful.
IDX_LEVEL = {"NFCI", "STLFSI4"}
# Price indexes shown as year-over-year % instead of level.
YOY = {"CPI", "CORECPI", "COREPCE", "M2SL", "RETAIL", "INDPRO", "PAYEMS"}
EQUITY_GROUPS = {"sectors", "industries", "global", "stocks", "crypto"}

UA = {"User-Agent": "Mozilla/5.0 (compatible; macro-dashboard/1.0)"}


# ------------------------------------------------------------------ fetching
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
_fred_csv_failures = 0


def fetch_fred(code):
    """FRED via the official API when FRED_API_KEY is set, else the public CSV endpoint.

    The public CSV endpoint often stalls for cloud IPs (GitHub runners included), so after a
    few consecutive failures it is skipped and the keyless fallbacks below fill the gaps.
    """
    global _fred_csv_failures
    start = (pd.Timestamp.now() - pd.DateOffset(years=HISTORY_YEARS + 1)).strftime("%Y-%m-%d")
    if FRED_KEY:
        for attempt in range(3):
            try:
                r = requests.get("https://api.stlouisfed.org/fred/series/observations", timeout=30, params=dict(
                    series_id=code, api_key=FRED_KEY, file_type="json", observation_start=start))
                r.raise_for_status()
                obs = r.json()["observations"]
                s = pd.Series({pd.Timestamp(o["date"]): pd.to_numeric(o["value"], errors="coerce") for o in obs})
                return s.dropna()
            except Exception as e:  # noqa: BLE001
                print(f"  FRED API {code} attempt {attempt + 1} failed: {e}")
                time.sleep(1 + attempt)
        return None
    if _fred_csv_failures >= 4:
        return None
    try:
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd={start}", headers=UA, timeout=12)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["date", "v"]
        df["date"] = pd.to_datetime(df["date"])
        df["v"] = pd.to_numeric(df["v"], errors="coerce")
        _fred_csv_failures = 0
        return df.dropna().set_index("date")["v"]
    except Exception as e:  # noqa: BLE001
        _fred_csv_failures += 1
        print(f"  FRED csv {code} failed: {e}")
        return None


# ---------------------------------------------------------- keyless fallbacks
def fetch_treasury_curves():
    """Daily nominal and real (TIPS) par yield curves from the US Treasury."""
    nominal, real = [], []
    for year in range(pd.Timestamp.now().year - HISTORY_YEARS, pd.Timestamp.now().year + 1):
        for kind, out in (("daily_treasury_yield_curve", nominal), ("daily_treasury_real_yield_curve", real)):
            url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                   f"daily-treasury-rates.csv/{year}/all?type={kind}&field_tdr_date_value={year}&page&_format=csv")
            try:
                r = requests.get(url, headers=UA, timeout=40)
                r.raise_for_status()
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = [c.strip().lower().replace(" ", "") for c in df.columns]
                df["date"] = pd.to_datetime(df["date"])
                out.append(df.set_index("date"))
            except Exception as e:  # noqa: BLE001
                print(f"  Treasury {kind} {year} failed: {e}")
    res = {}
    if nominal:
        n = pd.concat(nominal).sort_index()
        n = n[~n.index.duplicated(keep="last")]
        col = lambda c: pd.to_numeric(n[c], errors="coerce").dropna() if c in n else None  # noqa: E731
        for sid, c in (("DGS3MO", "3mo"), ("DGS2", "2yr"), ("DGS5", "5yr"), ("DGS10", "10yr"), ("DGS30", "30yr")):
            if col(c) is not None:
                res[sid] = col(c)
        if "DGS10" in res and "DGS2" in res:
            res["T10Y2Y"] = (res["DGS10"] - res["DGS2"]).dropna()
        if "DGS10" in res and "DGS3MO" in res:
            res["T10Y3M"] = (res["DGS10"] - res["DGS3MO"]).dropna()
    if real:
        rl = pd.concat(real).sort_index()
        rl = rl[~rl.index.duplicated(keep="last")]
        if "10yr" in rl:
            res["DFII10"] = pd.to_numeric(rl["10yr"], errors="coerce").dropna()
        if "5yr" in rl and "DGS5" in res:
            res["T5YIE"] = (res["DGS5"] - pd.to_numeric(rl["5yr"], errors="coerce")).dropna()
        if "DFII10" in res and "DGS10" in res:
            res["T10YIE"] = (res["DGS10"] - res["DFII10"]).dropna()
    return res


def fetch_tga():
    """Treasury General Account closing balance ($mn) from the Daily Treasury Statement."""
    url = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
    start = (pd.Timestamp.now() - pd.DateOffset(years=HISTORY_YEARS)).strftime("%Y-%m-%d")
    rows, page = [], 1
    while page < 20:
        r = requests.get(url, timeout=40, params={
            "filter": f"record_date:gte:{start}",
            "fields": "record_date,account_type,open_today_bal,close_today_bal",
            "page[size]": 10000, "page[number]": page, "sort": "record_date"})
        r.raise_for_status()
        j = r.json()
        rows += j["data"]
        if page >= j.get("meta", {}).get("total-pages", 1):
            break
        page += 1
    df = pd.DataFrame(rows)
    df = df[df["account_type"].str.contains("Treasury General Account", case=False, na=False) &
            df["account_type"].str.contains("Closing", case=False, na=False)]
    val = pd.to_numeric(df["open_today_bal"], errors="coerce")
    if val.isna().all():
        val = pd.to_numeric(df["close_today_bal"], errors="coerce")
    return pd.Series(val.values, index=pd.to_datetime(df["record_date"])).dropna()


def fetch_rrp():
    """Overnight reverse repo accepted ($bn) from the NY Fed."""
    start = (pd.Timestamp.now() - pd.DateOffset(years=HISTORY_YEARS)).strftime("%Y-%m-%d")
    end = pd.Timestamp.now().strftime("%Y-%m-%d")
    r = requests.get("https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json",
                     params={"startDate": start, "endDate": end}, headers=UA, timeout=40)
    r.raise_for_status()
    ops = r.json()["repo"]["operations"]
    s = pd.Series({pd.Timestamp(o["operationDate"]): o.get("totalAmtAccepted", 0) / 1e9 for o in ops})
    return s.groupby(level=0).sum().sort_index()


def fetch_mortgage():
    """Freddie Mac 30-year fixed mortgage rate (weekly)."""
    r = requests.get("https://www.freddiemac.com/pmms/docs/PMMS_history.csv", headers=UA, timeout=40)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip().lower() for c in df.columns]
    s = pd.Series(pd.to_numeric(df["pmms30"], errors="coerce").values, index=pd.to_datetime(df["date"], format="mixed"))
    return s.dropna().sort_index()


BLS = {"CPI": "CUSR0000SA0", "CORECPI": "CUSR0000SA0L1E", "UNRATE": "LNS14000000", "PAYEMS": "CES0000000001"}


def fetch_bls(ids):
    """Monthly BLS series via the keyless v1 API (10-year window)."""
    now = pd.Timestamp.now().year
    r = requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/", timeout=40,
                      json={"seriesid": [BLS[i] for i in ids], "startyear": str(now - HISTORY_YEARS), "endyear": str(now)})
    r.raise_for_status()
    out = {}
    code_to_id = {v: k for k, v in BLS.items()}
    for ser in r.json().get("Results", {}).get("series", []):
        pts = {pd.Timestamp(int(d["year"]), int(d["period"][1:]), 1): float(d["value"])
               for d in ser["data"] if d["period"].startswith("M") and d["period"] != "M13" and d["value"] not in ("-", "")}
        if pts:
            out[code_to_id[ser["seriesID"]]] = pd.Series(pts).sort_index()
    return out


def fetch_yahoo(tickers):
    import yfinance as yf

    out = {}
    for i in range(0, len(tickers), 40):
        chunk = tickers[i:i + 40]
        try:
            df = yf.download(chunk, period=f"{HISTORY_YEARS}y", interval="1d", auto_adjust=True,
                             progress=False, group_by="ticker", threads=True)
        except Exception as e:  # noqa: BLE001
            print(f"  yfinance chunk failed: {e}")
            continue
        for t in chunk:
            try:
                s = df[t]["Close"].dropna() if len(chunk) > 1 else df["Close"].dropna()
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                if len(s):
                    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                    out[t] = s
            except Exception:  # noqa: BLE001
                pass
    missing = [t for t in tickers if t not in out]
    for t in missing:  # direct chart-API fallback
        try:
            r = requests.get(f"https://query2.finance.yahoo.com/v8/finance/chart/{t}",
                             params={"range": f"{HISTORY_YEARS}y", "interval": "1d"}, headers=UA, timeout=30)
            res = r.json()["chart"]["result"][0]
            idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
            s = pd.Series(res["indicators"]["adjclose"][0]["adjclose"] if "adjclose" in res["indicators"]
                          else res["indicators"]["quote"][0]["close"], index=idx, dtype=float).dropna()
            if len(s):
                out[t] = s[~s.index.duplicated(keep="last")]
        except Exception as e:  # noqa: BLE001
            print(f"  Yahoo fallback {t} failed: {e}")
    return out


# ------------------------------------------------------------------ analytics
def val_at(s, when):
    """Last value on or before `when`."""
    sub = s[s.index <= when]
    return float(sub.iloc[-1]) if len(sub) else float("nan")


def change(s, days, kind):
    last_date = s.index[-1]
    a, b = float(s.iloc[-1]), val_at(s, last_date - timedelta(days=days))
    if not np.isfinite(b):
        return None
    if kind == "pct":
        return None if b == 0 else (a / b - 1) * 100
    return a - b


def ytd_change(s, kind):
    last_date = s.index[-1]
    b = val_at(s, pd.Timestamp(last_date.year - 1, 12, 31))
    a = float(s.iloc[-1])
    if not np.isfinite(b):
        return None
    return (a / b - 1) * 100 if kind == "pct" else a - b


def rolling_change(s, days, kind):
    """Series of trailing `days` changes, sampled on s's own index."""
    shifted = s.copy()
    shifted.index = shifted.index + timedelta(days=days)
    prev = shifted.reindex(s.index, method="ffill")
    return (s / prev - 1) * 100 if kind == "pct" else s - prev


def zscore_last(x):
    x = x.replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < 30:
        return None
    sd = x.std()
    return None if not sd else float((x.iloc[-1] - x.mean()) / sd)


def trend(s):
    ma200 = s.rolling("290D", min_periods=5).mean()
    ma50 = s.rolling("72D", min_periods=3).mean()
    last, m200 = float(s.iloc[-1]), float(ma200.iloc[-1])
    m200_prev = val_at(ma200, s.index[-1] - timedelta(days=30))
    rising = np.isfinite(m200_prev) and m200 > m200_prev
    above = last > m200
    recent = s[s.index >= s.index[-1] - timedelta(days=30)]
    rma = ma200.reindex(recent.index)
    crossed = bool(((recent > rma) != above).any())
    if above and rising and not crossed:
        state = "up"
    elif above:
        state = "turning_up"
    elif not above and not rising and not crossed:
        state = "down"
    else:
        state = "rolling_over"
    ext = (last / m200 - 1) * 100 if m200 else None
    return state, ext, float(ma50.iloc[-1]), m200


STATE_SCORE = {"up": 1.0, "turning_up": 0.5, "rolling_over": -0.5, "down": -1.0}


def clean(x, nd=4):
    if x is None:
        return None
    try:
        if not math.isfinite(x):
            return None
    except TypeError:
        return x
    return round(float(x), nd)


def sig(x, n=5):
    if x is None or not math.isfinite(x) or x == 0:
        return 0 if x == 0 else None
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))


def analyze(item, s, spy):
    sid = item["id"]
    kind = "lvl" if (sid in PCT_LEVEL or sid in IDX_LEVEL or sid in YOY or item["src"] == "spread") else "pct"
    unit = "%" if (sid in PCT_LEVEL or sid in YOY) else ""
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if sid in YOY:
        s = rolling_change(s, 365, "pct").dropna()
        unit = "%"
    if len(s) < 10:
        return None

    r1m = rolling_change(s, 30, kind)
    z1m = zscore_last(r1m)
    # acceleration: this month's move minus last month's move
    prev_r1m = r1m.copy()
    prev_r1m.index = prev_r1m.index + timedelta(days=30)
    accel_series = r1m - prev_r1m.reindex(r1m.index, method="ffill")
    accel = accel_series.iloc[-1] if len(accel_series.dropna()) else None
    accel_z = zscore_last(accel_series)

    state, ext, ma50, ma200 = trend(s)
    ext_series = (s / s.rolling("290D", min_periods=5).mean() - 1) * 100
    ext_z = zscore_last(ext_series) if kind == "pct" else None

    yr = s[s.index >= s.index[-1] - timedelta(days=365)]
    hi, lo = float(yr.max()), float(yr.min())
    pos52 = (float(s.iloc[-1]) - lo) / (hi - lo) if hi > lo else 0.5

    rs = None
    if item["group"] in EQUITY_GROUPS and spy is not None and sid != "SPY":
        rel = (s / spy.reindex(s.index, method="ffill")).dropna()
        if len(rel) > 60:
            rstate, _, _, _ = trend(rel)
            rs = dict(chg1m=clean(change(rel, 30, "pct"), 2), chg3m=clean(change(rel, 91, "pct"), 2),
                      chg6m=clean(change(rel, 182, "pct"), 2), state=rstate)

    freq_days = float(np.median(np.diff(s.index.values).astype("timedelta64[D]").astype(float))) if len(s) > 2 else 1
    pol = item["pol"]
    score = None
    if pol and z1m is not None:
        score = pol * (0.5 * max(-3, min(3, z1m)) / 1.5 + 0.5 * STATE_SCORE[state])

    chart = s[s.index >= s.index[-1] - timedelta(days=CHART_DAYS)]
    return dict(
        id=sid, name=item["name"], group=item["group"], pol=pol, why=item["why"], sym=item["sym"],
        kind=kind, unit=unit, freq=freq_days,
        last=sig(float(s.iloc[-1])), date=s.index[-1].strftime("%Y-%m-%d"),
        chg={k: clean(v, 3) for k, v in dict(
            d1=None if freq_days > 1.5 else (change(s, 1, kind) if len(s) < 2 else
                                            ((s.iloc[-1] / s.iloc[-2] - 1) * 100 if kind == "pct" else s.iloc[-1] - s.iloc[-2])),
            w1=change(s, 7, kind), m1=change(s, 30, kind), m3=change(s, 91, kind), m6=change(s, 182, kind),
            ytd=ytd_change(s, kind), y1=change(s, 365, kind)).items()},
        z1m=clean(z1m, 2), accel=clean(accel, 3), accelZ=clean(accel_z, 2),
        state=state, ext=clean(ext, 2), extZ=clean(ext_z, 2), ma50=sig(ma50), ma200=sig(ma200),
        pos52=clean(pos52, 3), hi52=sig(hi), lo52=sig(lo), rs=rs, score=clean(score, 3),
        # chart points: t0 + day offsets keeps the payload small for phones
        t0=chart.index[0].strftime("%Y-%m-%d"),
        dt=[int((d - chart.index[0]).days) for d in chart.index], v=[sig(float(x), 4) for x in chart.values],
    )


# Composites are all scored in "good for risk assets" direction (+100 best, -100 worst).
COMPOSITES = [
    ("liquidity", "Liquidity", ["NETLIQ", "WRESBAL", "NFCI", "M2SL", "RRPONTSYD", "WTREGEN"]),
    ("rates", "Rates", ["DGS10", "DGS2", "DFII10", "MOVE"]),
    ("dollar", "Dollar", ["DXY", "CEW", "AUDJPY"]),
    ("credit", "Credit & vol", ["HYOAS", "CCCOAS", "HYG_IEF", "VIXTS", "VIX"]),
    ("growth", "Growth pulse", ["CU_AU", "XLI_XLU", "DJT", "ICSA", "IWM_SPY", "COPPER"]),
    ("breadth", "Breadth & appetite", ["RSP_SPY", "SPHB_SPLV", "XLY_XLP", "KRE_SPY", "ARKK"]),
    ("inflation", "Inflation", ["WTI", "T5YIE", "GASOLINE", "DBC"]),
]
# Members whose own polarity is neutral but that count against risk inside a composite.
COMPOSITE_POL = {"WTI": -1, "DBC": -1}


def composite(series_by_id, ids):
    vals = []
    for i in ids:
        x = series_by_id.get(i)
        if not x or x["z1m"] is None:
            continue
        pol = COMPOSITE_POL.get(i, x["pol"])
        if not pol:
            continue
        vals.append(pol * (0.5 * max(-3, min(3, x["z1m"])) / 1.5 + 0.5 * STATE_SCORE[x["state"]]))
    return round(100 * sum(vals) / len(vals)) if vals else None


def main():
    by_id = {u["id"]: u for u in U}
    raw = {}

    print("FRED ...")
    from concurrent.futures import ThreadPoolExecutor
    fred_items = [u for u in U if u["src"] == "fred"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda u: fetch_fred(u["sym"]), fred_items))
    for u, s in zip(fred_items, results):
        if s is not None and len(s):
            raw[u["id"]] = s
        else:
            print(f"  missing FRED {u['id']}")

    missing_fred = [u["id"] for u in fred_items if u["id"] not in raw]
    if missing_fred:
        print(f"FRED unavailable for {len(missing_fred)} series; trying official keyless sources ...")
        try:
            for k, v in fetch_treasury_curves().items():
                if k in missing_fred and len(v):
                    raw[k] = v
        except Exception as e:  # noqa: BLE001
            print(f"  Treasury curves failed: {e}")
        for sid, fn in (("WTREGEN", fetch_tga), ("RRPONTSYD", fetch_rrp), ("MORTGAGE30US", fetch_mortgage)):
            if sid in missing_fred:
                try:
                    raw[sid] = fn()
                except Exception as e:  # noqa: BLE001
                    print(f"  {sid} fallback failed: {e}")
        want = [i for i in BLS if i in missing_fred]
        if want:
            try:
                raw.update(fetch_bls(want))
            except Exception as e:  # noqa: BLE001
                print(f"  BLS failed: {e}")
        print(f"  still missing: {[i for i in missing_fred if i not in raw]}")

    print("Yahoo ...")
    yf_items = [u for u in U if u["src"] == "yf"]
    got = fetch_yahoo(sorted({u["sym"] for u in yf_items}))
    for u in yf_items:
        if u["sym"] in got:
            raw[u["id"]] = got[u["sym"]]
        else:
            print(f"  missing Yahoo {u['id']} ({u['sym']})")

    # Net liquidity = Fed balance sheet - TGA - reverse repo (all $bn; WALCL/WTREGEN are $mn)
    if all(k in raw for k in ("WALCL", "WTREGEN", "RRPONTSYD")):
        idx = raw["WALCL"].index
        bs = raw["WALCL"] / 1000
        tga = raw["WTREGEN"].reindex(idx, method="ffill") / 1000
        rrp = raw["RRPONTSYD"].reindex(idx, method="ffill")
        raw["NETLIQ"] = (bs - tga - rrp).dropna()

    for u in U:
        if u["src"] in ("ratio", "spread"):
            a, b = u["sym"].split("/")
            if a in raw and b in raw:
                A, B = raw[a], raw[b]
                idx = A.index.intersection(B.index)
                raw[u["id"]] = (A[idx] / B[idx]) if u["src"] == "ratio" else (A[idx] - B[idx])

    spy = raw.get("SPY")
    series = []
    for u in U:
        if u["id"] not in raw:
            continue
        try:
            r = analyze(u, raw[u["id"]], spy)
            if r:
                series.append(r)
        except Exception as e:  # noqa: BLE001
            print(f"  analyze {u['id']} failed: {e}")

    sb = {x["id"]: x for x in series}
    comps = [dict(key=k, label=l, value=composite(sb, ids), members=ids) for k, l, ids in COMPOSITES]
    vals = [c["value"] for c in comps if c["value"] is not None]
    regime = round(sum(vals) / len(vals)) if vals else None

    data = dict(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        groups=[dict(key=k, label=l) for k, l in GROUPS],
        composites=comps, regime=regime, series=series,
        missing=[u["id"] for u in U if u["id"] not in sb],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False))
    print(f"wrote {OUT} with {len(series)} series ({OUT.stat().st_size / 1e6:.2f} MB); missing: {data['missing']}")


if __name__ == "__main__":
    main()
