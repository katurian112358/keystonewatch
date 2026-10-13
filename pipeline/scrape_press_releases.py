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
# Pause between individual release fetches. Member sites share hosting and
# return 429 when hit with a burst of page loads.
RELEASE_DELAY = 1.0
# Retries for a release page that returns 429/5xx before giving up for tonight.
RELEASE_RETRIES = 2
MAX_RETRY_WAIT = 30
# Existing releases stored with empty text (from earlier rate-limited fetches)
# are refetched up to this many per run, and abandoned after TEXT_ATTEMPTS_MAX.
TEXT_RETRY_BUDGET = 200
TEXT_ATTEMPTS_MAX = 3


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


def scrape_legis(base_url: str, existing_urls: set[str]) -> list[dict]:
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
            if not title or href in existing_urls:
                continue
            release = make_release(title, href)
            if release:
                releases.append(release)
        return releases
    except Exception as e:
        raise RuntimeError(f"legis scrape failed: {e}") from e


def scrape_pahouse(base_url: str, existing_urls: set[str]) -> list[dict]:
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
        if full_url in existing_urls:
            continue

        title = a.get_text(strip=True)
        if not title:
            # Try parent element text
            title = (a.parent or a).get_text(strip=True)[:160]
        release = make_release(title, full_url)
        if release:
            releases.append(release)

    if not seen:
        raise RuntimeError("pahouse scrape: no NewsRelease links found")
    return releases


def scrape_pasenate(base_url: str, existing_urls: set[str]) -> list[dict]:
    """pasenate.com subdomain - similar structure to pahouse."""
    return scrape_pahouse(base_url, existing_urls)  # same pattern


def scrape_generic(base_url: str, existing_urls: set[str]) -> list[dict]:
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

    # Index pages often link each release twice (headline, then "Continue
    # Reading"); the first link carries the real title.
    seen: set[str] = set()
    releases = []
    for a in soup2.select("a[href]"):
        href = urljoin(news_link, a["href"]).strip()
        title = a.get_text(strip=True)
        if len(title) < 10 or href == news_link or href in seen:
            continue
        # Only the member's own site; skip mailto:, agency pages, partner sites
        if not href.startswith("http") or site_host(href) != site_host(news_link):
            continue
        seen.add(href)
        if href in existing_urls:
            continue
        release = make_release(title, href)
        if release:
            releases.append(release)
        if len(releases) >= 20:
            break

    return releases


def site_host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def make_release(title: str, url: str) -> dict | None:
    """Build a release record, or None if the page couldn't be fetched. A
    skipped release isn't stored, so the next run tries it again."""
    full_text, date = fetch_release_text(url)
    if full_text is None:
        return None
    return {
        "title": title,
        "url": url,
        "date": date,
        "raw_text": full_text,
        "ai_summary": None,
    }


def get_release_page(url: str) -> requests.Response | None:
    """GET with a short backoff on 429/5xx. Member sites share hosting and
    rate-limit bursts; earlier versions stored those failures as empty text."""
    for attempt in range(RELEASE_RETRIES + 1):
        time.sleep(RELEASE_DELAY)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        except requests.RequestException:
            return None
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < RELEASE_RETRIES:
            retry_after = resp.headers.get("Retry-After", "")
            wait = int(retry_after) if retry_after.isdigit() else 5 * 2 ** attempt
            time.sleep(min(wait, MAX_RETRY_WAIT))
            continue
        return resp if resp.ok else None
    return None


def fetch_release_text(url: str) -> tuple[str | None, str | None]:
    """Fetch and extract body text from a single press release page.
    Returns (None, None) if the page couldn't be fetched."""
    resp = get_release_page(url)
    if resp is None:
        return None, None
    try:
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
        return None, None


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
    # Scrapers skip URLs already on file, so known releases aren't re-downloaded
    return scraper(base_url, existing_urls)


def dedupe_releases(releases: list[dict]) -> list[dict]:
    """Collapse repeated URLs, keeping the first entry's title (the second is
    usually a "Continue Reading" link) and any text/summary from later copies."""
    by_url: dict[str, dict] = {}
    for r in releases:
        kept = by_url.get(r["url"])
        if kept is None:
            by_url[r["url"]] = r
            continue
        if not (kept.get("raw_text") or "").strip() and (r.get("raw_text") or "").strip():
            for key in ("raw_text", "date", "ai_summary"):
                kept[key] = r.get(key)
    return list(by_url.values())


def retry_empty_text(releases: list[dict], budget: int) -> int:
    """Refetch text for releases stored empty. Returns how many were tried."""
    tried = 0
    for r in releases:
        if tried >= budget:
            break
        if (r.get("raw_text") or "").strip():
            continue
        if r.get("text_attempts", 0) >= TEXT_ATTEMPTS_MAX:
            continue
        tried += 1
        text, date = fetch_release_text(r["url"])
        if text:
            r["raw_text"] = text
            r["date"] = r.get("date") or date
            r["ai_summary"] = None  # summarize step picks it up
            r.pop("text_attempts", None)
        else:
            r["text_attempts"] = r.get("text_attempts", 0) + 1
    return tried


def main(legislator_ids: list[str] | None = None) -> list[dict]:
    leg_path = DATA_DIR / "legislators.json"
    legislators = read_json(leg_path, [])

    if legislator_ids:
        legislators = [l for l in legislators if l["id"] in legislator_ids]

    pr_dir = DATA_DIR / "press_releases"
    pr_dir.mkdir(parents=True, exist_ok=True)

    # Only this step's errors; the orchestrator owns pipeline_errors.json.
    errors: list[dict] = []
    retry_budget = TEXT_RETRY_BUDGET

    for i, leg in enumerate(legislators, 1):
        leg_id = leg["id"]
        safe_id = leg_id.replace("/", "_")
        out_path = pr_dir / f"{safe_id}.json"

        print(f"  [{i}/{len(legislators)}] Scraping {leg['name']} ({leg_id})")
        try:
            existing = dedupe_releases(read_json(out_path, []))
            retry_budget -= retry_empty_text(existing, retry_budget)
            existing_urls = {r["url"] for r in existing}
            try:
                new_releases = scrape_legislator(leg, existing_urls)
            except Exception:
                # Keep dedupe/refetch progress even if the index scrape fails
                if existing:
                    write_json(out_path, existing)
                raise
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
