"""Validate downloaded images: check for corrupt, truncated, or non-image files."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from tqdm import tqdm


def validate_images(image_dir: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Scan all files in image_dir and verify they are valid images.

    Returns (valid_paths, errors) where errors is a list of (path, reason) tuples.
    """
    valid: list[Path] = []
    errors: list[tuple[Path, str]] = []

    files = sorted(image_dir.rglob("*"))
    files = [f for f in files if f.is_file()]

    for path in tqdm(files, desc="Validating images", unit="img"):
        try:
            with Image.open(path) as img:
                img.verify()
            valid.append(path)
        except Exception as exc:
            errors.append((path, str(exc)))

    return valid, errors


def print_validation_report(valid: list[Path], errors: list[tuple[Path, str]]) -> None:
    """Print a summary of image validation results."""
    total = len(valid) + len(errors)
    print(f"\nImage validation: {len(valid)}/{total} valid")

    if errors:
        print(f"  {len(errors)} broken files:")
        for path, reason in errors[:20]:
            print(f"    {path.relative_to(path.parent.parent)}: {reason}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
