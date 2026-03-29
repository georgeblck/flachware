"""Download artwork images from flachware.de with async concurrency and resume support."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx
from tqdm import tqdm

DEFAULT_CONCURRENCY = 5
MAX_RETRIES = 3
RETRY_WAIT = 3.0


async def download_images_async(
    image_urls: list[tuple[str, str]],  # (url, image_id)
    output_dir: Path,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    force: bool = False,
    timeout: float = 30.0,
) -> dict[str, str]:
    """Download images concurrently and return image_id -> sha256 mapping.

    Uses a semaphore to limit concurrent connections.
    Skips images that already exist unless force=True.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    errors: list[str] = []
    cached = 0
    fetched = 0
    sem = asyncio.Semaphore(concurrency)

    # Pre-filter: split into cached and to-download
    to_download: list[tuple[str, str, Path]] = []
    for url, image_id in image_urls:
        artist_slug = image_id.rsplit("_", 1)[0]
        artist_dir = output_dir / artist_slug
        artist_dir.mkdir(exist_ok=True)
        out_path = artist_dir / image_id

        if out_path.exists() and out_path.stat().st_size > 0 and not force:
            checksums[image_id] = _sha256(out_path)
            cached += 1
        else:
            to_download.append((url, image_id, out_path))

    if cached:
        print(f"  {cached} images already cached, {len(to_download)} to download")

    pbar = tqdm(total=len(to_download), desc="Downloading images", unit="img")

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={
            "User-Agent": (
                "flachware-dataset/0.1 "
                "(academic research crawler; "
                "https://github.com/nikolaihuckle/flachware)"
            ),
        },
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=concurrency + 2,
            max_keepalive_connections=concurrency,
        ),
    ) as client:

        async def _fetch_one(url: str, image_id: str, out_path: Path) -> None:
            nonlocal fetched

            # Sanitize URL
            clean_url = url.strip().replace(" ", "%20")
            if (
                not clean_url
                or "\n" in clean_url
                or "\r" in clean_url
                or "<" in clean_url
            ):
                errors.append(f"{image_id}: malformed URL")
                pbar.update(1)
                return

            async with sem:
                for attempt in range(MAX_RETRIES):
                    try:
                        resp = await client.get(clean_url)
                        resp.raise_for_status()

                        if len(resp.content) == 0:
                            raise ValueError("Empty response body")

                        out_path.write_bytes(resp.content)
                        checksums[image_id] = hashlib.sha256(resp.content).hexdigest()
                        fetched += 1
                        pbar.update(1)
                        return
                    except (httpx.TimeoutException, httpx.ConnectError):
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_WAIT * (attempt + 1))
                            continue
                        errors.append(
                            f"{image_id}: timeout after {MAX_RETRIES} retries"
                        )
                    except (httpx.HTTPStatusError, httpx.InvalidURL) as exc:
                        errors.append(f"{image_id}: {exc}")
                        break
                    except (httpx.RequestError, ValueError) as exc:
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_WAIT * (attempt + 1))
                            continue
                        errors.append(f"{image_id}: {exc}")

                pbar.update(1)

        tasks = [_fetch_one(url, iid, out) for url, iid, out in to_download]
        await asyncio.gather(*tasks)

    pbar.close()

    if errors:
        print(f"\n{len(errors)} images failed:")
        for e in errors[:30]:
            print(f"  - {e}")
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more")

    return checksums


def download_images(
    image_urls: list[tuple[str, str]],
    output_dir: Path,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    force: bool = False,
) -> dict[str, str]:
    """Sync wrapper around the async downloader."""
    return asyncio.run(
        download_images_async(
            image_urls,
            output_dir,
            concurrency=concurrency,
            force=force,
        )
    )


def _sha256(path: Path) -> str:
    """Compute SHA-256 checksum for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
