"""Score every trade idea the dashboard has ever published, and write site/trades.json for the
Scorecard page.

Stateless by design: each run rebuilds the whole record from (a) every version of
site/notes.json in git history, (b) the price history already in site/data.json, and
(c) pipeline/backfill_legs.json for ideas published before trades carried their own legs.
Nothing is carried over between runs, so there is no ledger to drift or get clobbered by two
runs at once, and the backfill uses the same code path as live ideas.

Rules (also written into trades.json so the page can show them):
  - Entry: the first daily close after the idea was published. A close dated D counts only if
    the idea was published before 19:00 UTC on D (US close is 20:00/21:00 UTC), so a 7:15 AM ET
    idea enters at that day's close and a 6:37 PM ET idea at the next day's.
  - Position return: sum(side * weight * leg return) / max(total long weight, total short weight).
    A 1:1 pair is (long return - short return); a single leg is +/- its return.
  - Exit: target hit, stop hit, or horizon expired, whichever comes first, checked on daily closes.
  - The same legs and direction published again while the idea is still open is a reiteration
    of that idea, not a new one. Ideas dropped from the read still run to their exit.

Never breaks the site: run with continue-on-error in the workflow; on any failure the previous
site/trades.json (if any) is left in place.
"""
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "site" / "data.json"
NOTES_PATH = ROOT / "site" / "notes.json"
OUT_PATH = ROOT / "site" / "trades.json"
BACKFILL_PATH = Path(__file__).resolve().parent / "backfill_legs.json"

CUTOFF_HOUR_UTC = 19
DEFAULT_HORIZON_DAYS = 60
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "quarter": 91}
SKIP_NAMES = {"test"}  # placeholder from the very first commit

RULES = [
    "Each idea is scored with liquid stand-ins (its 'legs'), so an options or futures idea is "
    "scored on the direction of its underlying, not the exact P&L of the structure.",
    "Entry is the first daily close after the idea was published (before 19:00 UTC counts for "
    "that day's close; later ideas enter at the next day's close).",
    "Pair return = long-leg return minus short-leg return, weighted by the legs' stated sizes.",
    "Exit is the first of: target hit, stop hit, or horizon expired, checked on daily closes.",
    "Ideas repeated while still open count once. Ideas dropped from the read still run to their exit.",
    "Ideas published before 2026-11-10 had their stand-ins written afterwards from the prose and "
    "are marked 'reconstructed'. Their target is the % move the prose stated (low end of a range), "
    "their stop is the same size in the other direction, and ideas with no stated % exit at the horizon.",
    "Headline numbers count every idea marked to market (open ones at today's price). Closed-only "
    "numbers are biased early on, because ideas that hit targets close sooner than ones that expire.",
]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_horizon(text):
    """Upper end of a prose horizon like '1-3 months' or '4-10 weeks', in days."""
    best = None
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:[-–]\s*(\d+(?:\.\d+)?))?\s*(day|week|month|quarter)",
                         (text or "").lower()):
        n = float(m.group(2) or m.group(1)) * UNIT_DAYS[m.group(3)]
        best = max(best or 0, n)
    return int(round(best)) if best else None


def note_versions():
    """Every committed version of notes.json, oldest first, plus the working-tree file if it
    differs from HEAD (i.e. it was just regenerated in this run and isn't committed yet)."""
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        print("warning: shallow clone - only part of the trade history is visible "
              "(the workflow should check out with fetch-depth: 0)", file=sys.stderr)
    out = []
    for line in reversed(git("log", "--format=%H %aI", "--", "site/notes.json").split("\n")):
        if not line.strip():
            continue
        sha, ts = line.split()
        try:
            out.append((parse_ts(ts), json.loads(git("show", f"{sha}:site/notes.json")), sha[:7]))
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            continue
    if NOTES_PATH.exists():
        current = NOTES_PATH.read_text()
        try:
            head = git("show", "HEAD:site/notes.json")
        except subprocess.CalledProcessError:
            head = None
        if current != head:
            out.append((datetime.now(timezone.utc), json.loads(current), "working"))
    return out


def price_series(data):
    """id -> (sorted list of date, list of close)."""
    out = {}
    for s in data["series"]:
        if not s.get("t0") or not s.get("dt"):
            continue
        t0 = date.fromisoformat(s["t0"])
        pts = [(t0 + timedelta(days=d), v) for d, v in zip(s["dt"], s["v"]) if v is not None]
        if pts:
            out[s["id"]] = ([p[0] for p in pts], [float(p[1]) for p in pts])
    return out


def close_on_or_before(dates, values, d):
    """Last close dated on or before d, using bisection."""
    lo, hi = 0, len(dates)
    while lo < hi:
        mid = (lo + hi) // 2
        if dates[mid] <= d:
            lo = mid + 1
        else:
            hi = mid
    return values[lo - 1] if lo else None


