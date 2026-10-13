"""
Build voting records and sponsored-bill lists for PA legislators from one
session-wide scan of OpenStates bills. OpenStates v3 has no /votes endpoint;
votes (and sponsorships) are embedded in bill results.

Strategy: page through the session's bills oldest-update-first with
include=votes,sponsorships,actions, storing a compact copy of each bill in a
scan cache. The daily API quota can't cover the whole session in one night, so
the scan resumes from the last updated_at it reached; once it has caught up,
each night only fetches bills updated since. Votes and bills are then derived
from the full cache, so totals don't depend on how far tonight's run got.

The cache lives outside the repo (.cache/, persisted by the workflow with
actions/cache). If it is lost, the scan rebuilds it over a few nights.

Outputs: data/votes/{safe_legislator_id}.json and
         data/bills/{safe_legislator_id}.json per legislator
"""

import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from _http import get_with_backoff, QuotaExhausted
from fetch_bills import normalize_bill
from jsonio import read_json, write_json

load_dotenv()

OPENSTATES_API_KEY = os.environ.get("OPENSTATES_API_KEY")
OPENSTATES_BASE = "https://v3.openstates.org"
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_PATH = Path(__file__).parent.parent / ".cache" / "bill_scan.json"
# Current session only - see note in fetch_bills.py. OpenStates v3 caps /bills at
# 20 results per page (larger values return 400).
SESSIONS = ["2025-2026"]
VOTES_PER_PAGE = 20
REQUEST_DELAY = 1.0   # seconds between requests to stay under rate limit
# Resume a little before the last updated_at reached, so bills sharing that
# timestamp aren't skipped whether updated_since is inclusive or exclusive.
RESUME_OVERLAP = timedelta(minutes=5)


def compact_bill(bill: dict) -> dict:
    """Keep only what normalize_bill and the vote index need. Same field shapes
    as the API response, so both accept either form."""
    return {
        "id": bill.get("id"),
        "identifier": bill.get("identifier"),
        "title": bill.get("title"),
        "session": bill.get("session"),
        "latest_action_description": bill.get("latest_action_description"),
        "subject": bill.get("subject", []),
        "openstates_url": bill.get("openstates_url"),
        "updated_at": bill.get("updated_at"),
        "actions": [
            {"date": a.get("date"), "description": a.get("description")}
            for a in bill.get("actions", [])
        ],
        "sponsorships": [
            {
                "person": {"id": (s.get("person") or {}).get("id")},
                "primary": s.get("primary"),
            }
            for s in bill.get("sponsorships", [])
            if (s.get("person") or {}).get("id")
        ],
        "votes": [
            {
                "start_date": v.get("start_date") or v.get("date"),
                "motion_text": v.get("motion_text", ""),
                "votes": [
                    {
                        "option": vr.get("option", ""),
                        "voter": {
                            "id": (vr.get("voter") or {}).get("id") or vr.get("voter_id"),
                            "party": (vr.get("voter") or {}).get("party"),
                        },
                    }
                    for vr in v.get("votes", [])
                ],
            }
            for v in bill.get("votes", [])
        ],
    }


def load_cache() -> dict:
    cache = read_json(CACHE_PATH, None) or {}
    cache.setdefault("sessions", {})
    return cache


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(CACHE_PATH, cache)


