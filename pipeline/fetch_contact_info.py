"""
Compile contact information for all PA legislators from legislators.json.
Outputs: data/contacts.json - flat lookup keyed by legislator_id
"""

from pathlib import Path

from jsonio import read_json, write_json

DATA_DIR = Path(__file__).parent.parent / "data"


def main() -> list[dict]:
    leg_path = DATA_DIR / "legislators.json"
    legislators = read_json(leg_path, [])

    contacts = {}
    for leg in legislators:
        contacts[leg["id"]] = {
            "name": leg["name"],
            "contact_details": leg.get("contact_details", {}),
            "web_links": leg.get("web_links", []),
            "social_links": leg.get("social_links", {}),
        }

    out = DATA_DIR / "contacts.json"
    write_json(out, contacts)
    print(f"Wrote contacts for {len(contacts)} legislators to {out}")
    return []


if __name__ == "__main__":
    main()
