"""
Build voting records for PA legislators by scanning all PA bills with vote data.
OpenStates v3 has no /votes endpoint; votes are embedded in bill results.

Strategy: fetch all PA bills for current + prior session with include=votes,
then build a per-legislator vote index. Run once, writes all legislators.

Outputs: data/votes/{safe_legislator_id}.json per legislator
"""

import json
import sys
import time
import os
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from _http import get_with_backoff, QuotaExhausted
from jsonio import read_json, write_json

load_dotenv()

OPENSTATES_API_KEY = os.environ.get("OPENSTATES_API_KEY")
OPENSTATES_BASE = "https://v3.openstates.org"
DATA_DIR = Path(__file__).parent.parent / "data"
# Current session only - see note in fetch_bills.py. A single scan at per_page=50
# is ~100 requests, leaving room under the daily quota for the bills step.
SESSIONS = ["2025-2026"]
VOTES_PER_PAGE = 50
REQUEST_DELAY = 1.0   # seconds between requests to stay under rate limit


def fetch_bills_with_votes(session: str) -> list[dict]:
    """Fetch all PA bills for a session, including embedded vote records."""
    headers = {"X-API-KEY": OPENSTATES_API_KEY}
    bills = []
    page = 1

    while True:
        params = {
            "jurisdiction": "pa",
            "session": session,
            "include": ["votes"],
            "per_page": VOTES_PER_PAGE,
            "page": page,
        }
        try:
            data = get_with_backoff(f"{OPENSTATES_BASE}/bills", headers, params)
        except QuotaExhausted:
            # Preserve whatever we collected so far rather than losing the scan
            print(f"    Quota exhausted at page {page} - keeping {len(bills)} bills "
                  "collected so far", file=sys.stderr)
            raise QuotaExhausted(_partial=bills)
        results = data.get("results", [])
        bills.extend(results)

        pagination = data.get("pagination", {})
        max_page = pagination.get("max_page", 1)
        total = pagination.get("total_items", 0)
        if page == 1:
            print(f"    Session {session}: {total} bills across {max_page} pages")
        if page % 25 == 0:
            print(f"    ... page {page}/{max_page}")

        time.sleep(REQUEST_DELAY)

        if page >= max_page:
            break
        page += 1

    return bills


def build_legislator_vote_index(bills: list[dict]) -> dict[str, list[dict]]:
    """
    Returns {legislator_id: [vote_record, ...]} from all bills.
    Each vote_record: {bill_id, bill_title, bill_identifier, vote, date, motion}
    """
    index: dict[str, list[dict]] = defaultdict(list)

    for bill in bills:
        for vote_event in bill.get("votes", []):
            date = vote_event.get("start_date") or vote_event.get("date")
            motion = vote_event.get("motion_text", "")

            # Tally totals from individual voter records
            voter_records = vote_event.get("votes", [])
            yes_total = sum(1 for v in voter_records if v.get("option", "").lower() == "yes")
            no_total = sum(1 for v in voter_records if v.get("option", "").lower() == "no")

            for voter in voter_records:
                person = voter.get("voter") or {}
                person_id = person.get("id") or voter.get("voter_id")
                if not person_id:
                    continue
                choice = voter.get("option", "").lower()
                index[person_id].append({
                    "bill_id": bill.get("id"),
                    "bill_identifier": bill.get("identifier"),
                    "bill_title": bill.get("title"),
                    "vote": choice,
                    "date": date,
                    "motion": motion,
                    "yes_total": yes_total,
                    "no_total": no_total,
                })

    return dict(index)


def compute_stats(legislator_id: str, vote_records: list[dict]) -> dict:
    yes_count = no_count = absent_count = other_count = 0
    chamber_align = []

    for r in vote_records:
        choice = r.get("vote", "")
        if choice == "yes":
            yes_count += 1
        elif choice == "no":
            no_count += 1
        elif choice in ("absent", "excused", "not voting", "abstain"):
            absent_count += 1
        else:
            other_count += 1

        # Partisan alignment: did legislator vote with the majority of the chamber?
        yes_t = r.get("yes_total", 0)
        no_t = r.get("no_total", 0)
        if yes_t + no_t > 0:
            majority = "yes" if yes_t > no_t else "no"
            if choice in ("yes", "no"):
                chamber_align.append(1 if choice == majority else 0)

    total = yes_count + no_count + absent_count + other_count
    attendance_rate = round((yes_count + no_count) / total, 4) if total > 0 else None
    partisan_score = round(sum(chamber_align) / len(chamber_align), 4) if chamber_align else None

    recent = sorted(vote_records, key=lambda r: r.get("date") or "", reverse=True)[:20]

    return {
        "legislator_id": legislator_id,
        "total_votes": total,
        "yes_count": yes_count,
        "no_count": no_count,
        "absent_count": absent_count,
        "attendance_rate": attendance_rate,
        "partisan_score": partisan_score,
        "recent_votes": recent,
    }


def main(legislator_ids: list[str] | None = None) -> list[dict]:
    if not OPENSTATES_API_KEY:
        print("ERROR: OPENSTATES_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    votes_dir = DATA_DIR / "votes"
    votes_dir.mkdir(parents=True, exist_ok=True)

    # If running for a single legislator, we still need to scan all bills
    # (no per-person vote endpoint exists). We scan and then filter.
    print("  Scanning PA bills for vote records (this takes a few minutes)...")
    all_vote_records: dict[str, list] = defaultdict(list)

    errors = []
    quota_hit = False
    for session in SESSIONS:
        try:
            bills = fetch_bills_with_votes(session)
        except QuotaExhausted as e:
            # Index whatever we managed to collect, then stop scanning
            bills = e.partial
            quota_hit = True
        except Exception as e:
            print(f"    ERROR fetching session {session}: {e}", file=sys.stderr)
            errors.append({"step": "fetch_votes", "session": session, "error": str(e)})
            continue

        session_index = build_legislator_vote_index(bills)
        for leg_id, records in session_index.items():
            all_vote_records[leg_id].extend(records)

        if quota_hit:
            print("    API quota exhausted - stopping vote scan; writing partial "
                  "results", file=sys.stderr)
            errors.append({"step": "fetch_votes", "error": "quota exhausted, partial scan"})
            break

    # Determine which legislators to write
    if legislator_ids:
        target_ids = set(legislator_ids)
    else:
        leg_path = DATA_DIR / "legislators.json"
        legislators = read_json(leg_path, [])
        target_ids = {l["id"] for l in legislators}

    written = 0
    for leg_id in target_ids:
        records = all_vote_records.get(leg_id, [])
        # On a partial (quota-limited) scan, don't overwrite an existing file with
        # zeros - a legislator's votes may simply be in pages we never reached.
        if quota_hit and not records:
            safe_id = leg_id.replace("/", "_")
            if (votes_dir / f"{safe_id}.json").exists():
                continue
        stats = compute_stats(leg_id, records)
        out = votes_dir / f"{leg_id.replace('/', '_')}.json"
        write_json(out, stats)
        written += 1

    print(f"  Wrote vote stats for {written} legislators"
          + (" (partial scan)" if quota_hit else ""))
    return errors


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--legislator-id")
    args = parser.parse_args()
    ids = [args.legislator_id] if args.legislator_id else None
    main(ids)
