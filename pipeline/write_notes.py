"""Regenerate site/notes.json (the headline, summary, good/bad and trade ideas) from the
freshly-computed site/data.json, using Claude with web search for current-events grounding.

Runs after pipeline/fetch.py, only on the scheduled/dispatched refresh (see
.github/workflows/update.yml) so a plain code push redeploys instantly without an API call or
the risk of clobbering a hand-edited notes.json seconds after it's pushed.

Never breaks the site: any failure (missing key, API error, bad JSON, failed validation) leaves
the existing site/notes.json untouched and exits with a clear message. A missing ANTHROPIC_API_KEY
is treated as "not configured" (exit 0, one informative line) rather than a failure.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "site" / "data.json"
NOTES_PATH = ROOT / "site" / "notes.json"
MODEL = "claude-opus-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sharp sentence: the day's dominant tension for markets."},
        "summary": {
            "type": "array",
            "items": {"type": "string"},
            "description": "EXACTLY 2 to 4 dense paragraphs. Specific numbers from the data provided, no filler.",
        },
        "good": {
            "type": "array",
            "description": "EXACTLY 3 to 6 items.",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "ids"], "additionalProperties": False,
            },
        },
        "bad": {
            "type": "array",
            "description": "EXACTLY 3 to 6 items.",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "ids"], "additionalProperties": False,
            },
        },
        "trades": {
            "type": "array",
            "description": "EXACTLY 4 to 7 items.",
            "items": {
                "type": "object",
                "properties": {
                    "dir": {"type": "string", "enum": ["LONG", "SHORT", "PAIR"]},
                    "name": {"type": "string"},
                    "line": {"type": "string", "description": "<=70 chars, for the one-line trade list at the top."},
                    "conviction": {"type": "integer", "enum": [1, 2, 3]},
                    "expr": {"type": "string", "description": "How to actually put the trade on."},
                    "thesis": {"type": "string"},
                    "trigger": {"type": "string", "description": "Why now, in the data."},
                    "stop": {"type": "string", "description": "What would prove this wrong."},
                    "target": {"type": "string"},
                    "horizon": {"type": "string"},
                    "ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dir", "name", "line", "conviction", "expr", "thesis",
                             "trigger", "stop", "target", "horizon", "ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "summary", "good", "bad", "trades"],
    "additionalProperties": False,
}

SYSTEM = """You are the macro strategist writing the top of "Macro Tape", a daily dashboard for an \
investment team, built in the style of Stan Druckenmiller's daily scan of ~200 charts.

You are given a digest of ~220 live series (prices, rates, spreads, currencies, commodities, \
sector/industry/country relative strength vs the S&P, and bellwether stocks), each with its \
change over several windows, a 1-month z-score, a trend state, an acceleration z-score, and a \
polarity (+1 = rising is good for risk assets, -1 = rising is bad for risk assets, 0 = neutral/ \
context-dependent, e.g. oil or gold). You may also use web search, sparingly, to ground the \
write-up in today's actual headlines (Fed decisions, data releases, geopolitics) - the data \
digest is the primary source; search only to confirm or add the 1-2 events that explain today's \
biggest moves. Never invent a number - every figure in your prose must come from the digest.

Write like a sharp CIO memo, not a research report: short declarative sentences, concrete \
numbers, no hedging, no "markets were mixed" filler. Explicitly separate what's good for risk \
assets from what's bad - remember polarity, so a rising number is not automatically "good" (e.g. \
rising yields, oil or credit spreads are bad; rising copper or breadth is good). Call out where \
something accelerating is actually bad (a faster sell-off, a faster tightening), not just where \
acceleration is bullish. If a previous day's read is provided, don't just restate it - say what \
changed and why, and don't recycle the same headline.

For trades: pick 4-7 SPECIFIC, monetizable ideas that follow directly from what's moving today \
(long, short, or pair trades). Prefer expressing a theme through a real, liquid instrument \
(an ETF, a future, an index option, a specific stock) over a vague "buy the sector" idea. Cover \
different themes - don't make all of them rates trades. Every "ids" array must contain ONLY ids \
that appear in the digest below (they become clickable chart links - a made-up id breaks the \
link), and every trade needs a concrete trigger (why now, citing the data), a stop (what proves \
it wrong) and a target.

