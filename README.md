# LawCodex — Canada (`ca`)

Canadian **federal** legislation as plain Markdown, in both official languages (English and French):
the Constitution Acts 1867 to 1982, every consolidated federal Act and every consolidated federal
regulation published by the Department of Justice on the Justice Laws Website.

Part of [LawCodex](https://github.com/LawCodex): the legislation of every country as Markdown in git.

Retrieved: **2026-10-11** (Justice Laws XML snapshot of 2026-09-28, commit `b7292cf` of
`justicecanada/laws-lois-xml`; Constitution page last modified 2026-09-28).

## Contents

| Category | English | French | Notes |
|---|---:|---:|---|
| Constitution (`constitution/`) | 3 | 3 | Constitution Act, 1867; Canada Act 1982; Constitution Act, 1982 (incl. the Charter) |
| Acts (`en/acts/`, `fr/lois/`) | 971 | 971 | 894 in force, 76 repealed, 1 status unknown |
| Regulations (`en/regulations/`, `fr/reglements/`) | 4,892 | 4,892 | see below |
| **Total** | **5,866** | **5,866** | **11,732 files** |

Regulations by instrument type:

| Type | English dir | French dir | Files (per language) | In force | Repealed | Unknown |
|---|---|---|---:|---:|---:|---:|
| SOR / DORS — Statutory Orders and Regulations | `sor/<year>/` | `dors/<year>/` | 3,070 | 2,401 | 652 | 17 |
| SI / TR — Statutory Instruments (other than regulations) | `si/<year>/` | `tr/<year>/` | 1,251 | 1,033 | 216 | 2 |
| C.R.C. — Consolidated Regulations of Canada, 1978 | `crc/` | `crc/` | 571 | 463 | 107 | 1 |

(French counts differ by one between DORS/TR in-force/unknown because the lookup tables differ slightly
between languages.)

Status (`status:` in front matter) comes from the official lookup tables: `in_force` if the law is
listed in `lookup.xml` (current laws), `repealed` if it is only listed in `lookupfull.xml` (which
includes repealed laws), `unknown` otherwise. Repealed laws are kept because the official XML
repository still publishes their last consolidated text (often just a "[Repealed, …]" line).

## Structure

```
en/constitution/constitution-act-1867.md     fr/constitution/constitution-act-1867.md
en/constitution/canada-act-1982.md           fr/constitution/canada-act-1982.md
en/constitution/constitution-act-1982.md     fr/constitution/constitution-act-1982.md
en/acts/<chapter>.md                         fr/lois/<chapter>.md
en/regulations/sor/<year>/sor-<yy>-<n>.md    fr/reglements/dors/<year>/dors-<yy>-<n>.md
en/regulations/si/<year>/si-<yy>-<n>.md      fr/reglements/tr/<year>/tr-<yy>-<n>.md
en/regulations/crc/crc-c-<n>.md              fr/reglements/crc/crc-ch-<n>.md
```

- Acts are named after their consolidated chapter number (the stable identifier used by Justice
  Laws), lowercased with `.` → `-`: `C-46` (Criminal Code) → `c-46.md`, `I-3.3` (Income Tax Act) →
  `i-3-3.md`, `A-0.6` → `a-0-6.md`. The same file name is used in `en/acts/` and `fr/lois/`.
- Regulations are named after their registration number: `SOR/2017-109` →
  `regulations/sor/2017/sor-2017-109.md`, `DORS/2017-109` → `reglements/dors/2017/dors-2017-109.md`,
  `C.R.C., c. 870` → `crc-c-870.md` / `crc-ch-870.md`. Two-digit years (before 2000) keep their
  official form in the file name (`sor-97-175.md`) and are filed under the four-digit year directory.
- Each file has YAML front matter (`title`, `identifier`, `citation` (acts, when different),
  `long_title`, `type`, `jurisdiction`, `language`, `date` (royal assent for acts / registration date
  for regulations, when known), `last_amended`, `consolidated` (consolidation date), `status`,
  `enabling_authority` (regulations), `source`, `retrieved`).
- Inside a file: Parts/Divisions/Subdivisions (`Heading level=n` in the XML) become `##`…`#####`
  headings; each section is a heading `Section N — <marginal note>` (`Article N — …` in French);
  subsections are `**(1)**` paragraphs preceded by their italic marginal note; paragraphs,
  subparagraphs, clauses… are nested lists. Historical notes (amendment citations) are kept in
  italics after each section. Schedules are `##` headings. Where heading depth would exceed `######`,
  bold text is used instead. "Related provisions" and "Amendments not in force" schedules are kept;
  quoted amending text is rendered as block quotes.
- Tables: simple tables become Markdown tables (multi-row headers merged with `<br>`); tables with
  row/column spans are kept as HTML. Footnotes are rendered inline as `<sup>a</sup>` with the note
  text following the paragraph. Images (e.g. the music of *O Canada*, forms, diagrams) are linked to
  their official URL on `laws-lois.justice.gc.ca/images/`, not copied.
- Constitution files use GitHub footnotes (`[^n]`) for the official endnotes of the consolidation.

## Sources

- Consolidated Acts and Regulations: official XML published by the Department of Justice Canada,
  <https://github.com/justicecanada/laws-lois-xml> (`eng/acts`, `eng/regulations`, `fra/lois`,
  `fra/reglements`, plus `lookup/lookup.xml` and `lookup/lookupfull.xml` for status), the same data
  as served by <https://laws-lois.justice.gc.ca/eng/XML/…>. Each file's `source:` links to the law's
  page on the Justice Laws Website.
