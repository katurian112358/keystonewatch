"""
Compile contact information for all PA legislators from legislators.json.
Outputs: data/contacts.json — flat lookup keyed by legislator_id
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def main() -> list[dict]:
    leg_path = DATA_DIR / "legislators.json"
    legislators = json.loads(leg_path.read_text())

    contacts = {}
    for leg in legislators:
        contacts[leg["id"]] = {
            "name": leg["name"],
            "contact_details": leg.get("contact_details", {}),
            "web_links": leg.get("web_links", []),
            "social_links": leg.get("social_links", {}),
        }

    out = DATA_DIR / "contacts.json"
    out.write_text(json.dumps(contacts, indent=2, ensure_ascii=False))
    print(f"Wrote contacts for {len(contacts)} legislators to {out}")
    return []


if __name__ == "__main__":
    main()
