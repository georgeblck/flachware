"""Parse flachware.de HTML pages to extract artist and artwork metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selectolax.parser import HTMLParser

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ArtistRecord:
    slug: str
    name: str
    last_updated: str  # ISO date string YYYY-MM-DD
    academy_class: str | None = None
    year_start: int | None = None
    website: str | None = None
    birth_info: str | None = None


@dataclass
class ArtworkRecord:
    artist_slug: str
    image_url: str
    image_id: str  # e.g. "abir-kobeissi_001.jpg"
    caption_raw: str | None = None
    title: str | None = None
    year: int | None = None
    medium: str | None = None
    dimensions: str | None = None


# ---------------------------------------------------------------------------
# Index page parsing
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def parse_index(html: str) -> list[ArtistRecord]:
    """Parse the main index page and return a list of ArtistRecords
    with slug, name, and last_updated filled in."""
    tree = HTMLParser(html)
    records: list[ArtistRecord] = []

    for link in tree.css("a.grau"):
        href = (link.attributes.get("href") or "").strip().rstrip("/")
        name = link.text(strip=True)
        if not href or not name:
            continue

        parent = link.parent
        date_str = ""
        if parent:
            span = parent.css_first("span.hellgrau-klein")
            if span:
                m = _DATE_RE.search(span.text())
                if m:
                    date_str = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

        records.append(ArtistRecord(slug=href, name=name, last_updated=date_str))

    return records


# ---------------------------------------------------------------------------
# Artist page parsing: class + enrollment year (the critical fields)
# ---------------------------------------------------------------------------

_KLASSE_META_RE = re.compile(r"Klasse\s+([^,]+)", re.IGNORECASE)


def _extract_academy_class(tree: HTMLParser, html: str) -> str | None:
    """Extract academy class (professor name) with multiple fallbacks.

    Strategy (in priority order):
      1. Sidebar link: <a href="../klasse-X">Name</a>
      2. Meta keywords tag: "Klasse X" in content attribute
      3. Raw text search for "Klasse " in sidebar area
    """
    # Strategy 1: sidebar link (most reliable, gives clean name)
    for a in tree.css("a"):
        href = a.attributes.get("href") or ""
        if "klasse-" in href:
            text: str = a.text(strip=True)
            if text:
                return text

    # Strategy 2: meta keywords
    meta = tree.css_first('meta[name="Keywords"]')
    if meta:
        content = meta.attributes.get("content") or ""
        m = _KLASSE_META_RE.search(content)
        if m:
            return m.group(1).strip()

    # Strategy 3: meta description (same format)
    meta_desc = tree.css_first('meta[name="Description"]')
    if meta_desc:
        content = meta_desc.attributes.get("content") or ""
        m = _KLASSE_META_RE.search(content)
        if m:
            return m.group(1).strip()

    return None


def _extract_year_start(tree: HTMLParser) -> int | None:
    """Extract enrollment year from sidebar.

    The pattern is always: <strong>ab YYYY</strong> in the sidebar.
    We also check surrounding text for "ab" to avoid false positives.
    """
    for strong in tree.css("strong"):
        text = strong.text(strip=True)
        m = re.search(r"\b((?:19|20)\d{2})\b", text)
        if not m:
            continue
        # Check that "ab" precedes the year (either inside the <strong> or just before it)
        parent_text = strong.parent.text() if strong.parent else text
        if "ab" in parent_text.lower():
            return int(m.group(1))

    return None


def _extract_last_updated(tree: HTMLParser) -> str:
    """Extract the 'Letzte Aktualisierung' date from the sidebar."""
    for a in tree.css("a"):
        href = a.attributes.get("href") or ""
        if href in ("../", "/"):
            text = a.text(strip=True)
            dm = _DATE_RE.search(text)
            if dm:
                return f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
    return ""


# ---------------------------------------------------------------------------
# Caption / artwork metadata parsing
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_YEAR_RANGE_RE = re.compile(r"\b((?:19|20)\d{2})\s*/\s*(\d{2,4})\b")
_DIMENSIONS_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[xX\N{MULTIPLICATION SIGN}]\s*(\d+(?:[.,]\d+)?)"
    r"(?:\s*[xX\N{MULTIPLICATION SIGN}]\s*(\d+(?:[.,]\d+)?))?"
    r"\s*cm",
    re.IGNORECASE,
)

_MEDIUM_KEYWORDS = [
    "öl",
    "oel",
    "oil",
    "acryl",
    "acrylic",
    "tempera",
    "eitempera",
    "aquarell",
    "watercolor",
    "watercolour",
    "gouache",
    "tusche",
    "ink",
    "bleistift",
    "pencil",
    "graphit",
    "graphite",
    "kohle",
    "charcoal",
    "leinwand",
    "canvas",
    "papier",
    "paper",
    "holz",
    "wood",
    "mdf",
    "fotografie",
    "photography",
    "photo",
    "pigment",
    "spray",
    "mischtechnik",
    "mixed media",
    "siebdruck",
    "screen print",
    "lithografie",
    "lithography",
    "bronze",
    "gips",
    "plaster",
    "stahl",
    "steel",
    "aluminium",
    "video",
    "film",
    "installation",
    "keramik",
    "ceramic",
    "textil",
    "textile",
    "stoff",
    "karton",
    "cardboard",
    "kupfer",
    "copper",
    "lack",
    "lacquer",
    "beton",
    "concrete",
    "harz",
    "resin",
    "epoxy",
    "pappe",
    "ton",
    "clay",
    "glas",
    "glass",
    "neon",
    "digital",
]

_MEDIUM_KW_SET = {kw.lower() for kw in _MEDIUM_KEYWORDS}

_MEDIUM_PATTERN = re.compile(
    r"(?:^|[,;/\s])("
    + "|".join(re.escape(kw) for kw in _MEDIUM_KEYWORDS)
    + r")"
    + r"(?:\s+(?:auf|on|und|and|/)\s+(?:"
    + "|".join(re.escape(kw) for kw in _MEDIUM_KEYWORDS)
    + r"))*",
    re.IGNORECASE,
)


def _extract_year_from_caption(caption: str) -> int | None:
    """Extract artwork creation year from caption text.

    Handles formats like:
      - "Title, 2019, oil on canvas"
      - "2016, oil on canvas, 45x50cm"
      - "Eremitage, 2004/05"
      - "Title, medium, 100x80 cm, 2020"
    """
    # First check for year ranges like "2004/05"
    range_match = _YEAR_RANGE_RE.search(caption)
    if range_match:
        return int(range_match.group(1))

    # Find all standalone 4-digit years
    years = [int(y) for y in _YEAR_RE.findall(caption) if 1950 <= int(y) <= 2030]
    if not years:
        return None

    # If there's only one year, use it
    if len(years) == 1:
        return years[0]

    # Multiple years: prefer the one that looks like a creation year.
    # Dimensions can contain year-like numbers (e.g. "2010" in "201x150cm")
    # so filter out numbers that are part of dimension strings.
    dims_span = _DIMENSIONS_RE.search(caption)
    filtered = []
    for y_match in _YEAR_RE.finditer(caption):
        y_val = int(y_match.group(1))
        if y_val < 1950 or y_val > 2030:
            continue
        # Skip if this match falls inside a dimension pattern
        if dims_span and dims_span.start() <= y_match.start() <= dims_span.end():
            continue
        filtered.append(y_val)

    if filtered:
        return filtered[-1]
    return years[-1]


def _extract_caption_fields(
    caption: str,
) -> tuple[str | None, int | None, str | None, str | None]:
    """Extract title, year, medium, and dimensions from a caption string."""
    title = None
    year = _extract_year_from_caption(caption)
    medium = None
    dimensions = None

    # Dimensions
    dim_match = _DIMENSIONS_RE.search(caption)
    if dim_match:
        dimensions = dim_match.group(0).strip()

    # Medium
    medium_match = _MEDIUM_PATTERN.search(caption.lower())
    if medium_match:
        start = medium_match.start()
        rest = caption[start:].strip().lstrip(",; ")
        end_match = re.search(r"[,\n]|\d+\s*[xX\N{MULTIPLICATION SIGN}]", rest)
        if end_match:
            medium = rest[: end_match.start()].strip().rstrip(",;. ")
        else:
            medium = rest.strip().rstrip(",;. ")
        if medium:
            medium = medium[:120]

    # Title: text before the first year, medium keyword, or dimension.
    # Common pattern: "Title, Year, medium, dimensions"
    parts = re.split(r",\s*", caption, maxsplit=1)
    candidate = parts[0].strip().rstrip(",;. ")
    if (
        candidate
        and not re.match(r"^\d{4}$", candidate)
        and len(candidate) > 1
        and not _MEDIUM_PATTERN.match(candidate.lower())
    ):
        title = candidate[:200]

    return title, year, medium, dimensions


# ---------------------------------------------------------------------------
# Full artist page parser
# ---------------------------------------------------------------------------


def parse_artist_page(html: str, slug: str) -> tuple[ArtistRecord, list[ArtworkRecord]]:
    """Parse a single artist page.

    Returns an ArtistRecord (with sidebar metadata) and a list of ArtworkRecords.
    """
    tree = HTMLParser(html)

    # -- Artist name --
    name = slug.replace("-", " ").title()
    name_node = tree.css_first("span.hellgrau-big strong")
    if name_node:
        name = name_node.text(strip=True)

    # -- Critical metadata: class + enrollment year --
    academy_class = _extract_academy_class(tree, html)
    year_start = _extract_year_start(tree)
    last_updated = _extract_last_updated(tree)

    # -- Optional metadata --
    website = None
    birth_info = None

    for a in tree.css("a"):
        href = a.attributes.get("href") or ""
        if (
            href.startswith("http")
            and "flachware" not in href
            and "facebook" not in href
            and "pinterest" not in href
        ):
            website = href
            break

    content_match = re.search(r"<!--anf2-->(.*?)<!--ende2-->", html, re.DOTALL)
    if content_match:
        content_text = HTMLParser(content_match.group(1)).text()
        birth_match = re.search(r"\(\*\s*(\d{4}[^)]*)\)", content_text)
        if birth_match:
            birth_info = birth_match.group(1).strip()

    artist = ArtistRecord(
        slug=slug,
        name=name,
        last_updated=last_updated,
        academy_class=academy_class,
        year_start=year_start,
        website=website,
        birth_info=birth_info,
    )

    # -- Artwork images --
    artworks: list[ArtworkRecord] = []
    img_counter = 0

    for img in tree.css("img"):
        src = img.attributes.get("src") or ""
        if "flachware.de/up/load/" not in src:
            continue

        img_counter += 1
        ext = Path(src).suffix or ".jpg"
        image_id = f"{slug}_{img_counter:03d}{ext}"

        caption_raw = _extract_following_text(img)

        title, year, medium, dimensions = (None, None, None, None)
        if caption_raw:
            title, year, medium, dimensions = _extract_caption_fields(caption_raw)

        artworks.append(
            ArtworkRecord(
                artist_slug=slug,
                image_url=src,
                image_id=image_id,
                caption_raw=caption_raw,
                title=title,
                year=year,
                medium=medium,
                dimensions=dimensions,
            )
        )

    return artist, artworks


def _extract_following_text(img_node: Any) -> str | None:
    """Extract text that follows an <img> tag until the next <img> or block element."""
    texts = []
    node = img_node.next
    while node is not None:
        if node.tag == "img":
            break
        if node.tag in ("-text", "br"):
            if node.tag == "-text":
                t = node.text(strip=True)
                if t and t != ".":
                    texts.append(t)
        elif node.tag in ("a", "strong", "em", "span", "b", "i"):
            t = node.text(strip=True)
            if t and t != ".":
                texts.append(t)
        else:
            if node.tag in ("table", "div", "p", "hr", "iframe"):
                break
            t = node.text(strip=True)
            if t and t != ".":
                texts.append(t)
        node = node.next

    result = " ".join(texts).strip()
    result = re.sub(r"[\s.]{3,}", " ", result)
    result = result.strip(" .")
    return result if result else None
