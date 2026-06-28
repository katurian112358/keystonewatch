"""
Fetch sponsored/co-sponsored bills for each PA legislator from OpenStates.
Outputs: data/bills/{legislator_id}.json per legislator
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OPENSTATES_API_KEY = os.environ.get("OPENSTATES_API_KEY")
OPENSTATES_BASE = "https://v3.openstates.org"
DATA_DIR = Path(__file__).parent.parent / "data"
REQUEST_DELAY = 0.5
MAX_RETRIES = 5


def get_with_backoff(url: str, headers: dict, params: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt * 10
                print(f"    HTTP {resp.status_code} — waiting {wait}s (retry {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            wait = 2 ** attempt * 5
            time.sleep(wait)
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries")

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


SESSIONS = ["2025-2026", "2023-2024"]


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

        # Determine sponsorship role
        role = "cosponsor"
        for sponsor in bill.get("sponsorships", []):
            if sponsor.get("person_id") == legislator_id and sponsor.get("primary"):
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
        legislators = json.loads(leg_path.read_text())
        legislator_ids = [l["id"] for l in legislators]

    bills_dir = DATA_DIR / "bills"
    bills_dir.mkdir(parents=True, exist_ok=True)

    errors = []
    for i, leg_id in enumerate(legislator_ids, 1):
        print(f"  [{i}/{len(legislator_ids)}] Fetching bills for {leg_id}")
        try:
            bills = fetch_bills_for_legislator(leg_id)
            out = bills_dir / f"{leg_id.replace('/', '_')}.json"
            out.write_text(json.dumps(bills, indent=2, ensure_ascii=False))
            print(f"    {len(bills)} bills")
        except Exception as e:
            print(f"    ERROR: {e}", file=sys.stderr)
            errors.append({"legislator_id": leg_id, "error": str(e)})

    return errors


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--legislator-id")
    args = parser.parse_args()
    ids = [args.legislator_id] if args.legislator_id else None
    main(ids)
