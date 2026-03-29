# Datasheet: Flachware Dataset

Following the framework proposed by Gebru et al. (2021),
"Datasheets for Datasets" (Communications of the ACM, 64(12), 86-92).

## Motivation

**Purpose.** This dataset was created to support computational art analysis
research. It provides structured metadata and artwork images from a single
art school, enabling studies on artistic style, medium use, class/mentorship
effects, and temporal trends in contemporary art education.

**Creators.** Nikolai Huckle. The initial crawl was performed in 2021, with
a full refresh in 2026.

**Funding.** No external funding. This is an independent research project.

## Composition

**Instances.** Each instance is an artwork image uploaded by a student or
alumnus of the Academy of Fine Arts Munich (Akademie der Bildenden Kuenste
Muenchen) to the platform flachware.de.

**Count.** Approximately 670 artists and 12,000 artwork images (as of
March 2026). The exact count depends on the crawl date.

**Data per instance.**
- Image file (JPEG, variable resolution, typically 420px wide)
- Artist name and URL slug
- Academy class (professor name)
- Year of enrollment
- Artwork title (where available, ~54%)
- Year of creation (where available, ~42%)
- Medium/technique in German or English (where available, ~30%)
- Dimensions in cm (where available, ~18%)
- Raw caption text (unprocessed)

**Missing data.** Artwork-level metadata (title, year, medium, dimensions)
is extracted from free-form captions that artists write themselves. Coverage
varies because there is no enforced format on flachware.de. Some artists
provide detailed structured captions, others provide only images with no
text.

**Confidentiality.** All data is publicly available on flachware.de. Email
addresses visible on the site are not included in this dataset.

## Collection Process

**Source.** All data was collected from https://www.flachware.de by crawling
the public website.

**Mechanism.** A Python-based crawler fetches the main artist index page,
then each individual artist profile page. Metadata is extracted from HTML
using CSS selectors and regular expressions. Images are downloaded from
the URLs embedded in artist pages.

**Time frame.** The original crawl was performed in April 2021. A full
refresh was performed in March 2026. The site has been active since
November 2006.

**Consent.** Artists voluntarily upload their work and biographical
information to flachware.de, a public platform. This dataset is provided
for non-commercial research under German copyright law (Section 60d UrhG,
scientific research; Section 44b UrhG, text and data mining).

## Preprocessing

**Metadata extraction.** Artist-level metadata (name, class, enrollment
year) is extracted from structured HTML elements in the page sidebar. These
fields have near-100% coverage. Artwork-level metadata is parsed from
unstructured caption text following each image, using pattern matching for
years, dimensions, and medium keywords.

**Image processing.** Images are downloaded as-is from flachware.de with no
resizing, cropping, or color correction. SHA-256 checksums are computed for
integrity verification.

**Raw data.** The original HTML pages are preserved in `data/raw_html/` so
the parsing step can be re-run with improved logic without re-crawling.

## Uses

**Intended uses.**
- Computational art analysis (style classification, similarity, clustering)
- Studying the influence of academy classes/professors on student work
- Temporal analysis of medium and style trends
- Training or evaluating computer vision models on contemporary art

**Unintended uses.** This dataset should not be used for commercial
purposes, to train commercial generative models, or to create derivative
works that compete with the original artists.

## Distribution

**License.** Code is MIT-licensed. Images remain under the copyright of
their respective artists and are provided for non-commercial research only.
See the LICENSE file for full terms.

**Access.** The dataset can be reproduced from scratch using the provided
crawler. Run `uv run flachware run` to generate it.

## Maintenance

**Updates.** The crawler can be re-run at any time to capture new artists
and updated profiles. The site is actively maintained (most recent update:
March 2026).

**Contact.** Nikolai Huckle.

**Errata.** Known limitations: artwork metadata coverage depends on artist
formatting choices. The parser may miss or misparse unusual caption formats.