def scan_session(session: str, state: dict) -> None:
    """Fetch bills updated since state["cursor"] into state["bills"], advancing
    the cursor as pages arrive. Raises QuotaExhausted after recording progress
    in state."""
    headers = {"X-API-KEY": OPENSTATES_API_KEY}
    bills = state.setdefault("bills", {})
    cursor = state.get("cursor")
    run_started = datetime.now(timezone.utc).isoformat()
    newest_seen = cursor
    page = 1

    if cursor:
        print(f"    Session {session}: resuming from bills updated since {cursor}")
    else:
        print(f"    Session {session}: no saved scan, starting from the beginning")

    while True:
        params = {
            "jurisdiction": "pa",
            "session": session,
            "include": ["votes", "sponsorships", "actions"],
            "sort": "updated_asc",
            "per_page": VOTES_PER_PAGE,
            "page": page,
        }
        if cursor:
            params["updated_since"] = cursor
        try:
            data = get_with_backoff(f"{OPENSTATES_BASE}/bills", headers, params)
        except QuotaExhausted:
            if newest_seen and newest_seen != cursor:
                state["cursor"] = resume_point(newest_seen)
            state["caught_up"] = False
            print(f"    Quota exhausted at page {page}; next run resumes from "
                  f"{state.get('cursor')}", file=sys.stderr)
            raise

        for raw in data.get("results", []):
            bills[raw["id"]] = compact_bill(raw)
            updated = raw.get("updated_at")
            if updated and (not newest_seen or updated > newest_seen):
                newest_seen = updated

        pagination = data.get("pagination", {})
        max_page = pagination.get("max_page", 1)
        if page == 1:
            print(f"    {pagination.get('total_items', 0)} bills to fetch "
                  f"across {max_page} pages")
        if page % 25 == 0:
            print(f"    ... page {page}/{max_page}")

        time.sleep(REQUEST_DELAY)
        if page >= max_page:
            break
        page += 1

    # Caught up: next run only needs bills updated after this one started
    state["cursor"] = resume_point(run_started)
    state["caught_up"] = True


def resume_point(iso_ts: str) -> str:
    ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    return (ts - RESUME_OVERLAP).isoformat()


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

            # Tally chamber-wide totals from individual voter records
            voter_records = vote_event.get("votes", [])
            yes_total = sum(1 for v in voter_records if v.get("option", "").lower() == "yes")
            no_total = sum(1 for v in voter_records if v.get("option", "").lower() == "no")

            # Tally per-party totals so we can derive each party's majority choice
            party_counts: dict[str, dict[str, int]] = defaultdict(
                lambda: {"yes": 0, "no": 0}
            )
            for v in voter_records:
                opt = v.get("option", "").lower()
                party = ((v.get("voter") or {}).get("party")) or ""
                if party and opt in ("yes", "no"):
                    party_counts[party][opt] += 1

            for voter in voter_records:
                person = voter.get("voter") or {}
                person_id = person.get("id") or voter.get("voter_id")
                if not person_id:
                    continue
                choice = voter.get("option", "").lower()

                # This member's own party's majority choice on this vote
                party = person.get("party") or ""
                pc = party_counts.get(party)
                party_majority = None
                if pc:
                    if pc["yes"] > pc["no"]:
                        party_majority = "yes"
                    elif pc["no"] > pc["yes"]:
                        party_majority = "no"

                index[person_id].append({
                    "bill_id": bill.get("id"),
                    "bill_identifier": bill.get("identifier"),
                    "bill_title": bill.get("title"),
                    "vote": choice,
                    "date": date,
                    "motion": motion,
                    "yes_total": yes_total,
                    "no_total": no_total,
                    "party_majority": party_majority,
                })

    return dict(index)


def build_legislator_bill_index(bills: list[dict]) -> dict[str, list[dict]]:
    """Returns {legislator_id: [normalized bill, ...]} for every sponsor."""
    index: dict[str, list[dict]] = defaultdict(list)
    for bill in bills:
        sponsor_ids = {(s.get("person") or {}).get("id") for s in bill.get("sponsorships", [])}
        for leg_id in sponsor_ids - {None}:
            index[leg_id].append(normalize_bill(bill, leg_id))
    return dict(index)


