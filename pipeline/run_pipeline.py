"""
Orchestrator: runs all pipeline steps in order.
Usage:
  python run_pipeline.py                        # full run
  python run_pipeline.py --legislator-id ocd-person/...  # single legislator
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def log_section(name: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")


def run_step(name: str, fn, leg_ids: list[str] | None) -> list[dict]:
    log_section(name)
    t0 = time.time()
    try:
        errors = fn(leg_ids) if leg_ids is not None else fn()
        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.1f}s — {len(errors or [])} error(s)")
        return errors or []
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  FATAL in {elapsed:.1f}s: {e}", file=sys.stderr)
        return [{"step": name, "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}]


def main() -> None:
    parser = argparse.ArgumentParser(description="keystonewatch data pipeline")
    parser.add_argument(
        "--legislator-id",
        help="Run pipeline for a single legislator ID (for testing)",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip press release scraping (useful when debugging other steps)",
    )
    parser.add_argument(
        "--skip-votes",
        action="store_true",
        help="Skip vote scan (saves ~500 API calls; use locally when quota is limited)",
    )
    args = parser.parse_args()

    leg_ids = [args.legislator_id] if args.legislator_id else None

    # Import here so missing deps don't crash before argparse
    import fetch_legislators
    import fetch_votes
    import fetch_bills
    import scrape_press_releases
    import summarize_releases
    import fetch_contact_info

    all_errors: list[dict] = []
    t_start = time.time()

    # Step 1: Always fetch legislators first (needed by downstream steps)
    if leg_ids is None:
        errs = run_step("1. Fetch legislators", lambda: fetch_legislators.main() or [], None)
        all_errors.extend(errs)
    else:
        print("Skipping full legislator fetch (single-legislator mode)")

    # Step 2: Bills (cheap — a few pages per legislator; run before expensive vote scan)
    errs = run_step("2. Fetch bills", fetch_bills.main, leg_ids)
    all_errors.extend(errs)

    # Step 3: Votes (expensive — scans all PA bills; fine for nightly job, quota-heavy locally)
    if not args.skip_votes:
        errs = run_step("3. Fetch votes", fetch_votes.main, leg_ids)
        all_errors.extend(errs)
    else:
        print("\nSkipping vote scan (--skip-votes)")

    # Step 4: Press release scraping (can skip)
    if not args.skip_scrape:
        errs = run_step("4. Scrape press releases", scrape_press_releases.main, leg_ids)
        all_errors.extend(errs)
    else:
        print("\nSkipping press release scraping (--skip-scrape)")

    # Step 5: AI summarization
    errs = run_step("5. Summarize releases", summarize_releases.main, leg_ids)
    all_errors.extend(errs)

    # Step 6: Compile contacts
    if leg_ids is None:
        errs = run_step("6. Compile contacts", lambda: fetch_contact_info.main() or [], None)
        all_errors.extend(errs)

    # Write pipeline errors
    errors_path = DATA_DIR / "pipeline_errors.json"
    existing = json.loads(errors_path.read_text()) if errors_path.exists() else []
    errors_path.write_text(json.dumps(existing + all_errors, indent=2, ensure_ascii=False))

    # Write last_updated
    last_updated = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": len(all_errors),
        "runtime_seconds": round(time.time() - t_start, 1),
    }
    (DATA_DIR / "last_updated.json").write_text(
        json.dumps(last_updated, indent=2, ensure_ascii=False)
    )

    log_section("Pipeline complete")
    print(f"  Total runtime: {last_updated['runtime_seconds']}s")
    print(f"  Total errors:  {len(all_errors)}")
    if all_errors:
        print(f"  See data/pipeline_errors.json for details")
        sys.exit(1)


if __name__ == "__main__":
    main()
