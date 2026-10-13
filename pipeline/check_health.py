"""
Post-run health check for the nightly pipeline.

run_pipeline.py deliberately exits 0 so the workflow always commits whatever
data it fetched. That also hid real breakage: a bad API request failed every
vote and bill fetch for months under a green check. This script runs after the
commit step and fails the job only on problems that mean the data is broken,
while routine noise (press-release scrape misses, daily quota limits) is
reported as warnings.

Usage: python check_health.py [--pipeline-outcome success|failure|cancelled]
Exits 1 if any critical problem is found.
"""

import argparse
import os
import sys
from pathlib import Path

from jsonio import read_json

DATA_DIR = Path(__file__).parent.parent / "data"


def is_expected(err: dict) -> bool:
    """Errors the pipeline is designed to tolerate night to night."""
    if err.get("step") == "scrape_press_releases" or err.get("severity") == "warning":
        return True
    return "quota exhausted" in (err.get("error") or "")


def describe(err: dict) -> str:
    who = err.get("legislator_id") or err.get("session") or ""
    label = err.get("step", "unknown step") + (f" [{who}]" if who else "")
    return f"{label}: {(err.get('error') or '')[:200]}"


def annotate(level: str, msg: str) -> None:
    # GitHub Actions renders these as annotations on the run page
    print(f"::{level}::{msg}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-outcome", default="success")
    args = parser.parse_args()

    critical: list[str] = []
    warnings: list[str] = []

    if args.pipeline_outcome != "success":
        critical.append(
            f"Pipeline step finished with outcome '{args.pipeline_outcome}' "
            "(crashed, timed out, or missing an API key); see its log"
        )

    errors = read_json(DATA_DIR / "pipeline_errors.json", []) or []
    unexpected = [e for e in errors if not is_expected(e)]
    expected = [e for e in errors if is_expected(e)]

    for e in unexpected:
        critical.append(describe(e))
    quota = [e for e in expected if e.get("step") != "scrape_press_releases"]
    for e in quota:
        warnings.append(describe(e))
    scrape_count = len(expected) - len(quota)
    if scrape_count:
        warnings.append(f"{scrape_count} press-release scrape(s) skipped")

    vote_files = list((DATA_DIR / "votes").glob("*.json"))
    if not vote_files:
        critical.append("No vote files in data/votes/")
    else:
        with_votes = sum(
            1 for f in vote_files if (read_json(f, {}) or {}).get("total_votes", 0) > 0
        )
        if with_votes == 0:
            critical.append(
                f"All {len(vote_files)} vote files have zero recorded votes"
            )

    bill_files = list((DATA_DIR / "bills").glob("*.json"))
    if not bill_files:
        warnings.append("No bill files in data/bills/ yet")

    lines = ["## Pipeline health", ""]
    lines.append(f"- Logged errors: {len(errors)} "
                 f"({len(unexpected)} unexpected, {len(expected)} expected)")
    lines.append(f"- Vote files: {len(vote_files)}, bill files: {len(bill_files)}")
    if critical:
        lines += ["", "### Critical", *[f"- {c}" for c in critical]]
    if warnings:
        lines += ["", "### Warnings", *[f"- {w}" for w in warnings]]
    report = "\n".join(lines)
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")

    # Cap annotations so one systemic failure doesn't bury the run page
    for c in critical[:10]:
        annotate("error", c)
    for w in warnings[:10]:
        annotate("warning", w)

    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
