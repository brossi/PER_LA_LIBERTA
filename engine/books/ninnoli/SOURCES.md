# Ninnoli spike resources

**Acquired:** 2026-07-12
**Book:** Gerolamo Rovetta, *Ninnoli*
**Spike posture:** new-book production input; no downstream artifact is frozen or seeded.

## Production witnesses

| Role | Edition / holding | Scan | IA OCR | Local scan | Local OCR |
|---|---|---|---|---|---|
| `copy1` / primary scan | Third edition, Rome: A. Sommaruga, 1884; University of Toronto | [IA item](https://archive.org/details/ninnolir00roveuoft) | [DjVu text](https://archive.org/download/ninnolir00roveuoft/ninnolir00roveuoft_djvu.txt) | `scans/ninnolir00roveuoft.pdf` (110 pages) | `sources/ninnolir00roveuoft_djvu.{txt,xml}` |
| `copy2` / qualified secondary | Rome: A. Sommaruga, 1883; Google digitization | [IA item](https://archive.org/details/ninnoli00rovegoog) | [DjVu text](https://archive.org/download/ninnoli00rovegoog/ninnoli00rovegoog_djvu.txt) | `scans/ninnoli00rovegoog.pdf` (166 pages) | `sources/ninnoli00rovegoog_djvu.{txt,xml}` |

The witnesses are adjacent editions, not two copies of one impression. They may not participate as equal reconciliation witnesses until an edition-difference preflight distinguishes OCR disagreement from editorial change. The primary production scan is the 1884 third edition named by `manifest.json`.

The OCR sizes are close enough to justify that preflight:

- 1884 IA OCR: 25,439 whitespace-delimited words / 176,012 bytes.
- 1883 IA OCR: 26,657 words / 160,163 bytes (includes Google wrapper matter).

The XML derivatives are retained for page/word geometry. The IA metadata snapshots and page/scandata derivatives are acquisition evidence, not pipeline text inputs.

## Sealed evaluation reference

Project Gutenberg ebook [#28231](https://www.gutenberg.org/ebooks/28231) is stored under `evaluation/` as UTF-8 text and HTML. Gutenberg reports that it was human-produced from Internet Archive images.

**Rule:** neither evaluation file may seed a manifest field beyond public bibliographic facts, a structure map, OCR correction, cleanup cache, prompt, or translation. It remains unread by the production run until the corresponding output is complete and hashed. It is a held-out evaluator, not a third witness.

The reference contains 26,138 whitespace-delimited words / 169,544 bytes. It is not an independent physical witness and no English reference translation has been acquired.

## Provisional hypotheses (not rulings)

- The book is a flat collection of five titled prose stories, with no part level.
- `italian_1900_1922` and `bodoni_didone` are starting profiles only; the run must expose where the 1880s text or scan differs.
- `leaf_offset = 0`, `running_heads = []`, and the structural counts in `manifest.json` are acquisition placeholders to be verified before the first run.
- The 1883 witness may be demoted or restricted by span if the edition preflight finds substantive revision.

All downloaded resources are ignored by Git. `resources.sha256` pins the exact local acquisition used by the spike.
