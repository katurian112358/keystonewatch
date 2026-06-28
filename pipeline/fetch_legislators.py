"""
Fetch all current PA legislators from OpenStates API.
Outputs: data/legislators.json, data/legislators_by_district.json
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OPENSTATES_API_KEY = os.environ.get("OPENSTATES_API_KEY")
OPENSTATES_BASE = "https://v3.openstates.org"
DATA_DIR = Path(__file__).parent.parent / "data"


def fetch_all_legislators() -> list[dict]:
    """Fetch all current PA legislators via paginated OpenStates API."""
    if not OPENSTATES_API_KEY:
        print("ERROR: OPENSTATES_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    headers = {"X-API-KEY": OPENSTATES_API_KEY}
    legislators = []
    page = 1
    per_page = 50

    while True:
        params = {
            "jurisdiction": "pa",
            "page": page,
            "per_page": per_page,
        }
        resp = requests.get(
            f"{OPENSTATES_BASE}/people",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        # Keep only House (lower) and Senate (upper) members
        results = [
            r for r in results
            if (r.get("current_role") or {}).get("org_classification") in ("lower", "upper")
        ]
        legislators.extend(results)

        pagination = data.get("pagination", {})
        max_page = pagination.get("max_page", 1)
        print(f"  Fetched page {page}/{max_page} ({len(results)} legislators kept)")

        if page >= max_page:
            break
        page += 1

    return legislators


def normalize_legislator(raw: dict) -> dict:
    """Extract and normalize fields we care about from OpenStates person record."""
    current_role = raw.get("current_role") or {}
    extras = raw.get("extras", {}) or {}

    # Website lives in extras.website; email is a top-level field
    website = extras.get("website") or extras.get("Website") or ""
    web_links = [website] if website else []

    # OpenStates v3 doesn't return social links in people endpoint;
    # we store email from the top-level field
    email = raw.get("email") or ""

    contact_details: dict = {}
    if email:
        contact_details["email"] = email
    if website:
        contact_details["website"] = website

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "party": raw.get("party"),
        "chamber": current_role.get("org_classification"),  # 'upper' or 'lower'
        "district": current_role.get("district"),
        "title": current_role.get("title"),
        "image_url": raw.get("image"),
        "openstates_url": raw.get("openstates_url"),
        "web_links": web_links,
        "social_links": {},  # populated by future enrichment step
        "contact_details": contact_details,
    }


def build_district_map(legislators: list[dict]) -> dict:
    """Build lookup keyed by 'house_{district}' or 'senate_{district}'."""
    district_map: dict = {}
    for leg in legislators:
        chamber = leg.get("chamber", "")
        district = leg.get("district", "")
        if chamber and district:
            chamber_label = "house" if chamber == "lower" else "senate"
            key = f"{chamber_label}_{district}"
            district_map.setdefault(key, []).append(leg["id"])
    return district_map


def summarize(legislators: list[dict]) -> None:
    house = [l for l in legislators if l.get("chamber") == "lower"]
    senate = [l for l in legislators if l.get("chamber") == "upper"]

    party_counts: dict = {}
    for leg in legislators:
        p = leg.get("party", "Unknown")
        party_counts[p] = party_counts.get(p, 0) + 1

    print(f"\n--- PA Legislator Fetch Summary ---")
    print(f"Total legislators: {len(legislators)}")
    print(f"  House members:   {len(house)}")
    print(f"  Senate members:  {len(senate)}")
    print("  By party:")
    for party, count in sorted(party_counts.items()):
        print(f"    {party}: {count}")
    print()


def main() -> None:
    print("Fetching PA legislators from OpenStates...")
    raw_legislators = fetch_all_legislators()

    legislators = [normalize_legislator(r) for r in raw_legislators]

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    out_path = DATA_DIR / "legislators.json"
    out_path.write_text(json.dumps(legislators, indent=2, ensure_ascii=False))
    print(f"Wrote {len(legislators)} legislators to {out_path}")

    district_map = build_district_map(legislators)
    map_path = DATA_DIR / "legislators_by_district.json"
    map_path.write_text(json.dumps(district_map, indent=2, ensure_ascii=False))
    print(f"Wrote district map ({len(district_map)} districts) to {map_path}")

    summarize(legislators)


if __name__ == "__main__":
    main()