def first_eligible(dates, published):
    for d in dates:
        if datetime(d.year, d.month, d.day, CUTOFF_HOUR_UTC, tzinfo=timezone.utc) > published:
            return d
    return None


def score_idea(idea, prices, spy):
    """Fill in entry, marking path, exit and benchmark for one idea, in place."""
    legs = idea["legs"]
    if any(leg["id"] not in prices for leg in legs):
        idea["status"] = "no_data"
        return
    firsts = [first_eligible(prices[leg["id"]][0], idea["published_dt"]) for leg in legs]
    if any(f is None for f in firsts):
        idea["status"] = "pending"
        return
    entry = max(firsts)
    entry_px = [close_on_or_before(*prices[leg["id"]], entry) for leg in legs]
    long_w = sum(leg["weight"] for leg in legs if leg["side"] == "long")
    short_w = sum(leg["weight"] for leg in legs if leg["side"] == "short")
    denom = max(long_w, short_w) or 1.0

    timeline = sorted({d for leg in legs for d in prices[leg["id"]][0] if d > entry})
    horizon_end = entry + timedelta(days=idea["horizon_days"])
    status, exit_d, ret, mfe, mae, path = "open", None, 0.0, 0.0, 0.0, [(0, 0.0)]
    for d in timeline:
        r = 0.0
        for leg, px0 in zip(legs, entry_px):
            px = close_on_or_before(*prices[leg["id"]], d)
            sign = 1 if leg["side"] == "long" else -1
            r += sign * leg["weight"] * (px / px0 - 1)
        ret = 100 * r / denom
        mfe, mae = max(mfe, ret), min(mae, ret)
        path.append(((d - entry).days, round(ret, 2)))
        if idea["target_pct"] is not None and ret >= idea["target_pct"]:
            status, exit_d = "target", d
        elif idea["stop_pct"] is not None and ret <= idea["stop_pct"]:
            status, exit_d = "stop", d
        elif d >= horizon_end:
            status, exit_d = "expired", d
        if exit_d:
            break

    last_d = exit_d or (timeline[-1] if timeline else entry)
    spy_ret = None
    if spy:
        s0, s1 = close_on_or_before(*spy, entry), close_on_or_before(*spy, last_d)
        if s0 and s1:
            spy_ret = round(100 * (s1 / s0 - 1), 2)
    step = max(1, len(path) // 40)
    idea.update(
        status=status, entry_date=entry.isoformat(), exit_date=exit_d.isoformat() if exit_d else None,
        exit_dt=exit_d, mark_date=last_d.isoformat(), days_held=(last_d - entry).days,
        ret=round(ret, 2), mfe=round(mfe, 2), mae=round(mae, 2), spy_ret=spy_ret,
        entry_px=[round(p, 4) for p in entry_px],
        path=[p for i, p in enumerate(path) if i % step == 0 or i == len(path) - 1],
        _timeline=[(d, v) for d, v in zip([entry] + timeline[: len(path) - 1], [p[1] for p in path])],
    )


def resolve_legs(t, backfill):
    """Legs and exit levels for a published trade: its own fields if it has legs, else the
    hand-written backfill stand-in. Returns None if the idea can't be scored."""
    if t.get("legs"):
        return dict(legs=t["legs"], horizon_days=t.get("horizon_days") or parse_horizon(t.get("horizon")),
                    stop_pct=t.get("stop_pct"), target_pct=t.get("target_pct"), reconstructed=False)
    b = backfill.get(t.get("name", "").strip().lower())
    if not b or not b.get("legs"):
        return None
    # The old prose gave stops as price levels, not % moves, so there's no numeric stop to
    # recover. A target with no stop would let winners close early while losers sit open to the
    # horizon, which inflates the closed win rate; a symmetric stop removes that bias.
    tgt = b.get("target_pct")
    return dict(legs=b["legs"], horizon_days=b.get("horizon_days") or parse_horizon(t.get("horizon")),
                stop_pct=-tgt if tgt else None, target_pct=tgt, reconstructed=True)


def is_open_at(idea, when):
    if idea["status"] in ("pending", "open"):
        return True
    if idea.get("exit_dt") is None:
        return False
    close_time = datetime(idea["exit_dt"].year, idea["exit_dt"].month, idea["exit_dt"].day,
                          CUTOFF_HOUR_UTC, tzinfo=timezone.utc)
    return when < close_time


def group_stats(ideas):
    closed = [i for i in ideas if i["status"] in ("target", "stop", "expired")]
    marked = [i for i in ideas if i["status"] in ("target", "stop", "expired", "open")]

    def block(xs):
        if not xs:
            return {"n": 0}
        rets = [x["ret"] for x in xs]
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]
        spys = [x["spy_ret"] for x in xs if x.get("spy_ret") is not None]
        return {
            "n": len(xs), "win_rate": round(100 * len(wins) / len(xs), 1),
            "avg_ret": round(sum(rets) / len(rets), 2), "median_ret": round(median(rets), 2),
            "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "avg_spy": round(sum(spys) / len(spys), 2) if spys else None,
            "avg_days": round(sum(x["days_held"] for x in xs) / len(xs), 1),
        }

    return {"closed": block(closed), "all": block(marked),
            "outcomes": {k: sum(1 for i in ideas if i["status"] == k)
                         for k in ("target", "stop", "expired", "open", "pending")}}


