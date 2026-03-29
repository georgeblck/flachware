"""Export parsed metadata to CSV and Parquet."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from flachware.parser import ArtistRecord, ArtworkRecord

_ARTISTS_SCHEMA = {
    "slug": pl.Utf8,
    "name": pl.Utf8,
    "academy_class": pl.Utf8,
    "year_start": pl.Int32,
    "last_updated": pl.Utf8,
    "website": pl.Utf8,
    "birth_info": pl.Utf8,
}

_ARTWORKS_SCHEMA = {
    "artist_slug": pl.Utf8,
    "image_id": pl.Utf8,
    "image_url": pl.Utf8,
    "title": pl.Utf8,
    "year": pl.Int32,
    "medium": pl.Utf8,
    "dimensions": pl.Utf8,
    "caption_raw": pl.Utf8,
    "sha256": pl.Utf8,
    "art_score": pl.Float64,
    "is_art": pl.Boolean,
}


def artists_to_dataframe(records: list[ArtistRecord]) -> pl.DataFrame:
    """Convert artist records to a Polars DataFrame."""
    return pl.DataFrame(
        [
            {
                "slug": r.slug,
                "name": r.name,
                "academy_class": r.academy_class,
                "year_start": r.year_start,
                "last_updated": r.last_updated,
                "website": r.website,
                "birth_info": r.birth_info,
            }
            for r in records
        ],
        schema=_ARTISTS_SCHEMA,
    )


def artworks_to_dataframe(
    records: list[ArtworkRecord],
    checksums: dict[str, str] | None = None,
) -> pl.DataFrame:
    """Convert artwork records to a Polars DataFrame."""
    checksums = checksums or {}
    return pl.DataFrame(
        [
            {
                "artist_slug": r.artist_slug,
                "image_id": r.image_id,
                "image_url": r.image_url,
                "title": r.title,
                "year": r.year,
                "medium": r.medium,
                "dimensions": r.dimensions,
                "caption_raw": r.caption_raw,
                "sha256": checksums.get(r.image_id),
            }
            for r in records
        ],
        schema=_ARTWORKS_SCHEMA,
    )


def export_dataset(
    artists: pl.DataFrame,
    artworks: pl.DataFrame,
    output_dir: Path,
) -> None:
    """Write CSV and Parquet files for both tables."""
    output_dir.mkdir(parents=True, exist_ok=True)

    artists.write_csv(output_dir / "artists.csv")
    artists.write_parquet(output_dir / "artists.parquet")

    artworks.write_csv(output_dir / "artworks.csv")
    artworks.write_parquet(output_dir / "artworks.parquet")


def print_summary(artists: pl.DataFrame, artworks: pl.DataFrame) -> None:
    """Print a summary of the dataset."""
    n_artists = len(artists)
    n_artworks = len(artworks)
    n_with_title = artworks.filter(pl.col("title").is_not_null()).height
    n_with_medium = artworks.filter(pl.col("medium").is_not_null()).height
    n_with_dims = artworks.filter(pl.col("dimensions").is_not_null()).height
    n_with_year = artworks.filter(pl.col("year").is_not_null()).height
    n_classes = artists.filter(pl.col("academy_class").is_not_null()).n_unique(
        subset=["academy_class"]
    )

    print("\nDataset summary:")
    print(f"  Artists:    {n_artists}")
    print(f"  Artworks:   {n_artworks}")
    print(f"  Classes:    {n_classes}")
    print(
        f"  With title: {n_with_title} ({100 * n_with_title / max(n_artworks, 1):.0f}%)"
    )
    print(
        f"  With year:  {n_with_year} ({100 * n_with_year / max(n_artworks, 1):.0f}%)"
    )
    print(
        f"  With medium:{n_with_medium} ({100 * n_with_medium / max(n_artworks, 1):.0f}%)"
    )
    print(
        f"  With dims:  {n_with_dims} ({100 * n_with_dims / max(n_artworks, 1):.0f}%)"
    )