- Constitution Acts 1867 to 1982 (consolidation by the Department of Justice, with endnotes): no XML
  is published, so the official HTML full-text pages are converted:
  <https://laws-lois.justice.gc.ca/eng/Const/FullText.html> and
  <https://laws-lois.justice.gc.ca/fra/Const/TexteComplet.html>.

## Not covered

- **Provincial and territorial legislation** (the 10 provinces and 3 territories each have their own
  legislature and official publisher, e.g. CanLII / e-Laws Ontario / LégisQuébec). Out of scope for
  this repository.
- **Point-in-time (historical) versions** and **annual statutes as enacted** (the source repository's
  `annual-statutes-lois-annuelles/` folder, 2001–2026): only the current consolidation is included.
- **Other constitutional instruments** listed in the Schedule to the Constitution Act, 1982
  (Manitoba Act, 1870; Statute of Westminster, 1931; the various Constitution Acts 1871–1975 and
  orders in council admitting provinces, etc.) are not reproduced separately; the Justice consolidation
  only reproduces the 1867 and 1982 Acts (with later amendments incorporated and noted in endnotes).
- **Unofficial texts:** the French version of the *Constitution Act, 1867* (and of other parts
  enacted only in English) is not official — it is the Department of Justice translation
  (see section 55 of the Constitution Act, 1982). The English and French versions of Acts and
  regulations are both official.
- Six `Z-…` "acts" (e.g. `z-040.md`, *Canadian Forces Act, 1950*) are placeholder entries for
  unconsolidated Acts under which regulations exist; they contain only a short notice.
- Non-official extras of the website (tables of provisions, links to amending Acts, "Previous
  Versions") are not reproduced. Cross-references (`XRefExternal`/`XRefInternal`) are kept as plain
  text, not links.

## Licence

The source texts are © Government of Canada and are published under the
[Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada)
(see the `LICENSE.md` of `justicecanada/laws-lois-xml`); the Reproduction of Federal Law Order
(SI/97-5) additionally allows anyone to reproduce federal enactments, provided due diligence is
exercised in ensuring accuracy and that the reproduction is not represented as an official version.
**These Markdown files are not the official version**; for legal purposes consult the
Justice Laws Website (the official consolidations are those published there, under the
*Legislation Revision and Consolidation Act*). Conversion scripts in `scripts/` are offered under the
same terms.

## Regenerating

```sh
pip install -r scripts/requirements.txt
PYTHON=python3 sh scripts/build.sh            # raw data goes to ../_raw/ca by default
```

- `scripts/fetch_xml.sh` — shallow-clones / updates `justicecanada/laws-lois-xml` (~1 GB unpacked).
- `scripts/constitution.py <raw-dir> <repo>` — downloads (cached) and converts the Constitution pages
  (User-Agent `LawCodex/1.0 (+https://github.com/LawCodex)`, retries with back-off).
- `scripts/convert_xml.py <laws-lois-xml-dir> <repo>` — converts all Acts and regulations (4 worker
  processes, ~10 s).
- `scripts/stats.py <repo>` — prints the counts used above.

Delete the raw directory afterwards; nothing raw is committed.
