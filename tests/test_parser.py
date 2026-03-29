"""Tests for the HTML parser, focused on class, year, and artwork metadata."""

from flachware.parser import (
    ArtistRecord,
    parse_artist_page,
    parse_index,
)

# ---------------------------------------------------------------------------
# Index parsing
# ---------------------------------------------------------------------------


class TestParseIndex:
    def test_returns_all_artists(self, index_html: str) -> None:
        artists = parse_index(index_html)
        assert len(artists) == 669

    def test_artist_fields(self, index_html: str) -> None:
        artists = parse_index(index_html)
        first = artists[0]
        assert isinstance(first, ArtistRecord)
        assert first.slug == "thomas-wiedemann"
        assert first.name == "Thomas Wiedemann"
        assert first.last_updated == "2021-04-03"

    def test_no_empty_slugs(self, index_html: str) -> None:
        artists = parse_index(index_html)
        assert all(a.slug for a in artists)
        assert all(a.name for a in artists)


# ---------------------------------------------------------------------------
# Artist page: class extraction (the critical field)
# ---------------------------------------------------------------------------


class TestClassExtraction:
    def test_class_from_sidebar_link(self, artist_html_adrine: str) -> None:
        artist, _ = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        assert artist.academy_class == "Kasseböhmer"

    def test_class_huber(self, artist_html_adrian: str) -> None:
        artist, _ = parse_artist_page(artist_html_adrian, "adrian-soelch")
        assert artist.academy_class == "Huber"

    def test_class_zeniuk(self, artist_html_afshin: str) -> None:
        artist, _ = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        assert artist.academy_class == "Zeniuk"

    def test_class_never_none_across_fixtures(
        self, artist_html_adrine: str, artist_html_adrian: str, artist_html_afshin: str
    ) -> None:
        for html, slug in [
            (artist_html_adrine, "adrine-ter-arakelyan"),
            (artist_html_adrian, "adrian-soelch"),
            (artist_html_afshin, "afshin-karimi-fard"),
        ]:
            artist, _ = parse_artist_page(html, slug)
            assert artist.academy_class is not None, f"class is None for {slug}"


# ---------------------------------------------------------------------------
# Artist page: enrollment year
# ---------------------------------------------------------------------------


class TestYearStartExtraction:
    def test_year_2012(self, artist_html_adrine: str) -> None:
        artist, _ = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        assert artist.year_start == 2012

    def test_year_2013(self, artist_html_adrian: str) -> None:
        artist, _ = parse_artist_page(artist_html_adrian, "adrian-soelch")
        assert artist.year_start == 2013

    def test_year_2010(self, artist_html_afshin: str) -> None:
        artist, _ = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        assert artist.year_start == 2010


# ---------------------------------------------------------------------------
# Artwork metadata
# ---------------------------------------------------------------------------


class TestArtworkExtraction:
    def test_artwork_count(self, artist_html_adrine: str) -> None:
        _, artworks = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        assert len(artworks) == 6

    def test_artwork_count_afshin(self, artist_html_afshin: str) -> None:
        _, artworks = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        assert len(artworks) == 19

    def test_image_ids_are_unique(self, artist_html_afshin: str) -> None:
        _, artworks = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        ids = [aw.image_id for aw in artworks]
        assert len(ids) == len(set(ids))

    def test_image_ids_follow_naming(self, artist_html_adrine: str) -> None:
        _, artworks = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        assert artworks[0].image_id == "adrine-ter-arakelyan_001.jpg"
        assert artworks[5].image_id == "adrine-ter-arakelyan_006.jpg"

    def test_all_image_urls_are_flachware(self, artist_html_afshin: str) -> None:
        _, artworks = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        for aw in artworks:
            assert "flachware.de/up/load/" in aw.image_url


# ---------------------------------------------------------------------------
# Artwork year of creation
# ---------------------------------------------------------------------------


class TestArtworkYear:
    def test_year_from_caption(self, artist_html_adrine: str) -> None:
        _, artworks = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        # Second artwork has "2016, oil on canvas, 45x50 cm"
        assert artworks[1].year == 2016

    def test_year_from_afshin(self, artist_html_afshin: str) -> None:
        _, artworks = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        assert artworks[0].year == 2015


# ---------------------------------------------------------------------------
# Artwork medium
# ---------------------------------------------------------------------------


class TestArtworkMedium:
    def test_oil_on_canvas(self, artist_html_adrine: str) -> None:
        _, artworks = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        assert artworks[1].medium is not None
        assert "oil" in artworks[1].medium.lower()
        assert "canvas" in artworks[1].medium.lower()

    def test_acrylic_on_paper(self, artist_html_afshin: str) -> None:
        _, artworks = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        assert artworks[0].medium is not None
        assert "acrylic" in artworks[0].medium.lower()


# ---------------------------------------------------------------------------
# Artwork dimensions
# ---------------------------------------------------------------------------


class TestArtworkDimensions:
    def test_dimensions_parsed(self, artist_html_adrine: str) -> None:
        _, artworks = parse_artist_page(artist_html_adrine, "adrine-ter-arakelyan")
        assert artworks[1].dimensions is not None
        assert "cm" in artworks[1].dimensions

    def test_dimensions_afshin(self, artist_html_afshin: str) -> None:
        _, artworks = parse_artist_page(artist_html_afshin, "afshin-karimi-fard")
        assert artworks[0].dimensions == "100 x 70 cm"
