"""
Summarize press releases using Claude API.
Updates data/press_releases/{legislator_id}.json in-place, adding ai_summary fields.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"

SYSTEM_PROMPT = """You are a nonpartisan legislative analyst. Translate the following Pennsylvania \
legislator press release into plain language for a general audience.

Return a JSON object with exactly these fields:
- "summary": 2–3 sentence plain-language description of what the legislator \
actually did or said (not what they claimed, what they did)
- "action_type": one of [bill_introduced, bill_passed, statement, event, \
award, committee_action, budget, other]
- "topics": array of 1–3 topic tags from [education, healthcare, public_safety, \
economy, infrastructure, environment, housing, voting_rights, other]
- "spin_flag": boolean — true if the release contains significant self-promotional \
framing that obscures the actual action taken

Return only valid JSON. No preamble."""


def summarize_release(client: anthropic.Anthropic, raw_text: str) -> dict | None:
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": raw_text[:8000]}],
        )
        text = message.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"    Summarization error: {e}", file=sys.stderr)
        return None


def main(legislator_ids: list[str] | None = None) -> list[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    # max_retries lets the SDK back off automatically on 429/529 during the
    # first large run when many releases are summarized in a burst.
    client = anthropic.Anthropic(api_key=api_key, max_retries=4)
    pr_dir = DATA_DIR / "press_releases"

    if legislator_ids:
        files = [pr_dir / f"{leg_id.replace('/', '_')}.json" for leg_id in legislator_ids]
    else:
        files = list(pr_dir.glob("*.json"))

    errors = []
    total_summarized = 0

    for f in files:
        if not f.exists():
            continue
        releases = json.loads(f.read_text())
        changed = False

        for rel in releases:
            if rel.get("ai_summary") is not None:
                continue  # already done
            raw = rel.get("raw_text", "").strip()
            if not raw:
                rel["ai_summary"] = None
                continue

            print(f"    Summarizing: {rel.get('title', '')[:60]}")
            summary = summarize_release(client, raw)
            rel["ai_summary"] = summary
            changed = True
            total_summarized += 1

        if changed:
            f.write_text(json.dumps(releases, indent=2, ensure_ascii=False))

    print(f"  Summarized {total_summarized} new releases")
    return errors


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--legislator-id")
    args = parser.parse_args()
    ids = [args.legislator_id] if args.legislator_id else None
    main(ids)
