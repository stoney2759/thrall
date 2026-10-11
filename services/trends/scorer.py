"""
Trend Radar Scorer
Reads daily JSONL snapshots, computes confidence scores, writes ranked report.

Usage:
    python services/trends/scorer.py
    python services/trends/scorer.py --workspace workspace/trends --min-days 2 --threshold 60
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


# ── Weights ────────────────────────────────────────────────────────────────────
W_VELOCITY    = 0.35
W_CONSISTENCY = 0.30
W_SATURATION  = 0.25
W_CROSS       = 0.10


def load_snapshots(snapshots_dir: Path) -> dict[str, list[dict]]:
    """Return {topic: [snapshot, ...]} sorted oldest-first."""
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(snapshots_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                snap = json.loads(line)
                topic = snap.get("topic", "").strip()
                if topic:
                    by_topic[topic].append(snap)
            except json.JSONDecodeError:
                continue
    # Sort each topic's history oldest-first
    for snaps in by_topic.values():
        snaps.sort(key=lambda s: s.get("date", ""))
    return dict(by_topic)


def _yt_recent(snap: dict) -> int:
    return snap.get("youtube", {}).get("recent_count", 0)

def _yt_total(snap: dict) -> int:
    return snap.get("youtube", {}).get("result_count", 0)

def _source_count(snap: dict) -> int:
    """Number of sources that returned non-zero data."""
    count = 0
    yt = snap.get("youtube", {})
    if yt.get("result_count", 0) > 0:
        count += 1
    web = snap.get("web", {})
    if web.get("result_count", 0) > 0:
        count += 1
    reddit = snap.get("reddit", {})
    if reddit.get("post_count", 0) > 0:
        count += 1
    return count


def velocity_score(history: list[dict]) -> float:
    """Growth rate of recent YouTube videos over the observation window."""
    if len(history) < 2:
        return 0.0
    oldest = _yt_recent(history[0])
    newest = _yt_recent(history[-1])
    if oldest == 0:
        return 50.0 if newest > 0 else 0.0
    growth = (newest - oldest) / oldest
    # Sigmoid-style clamp: 100% growth → score 80, 200% → ~95
    return min(100.0, max(0.0, growth * 50))


def consistency_score(history: list[dict]) -> float:
    """Fraction of consecutive days where recent_count grew."""
    if len(history) < 2:
        return 0.0
    growth_days = 0
    for i in range(1, len(history)):
        if _yt_recent(history[i]) > _yt_recent(history[i - 1]):
            growth_days += 1
    return (growth_days / (len(history) - 1)) * 100.0


def saturation_score(history: list[dict]) -> float:
    """Inverse saturation — low existing video count = high score (early entry)."""
    latest = history[-1]
    total = _yt_total(latest)
    if total == 0:
        return 80.0  # unknown = moderate optimism
    # log10 scale: 100 vids → ~60, 1000 → ~40, 10000 → ~20, 100000 → 0
    score = max(0.0, 100.0 - math.log10(max(1, total)) * 20)
    return score


def cross_source_score(history: list[dict]) -> float:
    """How many independent sources confirm the signal in latest snapshot."""
    latest = history[-1]
    sources = _source_count(latest)
    return (sources / 3) * 100.0  # 3 sources = full score


def confidence(history: list[dict]) -> float:
    v = velocity_score(history)
    c = consistency_score(history)
    s = saturation_score(history)
    x = cross_source_score(history)
    return round(
        v * W_VELOCITY + c * W_CONSISTENCY + s * W_SATURATION + x * W_CROSS, 1
    )


def score_all(by_topic: dict[str, list[dict]], min_days: int) -> list[dict]:
    results = []
    for topic, history in by_topic.items():
        if len(history) < min_days:
            continue
        latest = history[-1]
        results.append({
            "topic": topic,
            "confidence": confidence(history),
            "days_tracked": len(history),
            "velocity": round(velocity_score(history), 1),
            "consistency": round(consistency_score(history), 1),
            "saturation": round(saturation_score(history), 1),
            "cross_source": round(cross_source_score(history), 1),
            "latest_date": latest.get("date", ""),
            "yt_recent": _yt_recent(latest),
            "yt_total": _yt_total(latest),
        })
    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results


def render_report(results: list[dict], threshold: float, today: str) -> str:
    lines = [
        f"# Trend Radar — {today}",
        "",
        f"Topics scored: {len(results)}  |  Threshold: {threshold}+",
        "",
    ]

    actionable = [r for r in results if r["confidence"] >= threshold]
    watch = [r for r in results if 40 <= r["confidence"] < threshold]
    cold = [r for r in results if r["confidence"] < 40]

    def _row(r: dict) -> str:
        bar = "█" * int(r["confidence"] // 10) + "░" * (10 - int(r["confidence"] // 10))
        return (
            f"### {r['topic']}\n"
            f"**Confidence: {r['confidence']}** `{bar}`  "
            f"({r['days_tracked']}d tracked)\n\n"
            f"| Velocity | Consistency | Saturation | Cross-source |\n"
            f"|----------|-------------|------------|---------------|\n"
            f"| {r['velocity']} | {r['consistency']} | {r['saturation']} | {r['cross_source']} |\n\n"
            f"YouTube: {r['yt_recent']} recent / {r['yt_total']} total  |  Latest: {r['latest_date']}\n"
        )

    if actionable:
        lines += ["## 🟢 Act Now", ""]
        for r in actionable:
            lines.append(_row(r))
    else:
        lines += ["## 🟢 Act Now", "", "_No topics above threshold yet._", ""]

    if watch:
        lines += ["## 🟡 Building Signal", ""]
        for r in watch:
            lines.append(_row(r))

    if cold:
        lines += ["## 🔴 Cold / Fading", ""]
        for r in cold:
            lines += [f"- **{r['topic']}** — {r['confidence']} confidence ({r['days_tracked']}d)"]
        lines.append("")

    lines += [
        "---",
        "_Confidence = Velocity×0.35 + Consistency×0.30 + Saturation×0.25 + Cross-source×0.10_",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend Radar Scorer")
    parser.add_argument("--workspace", default="workspace/trends", help="Trends workspace path")
    parser.add_argument("--min-days", type=int, default=2, help="Minimum days of data required to score a topic")
    parser.add_argument("--threshold", type=float, default=75.0, help="Confidence threshold for 'Act Now'")
    parser.add_argument("--json", action="store_true", help="Also write scores.json")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    snapshots_dir = workspace / "snapshots"
    reports_dir = workspace / "reports"

    if not snapshots_dir.exists():
        print(f"No snapshots directory found at {snapshots_dir}", file=sys.stderr)
        sys.exit(1)

    reports_dir.mkdir(parents=True, exist_ok=True)

    by_topic = load_snapshots(snapshots_dir)
    if not by_topic:
        print("No snapshot data found.", file=sys.stderr)
        sys.exit(0)

    results = score_all(by_topic, args.min_days)
    today = date.today().isoformat()
    report = render_report(results, args.threshold, today)

    report_path = reports_dir / f"trend_radar_{today}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Report written: {report_path}")

    if args.json:
        json_path = reports_dir / f"trend_radar_{today}.json"
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"JSON written:   {json_path}")

    if results:
        print(f"\nTop topics today:")
        for r in results[:5]:
            flag = "🟢" if r["confidence"] >= args.threshold else "🟡" if r["confidence"] >= 40 else "🔴"
            print(f"  {flag} {r['topic']:<40} {r['confidence']:>5.1f}")


if __name__ == "__main__":
    main()
