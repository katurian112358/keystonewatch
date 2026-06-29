"""
Scrape press releases from PA legislator official websites.
Handles the ~3 common PA legislative site templates.
Outputs: data/press_releases/{legislator_id}.json (delta - skips already-scraped)
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from jsonio import read_json, write_json

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; keystonewatch/1.0; "
        "github.com/katurian112358/keystonewatch)"
    )
}
TIMEOUT = 20


# ---------------------------------------------------------------------------
# Site template detectors
# ---------------------------------------------------------------------------

def detect_template(url: str) -> str:
    """Return template key based on URL pattern."""
    if not url:
        return "unknown"
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "legis.state.pa.us" in host:
        return "legis"
    if "pahouse.com" in host or "pahousegop.com" in host:
        return "pahouse"
    if "pasenate.com" in host or "pasenategop.com" in host:
        return "pasenate"
    return "generic"


def scrape_legis(base_url: str) -> list[dict]:
    """legis.state.pa.us - press releases at /cfdocs/legis/pressReleases.cfm"""
    try:
        pr_url = re.sub(r"(legis\.state\.pa\.us/[^/]+).*",
                        r"\1/cfdocs/legis/pressReleases.cfm", base_url)
        resp = requests.get(pr_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        releases = []
        for link in soup.select("a[href*='pressRelease']"):
            href = urljoin(pr_url, link["href"])
            title = link.get_text(strip=True)
            if not title:
                continue
            full_text, date = fetch_release_text(href)
            releases.append({
                "title": title,
                "url": href,
                "date": date,
                "raw_text": full_text,
                "ai_summary": None,
            })
        return releases
    except Exception as e:
        raise RuntimeError(f"legis scrape failed: {e}") from e


def scrape_pahouse(base_url: str) -> list[dict]:
    """
    pahouse.com and pahousegop.com member sites.
    News index is at {base}/InTheNews/ and release links match NewsRelease/?id=
    """
    # Normalize: strip trailing path, keep scheme+host+member-slug
    # e.g. http://www.pahouse.com/merski -> http://www.pahouse.com/merski
    base = base_url.rstrip("/")
    news_url = f"{base}/InTheNews/"

    resp = requests.get(news_url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    seen = set()
    releases = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "NewsRelease" not in href and "PressRelease" not in href:
            continue
        full_url = urljoin(news_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        title = a.get_text(strip=True)
        if not title:
            # Try parent element text
            title = (a.parent or a).get_text(strip=True)[:160]
        full_text, date = fetch_release_text(full_url)
        releases.append({
            "title": title,
            "url": full_url,
            "date": date,
            "raw_text": full_text,
            "ai_summary": None,
        })

    if not releases:
        raise RuntimeError("pahouse scrape: no NewsRelease links found")
    return releases


def scrape_pasenate(base_url: str) -> list[dict]:
    """pasenate.com subdomain - similar structure to pahouse."""
    return scrape_pahouse(base_url)  # same pattern


def scrape_generic(base_url: str) -> list[dict]:
    """Heuristic fallback: look for links containing 'press' or 'news'."""
    resp = requests.get(base_url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Find a news/press index link
    news_link = None
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if any(kw in text for kw in ["press release", "news", "newsroom"]):
            news_link = urljoin(base_url, a["href"])
            break

    if not news_link:
        raise RuntimeError("generic scrape: no news link found")

    resp2 = requests.get(news_link, headers=HEADERS, timeout=TIMEOUT)
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, "lxml")

    releases = []
    for a in soup2.select("a[href]"):
        href = urljoin(news_link, a["href"])
        title = a.get_text(strip=True)
        if len(title) < 10 or href == news_link:
            continue
        full_text, date = fetch_release_text(href)
        releases.append({
            "title": title,
            "url": href,
            "date": date,
            "raw_text": full_text,
            "ai_summary": None,
        })
        if len(releases) >= 20:
            break

    return releases


def fetch_release_text(url: str) -> tuple[str, str | None]:
    """Fetch and extract body text from a single press release page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Try to find date
        date = None
        for selector in ["time", ".date", ".release-date", "span[class*='date']"]:
            el = soup.select_one(selector)
            if el:
                date = el.get("datetime") or el.get_text(strip=True)
                break

        # Extract body text - prefer article/main content areas
        for selector in ["article", "main", ".content", "#content", ".release-body"]:
            el = soup.select_one(selector)
            if el:
                return el.get_text(separator="\n", strip=True), date

        return soup.get_text(separator="\n", strip=True)[:5000], date
    except Exception:
        return "", None


# ---------------------------------------------------------------------------
# Main scrape logic
# ---------------------------------------------------------------------------

SCRAPERS = {
    "legis": scrape_legis,
    "pahouse": scrape_pahouse,
    "pasenate": scrape_pasenate,
    "generic": scrape_generic,
}


def scrape_legislator(leg: dict, existing_urls: set[str]) -> list[dict]:
    web_links = leg.get("web_links", [])
    if not web_links:
        raise RuntimeError("no website URL")

    base_url = web_links[0]
    template = detect_template(base_url)
    scraper = SCRAPERS.get(template, scrape_generic)
    releases = scraper(base_url)

    # Delta: skip URLs already in existing data
    new_releases = [r for r in releases if r["url"] not in existing_urls]
    return new_releases


def main(legislator_ids: list[str] | None = None) -> list[dict]:
    leg_path = DATA_DIR / "legislators.json"
    legislators = read_json(leg_path, [])

    if legislator_ids:
        legislators = [l for l in legislators if l["id"] in legislator_ids]

    pr_dir = DATA_DIR / "press_releases"
    pr_dir.mkdir(parents=True, exist_ok=True)

    # Only this step's errors; the orchestrator owns pipeline_errors.json.
    errors: list[dict] = []

    for i, leg in enumerate(legislators, 1):
        leg_id = leg["id"]
        safe_id = leg_id.replace("/", "_")
        out_path = pr_dir / f"{safe_id}.json"

        print(f"  [{i}/{len(legislators)}] Scraping {leg['name']} ({leg_id})")
        try:
            existing = read_json(out_path, [])
            existing_urls = {r["url"] for r in existing}
            new_releases = scrape_legislator(leg, existing_urls)
            combined = existing + new_releases
            write_json(out_path, combined)
            print(f"    +{len(new_releases)} new releases ({len(combined)} total)")
        except Exception as e:
            msg = str(e)
            print(f"    SKIP: {msg}", file=sys.stderr)
            errors.append({
                "step": "scrape_press_releases",
                "legislator_id": leg_id,
                "error": msg,
                "timestamp": datetime.utcnow().isoformat(),
            })

        # Courtesy delay - many members share pahouse.com / pasenate.com, so pace
        # requests to avoid being rate-limited or IP-blocked by those hosts.
        time.sleep(0.5)

    return errors


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--legislator-id")
    args = parser.parse_args()
    ids = [args.legislator_id] if args.legislator_id else None
    main(ids)
