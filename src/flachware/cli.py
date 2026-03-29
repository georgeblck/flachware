"""CLI entrypoint for the flachware dataset pipeline."""

from __future__ import annotations

from pathlib import Path

import click

from flachware.crawler import crawl_artist_pages, crawl_index, make_client
from flachware.downloader import download_images
from flachware.export import (
    artists_to_dataframe,
    artworks_to_dataframe,
    export_dataset,
    print_summary,
)
from flachware.parser import parse_artist_page, parse_index

DEFAULT_DATA_DIR = Path("data")


@click.group()
def main() -> None:
    """Flachware dataset: crawl, parse, and export art metadata from flachware.de."""


@main.command()
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
@click.option("--delay", type=float, default=1.0, help="Seconds between requests.")
@click.option("--force", is_flag=True, help="Re-download pages that already exist.")
def crawl(data_dir: Path, delay: float, force: bool) -> None:
    """Fetch the artist index and all artist profile pages."""
    index_path = data_dir / "raw_html" / "index.html"
    html_dir = data_dir / "raw_html" / "artists"

    client = make_client()

    click.echo("Fetching artist index...")
    crawl_index(client, index_path)

    html = index_path.read_text(encoding="utf-8")
    artists = parse_index(html)
    slugs = [a.slug for a in artists]
    click.echo(f"Found {len(slugs)} artists.")

    click.echo("Fetching individual artist pages...")
    crawl_artist_pages(client, slugs, html_dir, delay=delay, force=force)

    client.close()
    click.echo("Done crawling.")


@main.command()
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
def parse(data_dir: Path) -> None:
    """Parse cached HTML files and export metadata CSV/Parquet."""
    index_path = data_dir / "raw_html" / "index.html"
    html_dir = data_dir / "raw_html" / "artists"

    if not index_path.exists():
        click.echo("No cached index found. Run 'flachware crawl' first.", err=True)
        raise SystemExit(1)

    click.echo("Parsing index...")
    index_html = index_path.read_text(encoding="utf-8")
    index_artists = parse_index(index_html)
    slugs = [a.slug for a in index_artists]

    click.echo(f"Parsing {len(slugs)} artist pages...")
    all_artists = []
    all_artworks = []

    for slug in slugs:
        artist_html_path = html_dir / f"{slug}.html"
        if not artist_html_path.exists():
            continue
        html = artist_html_path.read_text(encoding="utf-8")
        artist, artworks = parse_artist_page(html, slug)
        all_artists.append(artist)
        all_artworks.extend(artworks)

    artists_df = artists_to_dataframe(all_artists)
    artworks_df = artworks_to_dataframe(all_artworks)

    export_dataset(artists_df, artworks_df, data_dir)
    print_summary(artists_df, artworks_df)


@main.command()
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
@click.option(
    "--concurrency", type=int, default=5, help="Number of concurrent downloads."
)
@click.option("--force", is_flag=True, help="Re-download images that already exist.")
def download(data_dir: Path, concurrency: int, force: bool) -> None:
    """Download artwork images based on parsed metadata."""
    artworks_csv = data_dir / "artworks.csv"
    if not artworks_csv.exists():
        click.echo("No artworks.csv found. Run 'flachware parse' first.", err=True)
        raise SystemExit(1)

    import polars as pl

    artworks = pl.read_csv(artworks_csv)
    image_pairs = list(
        zip(
            artworks["image_url"].to_list(),
            artworks["image_id"].to_list(),
            strict=True,
        )
    )

    click.echo(f"Downloading {len(image_pairs)} images ({concurrency} concurrent)...")
    checksums = download_images(
        image_pairs, data_dir / "images", concurrency=concurrency, force=force
    )

    # Update artworks with checksums and re-export
    checksum_series = artworks["image_id"].map_elements(
        lambda x: checksums.get(x), return_dtype=pl.Utf8
    )
    artworks = artworks.with_columns(checksum_series.alias("sha256"))
    artworks.write_csv(artworks_csv)
    artworks.write_parquet(data_dir / "artworks.parquet")

    click.echo(f"Done. {len(checksums)} images saved.")


@main.command()
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
@click.option("--delay", type=float, default=1.0, help="Delay for page fetches.")
@click.option("--concurrency", type=int, default=5, help="Concurrent image downloads.")
@click.option("--force", is_flag=True, help="Re-download everything.")
@click.option("--skip-images", is_flag=True, help="Skip image downloads.")
def run(
    data_dir: Path,
    delay: float,
    concurrency: int,
    force: bool,
    skip_images: bool,
) -> None:
    """Run the full pipeline: crawl, parse, and download."""

    ctx = click.get_current_context()

    ctx.invoke(crawl, data_dir=data_dir, delay=delay, force=force)
    ctx.invoke(parse, data_dir=data_dir)
    if not skip_images:
        ctx.invoke(download, data_dir=data_dir, concurrency=concurrency, force=force)

    click.echo("\nPipeline complete.")


@main.command()
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
def validate(data_dir: Path) -> None:
    """Validate that all downloaded images are intact."""
    from flachware.validate import print_validation_report, validate_images

    image_dir = data_dir / "images"
    if not image_dir.exists():
        click.echo(
            "No images directory found. Run 'flachware download' first.", err=True
        )
        raise SystemExit(1)

    valid, errors = validate_images(image_dir)
    print_validation_report(valid, errors)


@main.command()
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR)
def classify(data_dir: Path) -> None:
    """Classify images as art vs noise using CLIP and add is_art column."""
    try:
        from flachware.classify import classify_images
    except ImportError as exc:
        click.echo(
            "Classification requires torch + transformers.\n"
            "Install with: uv sync --group analysis",
            err=True,
        )
        raise SystemExit(1) from exc

    import polars as pl

    artworks_csv = data_dir / "artworks.csv"
    image_dir = data_dir / "images"
    if not artworks_csv.exists() or not image_dir.exists():
        click.echo(
            "Need artworks.csv and images. Run 'flachware parse' and 'flachware download' first.",
            err=True,
        )
        raise SystemExit(1)

    artworks = pl.read_csv(artworks_csv)

    # Build list of image paths in CSV order
    paths = []
    valid_mask = []
    for row in artworks.iter_rows(named=True):
        p = image_dir / row["artist_slug"] / row["image_id"]
        if p.exists() and p.stat().st_size > 100:
            paths.append(p)
            valid_mask.append(True)
        else:
            valid_mask.append(False)

    click.echo(f"Classifying {len(paths)} images with CLIP...")
    art_scores = classify_images(paths)

    # Map back to full dataframe
    score_iter = iter(art_scores)
    score_values: list[float | None] = [
        round(float(next(score_iter)), 3) if valid else None for valid in valid_mask
    ]
    is_art_values = [(s > 0.5) if s is not None else None for s in score_values]
    artworks = artworks.with_columns(
        pl.Series("art_score", score_values, dtype=pl.Float64),
        pl.Series("is_art", is_art_values, dtype=pl.Boolean),
    )
    artworks.write_csv(artworks_csv)

    n_art = sum(1 for v in is_art_values if v is True)
    n_noise = sum(1 for v in is_art_values if v is False)
    click.echo(
        f"Done. {n_art} art, {n_noise} noise, {sum(1 for v in is_art_values if v is None)} unclassified."
    )
