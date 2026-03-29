"""Crawl flachware.de: fetch the artist index and individual artist pages."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
from tqdm import tqdm

BASE_URL = "https://www.flachware.de"
INDEX_URL = BASE_URL + "/"
DEFAULT_DELAY = 1.0  # seconds between requests
MAX_RETRIES = 3
RETRY_WAIT = 5.0  # seconds before retrying a failed request


def fetch_page(
    client: httpx.Client,
    url: str,
    *,
    encoding: str = "iso-8859-1",
    retries: int = MAX_RETRIES,
) -> str:
    """Fetch a single page and return its HTML as a string.

    Retries on transient errors (timeouts, connection resets).
    """
    for attempt in range(retries):
        try:
            resp = client.get(url)
            resp.encoding = encoding
            resp.raise_for_status()
            result: str = resp.text
            return result
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt < retries - 1:
                time.sleep(RETRY_WAIT * (attempt + 1))
                continue
            raise
    return ""  # unreachable, but keeps the type checker happy


def crawl_index(client: httpx.Client, output_path: Path) -> Path:
    """Download the main artist index page and save it to disk."""
    html = fetch_page(client, INDEX_URL)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def crawl_artist_pages(
    client: httpx.Client,
    slugs: list[str],
    html_dir: Path,
    *,
    delay: float = DEFAULT_DELAY,
    force: bool = False,
) -> list[Path]:
    """Download individual artist HTML pages.

    Skips pages that already exist on disk unless force=True.
    Returns list of paths to all artist HTML files (new and existing).
    """
    html_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    skipped = 0
    fetched = 0
    errors: list[str] = []

    pbar = tqdm(slugs, desc="Fetching artist pages", unit="page")
    for slug in pbar:
        out = html_dir / f"{slug}.html"
        if out.exists() and not force:
            paths.append(out)
            skipped += 1
            pbar.set_postfix(cached=skipped, fetched=fetched, errors=len(errors))
            continue

        url = f"{BASE_URL}/{slug}"
        try:
            html = fetch_page(client, url)
            out.write_text(html, encoding="utf-8")
            paths.append(out)
            fetched += 1
        except httpx.HTTPStatusError as exc:
            msg = f"{slug}: HTTP {exc.response.status_code}"
            errors.append(msg)
            tqdm.write(f"  ERROR {msg}")
        except httpx.RequestError as exc:
            msg = f"{slug}: {exc}"
            errors.append(msg)
            tqdm.write(f"  ERROR {msg}")

        pbar.set_postfix(cached=skipped, fetched=fetched, errors=len(errors))
        time.sleep(delay)

    if errors:
        tqdm.write(f"\n{len(errors)} pages failed:")
        for e in errors:
            tqdm.write(f"  - {e}")

    return paths


def make_client(timeout: float = 30.0) -> httpx.Client:
    """Create an httpx client with polite headers."""
    return httpx.Client(
        timeout=timeout,
        headers={
            "User-Agent": (
                "flachware-dataset/0.1 "
                "(academic research crawler; "
                "https://github.com/nikolaihuckle/flachware)"
            ),
        },
        follow_redirects=True,
    )