def follow_every_idea(ideas, spy):
    """Equal-weight daily average of every idea that is open that day, compounded; S&P alongside."""
    daily = {}
    for idea in ideas:
        tl = idea.get("_timeline") or []
        for (d0, r0), (d1, r1) in zip(tl, tl[1:]):
            daily.setdefault(d1, []).append((1 + r1 / 100) / (1 + r0 / 100) - 1)
    if not daily:
        return []
    days = sorted(daily)
    start = days[0] - timedelta(days=1)
    s0 = close_on_or_before(*spy, start) if spy else None
    level, curve = 100.0, [[start.isoformat(), 100.0, 100.0 if s0 else None]]
    for d in days:
        level *= 1 + sum(daily[d]) / len(daily[d])
        s = close_on_or_before(*spy, d) if spy else None
        curve.append([d.isoformat(), round(level, 2), round(100 * s / s0, 2) if s0 and s else None])
    return curve


def main():
    data = json.loads(DATA_PATH.read_text())
    prices = price_series(data)
    spy = prices.get("SPY")
    backfill = json.loads(BACKFILL_PATH.read_text())["trades"] if BACKFILL_PATH.exists() else {}

    ideas, unscored = [], {}
    for published, notes, sha in note_versions():
        for t in notes.get("trades", []):
            name = (t.get("name") or "").strip()
            if not name or name.lower() in SKIP_NAMES:
                continue
            spec = resolve_legs(t, backfill)
            if spec is None:
                unscored.setdefault(name.lower(), {"name": name, "first_seen": published.isoformat()})
                continue
            sig = tuple(sorted((leg["id"], leg["side"]) for leg in spec["legs"]))
            same = next((i for i in reversed(ideas) if i["sig"] == sig and is_open_at(i, published)), None)
            if same:
                same["times_published"] += 1
                same["last_seen"] = published.isoformat()
                continue
            idea = dict(
                sig=sig, name=name, dir=t.get("dir"), conviction=t.get("conviction"),
                line=t.get("line") or "", expr=t.get("expr") or "", thesis=t.get("thesis") or "",
                ids=t.get("ids") or [], published=published.isoformat(), published_dt=published,
                last_seen=published.isoformat(), times_published=1, version=sha,
                legs=spec["legs"], horizon_days=spec["horizon_days"] or DEFAULT_HORIZON_DAYS,
                stop_pct=spec["stop_pct"], target_pct=spec["target_pct"],
                reconstructed=spec["reconstructed"],
            )
            score_idea(idea, prices, spy)
            ideas.append(idea)

    scored = [i for i in ideas if i["status"] != "no_data"]
    by = {
        "conviction": {str(c): group_stats([i for i in scored if i["conviction"] == c]) for c in (1, 2, 3)},
        "dir": {d: group_stats([i for i in scored if i["dir"] == d]) for d in ("LONG", "SHORT", "PAIR")},
        "source": {"live": group_stats([i for i in scored if not i["reconstructed"]]),
                   "reconstructed": group_stats([i for i in scored if i["reconstructed"]])},
    }
    curve = follow_every_idea([i for i in scored if i["status"] != "pending"], spy)
    for i in ideas:
        for k in ("sig", "published_dt", "exit_dt", "_timeline"):
            i.pop(k, None)
    ideas.sort(key=lambda i: i["published"], reverse=True)

    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_generated": data.get("generated"),
        "rules": RULES,
        "summary": group_stats(scored),
        "by": by,
        "curve": curve,
        "ideas": ideas,
        "unscored": sorted(unscored.values(), key=lambda u: u["first_seen"], reverse=True),
        "no_data": sum(1 for i in ideas if i["status"] == "no_data"),
    }
    OUT_PATH.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    s = out["summary"]
    print(f"Wrote {OUT_PATH}: {len(scored)} ideas scored "
          f"({s['outcomes']}), {len(out['unscored'])} unscoreable, {out['no_data']} missing price data; "
          f"closed win rate {s['closed'].get('win_rate')}% over n={s['closed']['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
