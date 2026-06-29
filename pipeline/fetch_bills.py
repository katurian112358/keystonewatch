"""
Fetch sponsored/co-sponsored bills for each PA legislator from OpenStates.
Outputs: data/bills/{legislator_id}.json per legislator
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from _http import get_with_backoff, QuotaExhausted
from jsonio import read_json, write_json

load_dotenv()

OPENSTATES_API_KEY = os.environ.get("OPENSTATES_API_KEY")
OPENSTATES_BASE = "https://v3.openstates.org"
DATA_DIR = Path(__file__).parent.parent / "data"
REQUEST_DELAY = 1.0          # seconds between requests
# Skip legislators whose bills were fetched within this many days. Bills are the
# most expensive step (~hundreds of pages each); under a daily API quota we cannot
# refresh all 251 in one run, so we rotate - each night fills in the stalest ones.
BILLS_FRESH_DAYS = 6

# Actions that indicate meaningful progress
INSTRUMENTAL_KEYWORDS = {
    "passed", "signed", "enacted", "committee", "referred", "amended", "reported"
}


def is_instrumental(bill: dict) -> bool:
    actions = bill.get("actions", [])
    for action in actions:
        desc = (action.get("description") or "").lower()
        if any(kw in desc for kw in INSTRUMENTAL_KEYWORDS):
            return True
    return False


# Current session only. The free OpenStates quota (~250 req/day) is too small to
# refresh both sessions plus votes; current-session activity is what the dashboard
# leads with. Add "2023-2024" back here if the API quota is raised.
SESSIONS = ["2025-2026"]


def fetch_bills_for_legislator(legislator_id: str) -> list[dict]:
    headers = {"X-API-KEY": OPENSTATES_API_KEY}
    all_bills = []

    for session in SESSIONS:
        page = 1
        while True:
            params = {
                "sponsor": legislator_id,
                "jurisdiction": "pa",
                "session": session,
                "include": ["sponsorships", "actions"],
                "page": page,
                "per_page": 50,
            }
            data = get_with_backoff(f"{OPENSTATES_BASE}/bills", headers, params)
            time.sleep(REQUEST_DELAY)
            results = data.get("results", [])
            all_bills.extend(results)

            pagination = data.get("pagination", {})
            if page >= pagination.get("max_page", 1):
                break
            page += 1

    normalized = []
    for bill in all_bills:
        latest_action = None
        if bill.get("actions"):
            latest_action = sorted(
                bill["actions"], key=lambda a: a.get("date", ""), reverse=True
            )[0]

        # Determine sponsorship role. The API nests the person id under
        # sponsorship.person.id (not a flat person_id field).
        role = "cosponsor"
        for sponsor in bill.get("sponsorships", []):
            sponsor_person_id = (sponsor.get("person") or {}).get("id")
            if sponsor_person_id == legislator_id and sponsor.get("primary"):
                role = "primary"
                break

        normalized.append({
            "id": bill.get("id"),
            "identifier": bill.get("identifier"),
            "title": bill.get("title"),
            "session": bill.get("session"),
            "status": bill.get("latest_action_description"),
            "subjects": bill.get("subject", []),
            "latest_action": latest_action,
            "openstates_url": bill.get("openstates_url"),
            "sponsorship_role": role,
            "instrumental": is_instrumental(bill),
        })

    return normalized


def main(legislator_ids: list[str] | None = None) -> list[dict]:
    if not OPENSTATES_API_KEY:
        print("ERROR: OPENSTATES_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    if legislator_ids is None:
        leg_path = DATA_DIR / "legislators.json"
        legislators = read_json(leg_path, [])
        legislator_ids = [l["id"] for l in legislators]

    bills_dir = DATA_DIR / "bills"
    bills_dir.mkdir(parents=True, exist_ok=True)

    # Single-legislator runs always refresh; full runs skip recently-fetched files
    # so each nightly run spends its quota on the stalest legislators.
    skip_fresh = len(legislator_ids) > 1
    now = datetime.now(timezone.utc)

    errors = []
    fetched = skipped = 0
    for i, leg_id in enumerate(legislator_ids, 1):
        out = bills_dir / f"{leg_id.replace('/', '_')}.json"

        if skip_fresh and out.exists():
            age_days = (now.timestamp() - out.stat().st_mtime) / 86400
            if age_days < BILLS_FRESH_DAYS:
                skipped += 1
                continue

        print(f"  [{i}/{len(legislator_ids)}] Fetching bills for {leg_id}")
        try:
            bills = fetch_bills_for_legislator(leg_id)
            write_json(out, bills)
            print(f"    {len(bills)} bills")
            fetched += 1
        except QuotaExhausted:
            print("    API quota exhausted - stopping bills step early "
                  f"(fetched {fetched}, {len(legislator_ids) - i} legislators "
                  "left for a future run)", file=sys.stderr)
            errors.append({"step": "fetch_bills", "error": "quota exhausted, stopped early"})
            break
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            errors.append({"legislator_id": leg_id, "error": str(e)})

    print(f"  Bills: {fetched} fetched, {skipped} skipped (still fresh)")
    return errors


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--legislator-id")
    args = parser.parse_args()
    ids = [args.legislator_id] if args.legislator_id else None
    main(ids)
