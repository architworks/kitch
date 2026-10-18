#!/usr/bin/env python3
"""Aggregate Kitch's usage metrics into small JSON files for the usage dashboard.

Run from the backend environment, which holds the database credentials:

    cd backend && uv run python ../scripts/usage_report.py

It reads usage_events (pseudonymous, content-free rows) and sign-up dates, and
writes only aggregates to reports/usage/: totals, rates and distributions.
No account, household or per-person row ever leaves the database.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.supabase_client import supabase  # noqa: E402

OUT = ROOT / "reports" / "usage"
WINDOW_DAYS = 30
# Estimated Gemini price for the configured model (Gemini 3.5 Flash-Lite, list
# price per 1M tokens, USD), shown in rupees at INR_PER_USD. Thinking tokens
# bill as output. Update when the model, price or exchange rate changes.
PRICE_MODEL = "Gemini 3.5 Flash-Lite"
PRICE_INPUT_PER_M = 0.30
PRICE_OUTPUT_PER_M = 2.50
INR_PER_USD = 96.5
OUTCOMES = ("ok", "limit", "quota", "rejected", "error")
FEATURES = ("chat", "meal_planning", "recipes_and_groceries", "nutrition", "photo", "pantry", "grocery_app")
KINDS = ("chat", "photo", "pantry_reconcile", "grocery_cart_build")


def fetch_all(table: str, columns: str, since: str | None = None, column: str = "occurred_at") -> list[dict]:
    rows, start, page = [], 0, 1000
    while True:
        query = supabase.table(table).select(columns)
        if since:
            query = query.gte(column, since)
        batch = query.range(start, start + page - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page:
            return rows
        start += page


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(q * len(ordered)) - 1)
    return float(ordered[rank])


def cost(input_tokens: int, output_tokens: int) -> float:
    """Estimated cost in rupees."""
    usd = input_tokens / 1e6 * PRICE_INPUT_PER_M + output_tokens / 1e6 * PRICE_OUTPUT_PER_M
    return round(usd * INR_PER_USD, 4)


def day_of(value: str) -> str:
    return value[:10]


def main() -> None:
    now = datetime.now(timezone.utc)
    today = now.date()
    since = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    days = [(today - timedelta(days=offset)).isoformat() for offset in range(WINDOW_DAYS - 1, -1, -1)]

    events = fetch_all(
        "usage_events",
        "occurred_at,user_key,kind,features,outcome,duration_ms,first_response_ms,model_calls,input_tokens,output_tokens",
    )
    accounts = fetch_all("household_accounts", "created_at")
    households = fetch_all("households", "created_at")
    profile_count = len(fetch_all("profiles", "id"))

    # First day each pseudonymous user appears in the retained metrics.
    first_seen: dict[str, str] = {}
    for e in sorted(events, key=lambda e: e["occurred_at"]):
        first_seen.setdefault(e["user_key"], day_of(e["occurred_at"]))
    recent = [e for e in events if day_of(e["occurred_at"]) >= since]
    served = [e for e in recent if e["outcome"] in ("ok", "limit")]

    by_day: dict[str, list[dict]] = defaultdict(list)
    for e in recent:
        by_day[day_of(e["occurred_at"])].append(e)
    signups = Counter(day_of(a["created_at"]) for a in accounts)
    new_households = Counter(day_of(h["created_at"]) for h in households)

    daily = []
    for d in days:
        rows = by_day.get(d, [])
        users = {e["user_key"] for e in rows}
        durations = [e["duration_ms"] for e in rows if e["outcome"] in ("ok", "limit")]
        firsts = [e["first_response_ms"] for e in rows if e["first_response_ms"] is not None]
        tin = sum(e["input_tokens"] for e in rows)
        tout = sum(e["output_tokens"] for e in rows)
        daily.append({
            "day": d,
            "requests": len(rows),
            "active_users": len(users),
            "new_users": sum(1 for u in users if first_seen.get(u) == d),
            "returning_users": sum(1 for u in users if first_seen.get(u, d) < d),
            **{kind: sum(1 for e in rows if e["kind"] == kind) for kind in KINDS},
            "input_tokens": tin,
            "output_tokens": tout,
            "est_cost_inr": cost(tin, tout),
            "p50_ms": percentile(durations, 0.5),
            "p95_ms": percentile(durations, 0.95),
            "avg_first_response_ms": round(mean(firsts)) if firsts else None,
            "errors": sum(1 for e in rows if e["outcome"] == "error"),
            "limited": sum(1 for e in rows if e["outcome"] in ("limit", "quota")),
            "new_accounts": signups.get(d, 0),
            "new_households": new_households.get(d, 0),
        })

    week_start = (today - timedelta(days=6)).isoformat()
    week = [e for e in recent if day_of(e["occurred_at"]) >= week_start]
    days_per_user_week: dict[str, set] = defaultdict(set)
    for e in week:
        days_per_user_week[e["user_key"]].add(day_of(e["occurred_at"]))
    month_users = {e["user_key"] for e in recent}
    week_users = set(days_per_user_week)
    per_user_month = Counter(e["user_key"] for e in recent)
    dau_avg = mean(row["active_users"] for row in daily)
    durations = [e["duration_ms"] for e in served]
    firsts = [e["first_response_ms"] for e in served if e["first_response_ms"] is not None]
    tin = sum(e["input_tokens"] for e in recent)
    tout = sum(e["output_tokens"] for e in recent)

    summary = [{
        "households": len(households),
        "accounts": len(accounts),
        "members": profile_count,
        "new_accounts_7d": sum(signups.get(d, 0) for d in days[-7:]),
        "active_users_7d": len(week_users),
        "active_users_30d": len(month_users),
        "sticky_users_7d": sum(1 for active in days_per_user_week.values() if len(active) >= 3),
        "one_time_users_30d": sum(1 for n in per_user_month.values() if n == 1),
        "stickiness": round(dau_avg / len(month_users), 3) if month_users else None,
        "requests_30d": len(recent),
        "messages_per_active_user_30d": round(len(recent) / len(month_users), 1) if month_users else None,
        "p50_ms_30d": percentile(durations, 0.5),
        "p95_ms_30d": percentile(durations, 0.95),
        "p99_ms_30d": percentile(durations, 0.99),
        "avg_ms_30d": round(mean(durations)) if durations else None,
        "avg_first_response_ms_30d": round(mean(firsts)) if firsts else None,
        "input_tokens_30d": tin,
        "output_tokens_30d": tout,
        "est_cost_inr_30d": cost(tin, tout),
        "est_cost_inr_per_active_user_30d": round(cost(tin, tout) / len(month_users), 4) if month_users else None,
        "error_rate_30d": round(sum(1 for e in recent if e["outcome"] == "error") / len(recent), 4) if recent else None,
        "limited_30d": sum(1 for e in recent if e["outcome"] in ("limit", "quota")),
        "price_model": PRICE_MODEL,
        "inr_per_usd": INR_PER_USD,
        "generated_at": now.isoformat(timespec="seconds"),
    }]

    by_kind = []
    for kind in KINDS:
        rows = [e for e in served if e["kind"] == kind]
        ds = [e["duration_ms"] for e in rows]
        fs = [e["first_response_ms"] for e in rows if e["first_response_ms"] is not None]
        by_kind.append({
            "kind": kind,
            "requests": len(rows),
            "avg_ms": round(mean(ds)) if ds else None,
            "p50_ms": percentile(ds, 0.5),
            "p95_ms": percentile(ds, 0.95),
            "p99_ms": percentile(ds, 0.99),
            "avg_first_response_ms": round(mean(fs)) if fs else None,
            "avg_model_calls": round(mean(e["model_calls"] for e in rows), 1) if rows else None,
            "avg_tokens": round(mean(e["input_tokens"] + e["output_tokens"] for e in rows)) if rows else None,
            "est_cost_inr": cost(sum(e["input_tokens"] for e in rows), sum(e["output_tokens"] for e in rows)),
        })

    feature_counts = Counter(feature for e in recent for feature in (e.get("features") or []))
    # Every known feature and outcome is listed, with zeros, so the files are
    # never empty; tool names seen in use follow the main features.
    names = list(FEATURES) + sorted((n for n in feature_counts if n not in FEATURES), key=lambda n: -feature_counts[n])
    features = sorted(({"feature": n, "requests": feature_counts.get(n, 0)} for n in names), key=lambda r: -r["requests"])
    outcome_counts = Counter(e["outcome"] for e in recent)
    outcomes = [{"outcome": name, "requests": outcome_counts.get(name, 0)} for name in OUTCOMES]

    buckets = (("1", 1, 1), ("2–5", 2, 5), ("6–10", 6, 10), ("11–25", 11, 25), ("26+", 26, 10**9))
    distribution = [
        {"bucket": label, "users": sum(1 for n in per_user_month.values() if low <= n <= high)}
        for label, low, high in buckets
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": summary, "daily": daily, "by_kind": by_kind, "features": features,
        "outcomes": outcomes, "message_distribution": distribution,
    }
    for name, rows in files.items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, indent=1))
    print(f"wrote {len(files)} files to {OUT} from {len(events)} events ({len(recent)} in the last {WINDOW_DAYS} days)")


if __name__ == "__main__":
    main()