def compute_stats(legislator_id: str, vote_records: list[dict]) -> dict:
    yes_count = no_count = absent_count = other_count = 0
    chamber_align = []   # voted with the winning side of each measure
    party_align = []     # voted with the majority of their own party

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

        if choice not in ("yes", "no"):
            continue

        # Winning side: did the legislator vote with the chamber's outcome?
        yes_t = r.get("yes_total", 0)
        no_t = r.get("no_total", 0)
        if yes_t + no_t > 0:
            majority = "yes" if yes_t > no_t else "no"
            chamber_align.append(1 if choice == majority else 0)

        # Party unity: did the legislator vote with their own party's majority?
        party_majority = r.get("party_majority")
        if party_majority:
            party_align.append(1 if choice == party_majority else 0)

    total = yes_count + no_count + absent_count + other_count
    attendance_rate = round((yes_count + no_count) / total, 4) if total > 0 else None
    partisan_score = round(sum(chamber_align) / len(chamber_align), 4) if chamber_align else None
    party_unity_score = round(sum(party_align) / len(party_align), 4) if party_align else None

    recent = sorted(vote_records, key=lambda r: r.get("date") or "", reverse=True)[:20]

    return {
        "legislator_id": legislator_id,
        "total_votes": total,
        "yes_count": yes_count,
        "no_count": no_count,
        "absent_count": absent_count,
        "attendance_rate": attendance_rate,
        "partisan_score": partisan_score,
        "party_unity_score": party_unity_score,
        "recent_votes": recent,
    }


def main(legislator_ids: list[str] | None = None) -> list[dict]:
    if not OPENSTATES_API_KEY:
        print("ERROR: OPENSTATES_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    votes_dir = DATA_DIR / "votes"
    bills_dir = DATA_DIR / "bills"
    votes_dir.mkdir(parents=True, exist_ok=True)
    bills_dir.mkdir(parents=True, exist_ok=True)

    print("  Scanning PA bills for votes and sponsorships...")
    cache = load_cache()
    errors = []
    all_caught_up = True
    for session in SESSIONS:
        state = cache["sessions"].setdefault(session, {})
        try:
            scan_session(session, state)
        except QuotaExhausted:
            all_caught_up = False
            errors.append({"step": "fetch_votes",
                           "error": "quota exhausted, partial scan (resumes next run)"})
            break
        except Exception as e:
            all_caught_up = False
            print(f"    ERROR scanning session {session}: {e}", file=sys.stderr)
            errors.append({"step": "fetch_votes", "session": session, "error": str(e)})
        finally:
            # Persist whatever arrived, even if the scan stopped early
            save_cache(cache)

    bills = [b for s in cache["sessions"].values() for b in s.get("bills", {}).values()]
    # Until the scan has covered the whole session once, totals from the cache
    # may undercount; don't let them replace larger numbers already published.
    ever_caught_up = all(s.get("caught_up_once") for s in cache["sessions"].values())
    if all_caught_up:
        for s in cache["sessions"].values():
            s["caught_up_once"] = True
        save_cache(cache)
        ever_caught_up = True
    print(f"    Scan cache: {len(bills)} bills"
          + ("" if all_caught_up else " (scan still catching up)"))

    vote_index = build_legislator_vote_index(bills)
    bill_index = build_legislator_bill_index(bills)

    if legislator_ids:
        target_ids = set(legislator_ids)
    else:
        legislators = read_json(DATA_DIR / "legislators.json", [])
        target_ids = {l["id"] for l in legislators}

    votes_written = bills_written = 0
    for leg_id in target_ids:
        safe_id = leg_id.replace("/", "_")

        vote_path = votes_dir / f"{safe_id}.json"
        stats = compute_stats(leg_id, vote_index.get(leg_id, []))
        existing = read_json(vote_path, None)
        if ever_caught_up or not existing or stats["total_votes"] >= existing.get("total_votes", 0):
            write_json(vote_path, stats)
            votes_written += 1

        # Merge with what's on file so a partial cache never drops bills
        bill_path = bills_dir / f"{safe_id}.json"
        new_bills = bill_index.get(leg_id, [])
        if new_bills:
            merged = {b["id"]: b for b in read_json(bill_path, []) or []}
            merged.update({b["id"]: b for b in new_bills})
            write_json(bill_path, list(merged.values()))
            bills_written += 1

    print(f"  Wrote vote stats for {votes_written} and bills for {bills_written} legislators")
    return errors


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--legislator-id")
    args = parser.parse_args()
    ids = [args.legislator_id] if args.legislator_id else None
    main(ids)
