"""
Shared HTTP helper for OpenStates API calls.

Centralizes retry/backoff, rate-limit handling, and tolerant JSON decoding so
every fetch step behaves identically and no single bad response crashes the run.
"""

import json
import time

import requests

MAX_RETRIES = 4
MAX_BACKOFF = 60  # cap a single wait so a failure can't stall the job for minutes


class QuotaExhausted(Exception):
    """Raised when the API keeps returning 429 after all retries — signals the
    caller to stop making requests rather than hammer a rate-limited endpoint.
    Carries any partially-collected results so progress isn't lost."""

    def __init__(self, *args, _partial=None):
        super().__init__(*args)
        self.partial = _partial or []


def _parse_json(resp: requests.Response) -> dict:
    """Parse JSON, tolerating occasional non-UTF-8 bytes instead of crashing.

    The OpenStates API is nominally UTF-8, but a truncated response or stray
    latin-1 byte (e.g. 0xe9) would otherwise raise UnicodeDecodeError and abort
    the whole pipeline. Good responses take the fast path unchanged; only a
    failed decode falls back to lenient replacement.
    """
    try:
        return resp.json()
    except (UnicodeDecodeError, ValueError):
        text = resp.content.decode("utf-8", errors="replace")
        return json.loads(text)


def get_with_backoff(
    url: str,
    headers: dict,
    params: dict,
    timeout: int = 60,
) -> dict:
    """GET with capped exponential backoff, Retry-After support, and tolerant
    JSON decoding. Raises QuotaExhausted if 429s persist, RuntimeError otherwise.
    """
    last_status = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            last_status = resp.status_code
            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                if resp.status_code == 429 and retry_after and retry_after.isdigit():
                    wait = min(int(retry_after), MAX_BACKOFF)
                else:
                    wait = min(2 ** attempt * 5, MAX_BACKOFF)
                print(
                    f"    HTTP {resp.status_code} — waiting {wait}s "
                    f"(retry {attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return _parse_json(resp)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            wait = min(2 ** attempt * 5, MAX_BACKOFF)
            print(f"    Network error — waiting {wait}s (retry {attempt + 1}/{MAX_RETRIES})")
            time.sleep(wait)
    if last_status == 429:
        raise QuotaExhausted(f"Rate limit not clearing after {MAX_RETRIES} retries")
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}")