Output must be valid JSON matching the provided schema. Nothing outside the JSON."""


def clean(x):
    return None if x is None else x


def fmt_chg(kind, unit, v):
    if v is None:
        return "-"
    if kind == "lvl" and unit == "%":
        return f"{v * 100:+.0f}bp"
    if kind == "lvl":
        return f"{v:+.2f}"
    return f"{v:+.1f}%"


def build_digest(data):
    groups = {g["key"]: g["label"] for g in data["groups"]}
    lines = [f"Risk regime: {data['regime']} (-100 risk-off to +100 risk-on)", "Composites:"]
    for c in data["composites"]:
        lines.append(f"  {c['label']}: {c['value']}")
    lines.append("")
    lines.append("Series (id | name | group | polarity | last | date | 1d/1w/1m/3m/ytd/1y chg | "
                 "1m-move z-score | trend state | acceleration z-score | vs 200d | 52wk pctile"
                 " | rel.strength vs S&P: 1m/3m/state):")
    by_group = {}
    for s in data["series"]:
        by_group.setdefault(s["group"], []).append(s)
    for gkey, glabel in groups.items():
        items = by_group.get(gkey, [])
        if not items:
            continue
        lines.append(f"-- {glabel} --")
        for s in items:
            c = s["chg"]
            rs = s.get("rs")
            rs_str = f"{rs['chg1m']:+.1f}%/{rs['chg3m']:+.1f}%/{rs['state']}" if rs else "-"
            lines.append(
                f"{s['id']} | {s['name']} | {gkey} | pol={s['pol']} | {s['last']} | {s['date']} | "
                f"{fmt_chg(s['kind'], s['unit'], c['d1'])}/{fmt_chg(s['kind'], s['unit'], c['w1'])}/"
                f"{fmt_chg(s['kind'], s['unit'], c['m1'])}/{fmt_chg(s['kind'], s['unit'], c['m3'])}/"
                f"{fmt_chg(s['kind'], s['unit'], c['ytd'])}/{fmt_chg(s['kind'], s['unit'], c['y1'])} | "
                f"z={s['z1m']} | {s['state']} | acc_z={s['accelZ']} | ext={s['ext']}% | "
                f"pos52={s['pos52']} | rs={rs_str}"
            )
    if data.get("missing"):
        lines.append("")
        lines.append(f"(Unavailable today, don't reference: {', '.join(data['missing'])})")
    return "\n".join(lines)


def validate(notes, valid_ids):
    """Coerce the model's output into something safe to publish: drop unknown chart ids rather
    than fail the whole run over one bad reference."""
    def keep_ids(ids):
        return [i for i in (ids or []) if i in valid_ids]

    assert isinstance(notes.get("headline"), str) and notes["headline"].strip()
    assert isinstance(notes.get("summary"), list) and 2 <= len(notes["summary"]) <= 6
    for para in notes["summary"]:
        assert isinstance(para, str) and para.strip()

    for key in ("good", "bad"):
        items = notes.get(key)
        assert isinstance(items, list) and len(items) >= 2
        for it in items:
            assert isinstance(it.get("text"), str) and it["text"].strip()
            it["ids"] = keep_ids(it.get("ids"))

    trades = notes.get("trades")
    assert isinstance(trades, list) and len(trades) >= 3
    for t in trades:
        assert t.get("dir") in ("LONG", "SHORT", "PAIR")
        assert isinstance(t.get("conviction"), int) and 1 <= t["conviction"] <= 3
        for k in ("name", "line", "expr", "thesis", "trigger", "stop", "target", "horizon"):
            assert isinstance(t.get(k), str) and t[k].strip()
        t["ids"] = keep_ids(t.get("ids"))
    return notes


def main():
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("ANTHROPIC_API_KEY not set; skipping notes regeneration (keeping existing notes.json).")
        return 0

    if not DATA_PATH.exists():
        print("site/data.json not found; skipping notes regeneration.", file=sys.stderr)
        return 0

    data = json.loads(DATA_PATH.read_text())
    valid_ids = {s["id"] for s in data["series"]}
    digest = build_digest(data)

    prev_context = ""
    if NOTES_PATH.exists():
        try:
            prev = json.loads(NOTES_PATH.read_text())
            prev_context = (
                f"\n\nYesterday's read (as of {prev.get('asof', '?')}), for continuity - don't "
                f"just repeat it, say what's changed:\nHeadline: {prev.get('headline', '')}\n"
                f"Summary: {' '.join(prev.get('summary', []))}"
            )
        except Exception:  # noqa: BLE001
            pass

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    user_content = (
        f"Today's data digest, generated {data['generated']}:\n\n{digest}{prev_context}\n\n"
        "Write today's read and trade ideas as JSON matching the schema."
    )

    try:
        response = client.with_options(timeout=480.0).messages.create(
            model=MODEL,
            # Adaptive thinking + web search both spend from this same budget before the final
            # JSON text is written, so 8000 was too tight - it truncated the response mid-string
            # more often than not (silent under continue-on-error until someone checked the logs).
            max_tokens=20000,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 4}],
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as e:
        print(f"Claude API call failed: {e}", file=sys.stderr)
        return 1

    if response.stop_reason == "refusal":
        print(f"Claude declined the request: {response.stop_details}", file=sys.stderr)
        return 1
    if response.stop_reason == "max_tokens":
        print(f"Hit max_tokens ({response.usage.output_tokens} output tokens) before finishing - "
              "the response was truncated. Raise max_tokens further.", file=sys.stderr)
        return 1

    text_blocks = [b.text for b in response.content if b.type == "text"]
    if not text_blocks:
        print("No text block in the response.", file=sys.stderr)
        return 1

    try:
        notes = json.loads(text_blocks[-1])
        notes = validate(notes, valid_ids)
    except Exception as e:  # noqa: BLE001
        print(f"Response failed validation, keeping existing notes.json: {e}", file=sys.stderr)
        print(text_blocks[-1][:2000], file=sys.stderr)
        return 1

    notes["asof"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    NOTES_PATH.write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {NOTES_PATH}: \"{notes['headline']}\" "
          f"({len(notes['summary'])} paragraphs, {len(notes['trades'])} trades)")
    print(f"Usage: {response.usage.input_tokens} in / {response.usage.output_tokens} out "
          f"(cache read {response.usage.cache_read_input_tokens})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
