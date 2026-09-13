# Duplicate-name review — 0.3.1

Duplicate review runs automatically for every selected value. It adds evidence to the
existing match result; it never deletes words from either input or treats repeated names
as proof of an error. Repetition can be intentional, and different people can share a name.

## Examples

Unless stated otherwise, the spreadsheet value is **Areeb Khan**.

| Document text / source case | Review evidence |
| --- | --- |
| Areeb Areeb Khan | Repeated `areeb`, two consecutive uses on that page. |
| Areeb Khan Khan | Repeated `khan`, two consecutive uses on that page. |
| Areeb Khan twice on page 1 | Two full-value occurrences; page 1 count is 2. |
| Areeb Khan on pages 1 and 4 | Two full-value occurrences; page 1 and page 4 each have count 1. |
| Areeb Khan twice on page 1 and once on page 4 | Three occurrences, with both per-page counts. |
| Spreadsheet itself has Areeb Areeb Khan or Areeb Khan Khan | A repeated-word finding identifies the spreadsheet value as its location. |
| Spreadsheet Areeb Ahmed Khan; PDF Areeb Ahmed Ahmed Khan | The repeated middle word `ahmed` is flagged even when the similarity score is below threshold. |
| Areeb Khan once, plus Areeb Khanna | One full-value occurrence; the longer surname is not counted as another occurrence. |

An `EXACT` result can also need duplicate review: `Areeb Khan` is still a substring of
`Areeb Areeb Khan`. The result retains its original status, score, and earliest matching
page; the review flag makes the additional evidence visible. Match rate measures matching
only and does not mean that duplicate review has passed. CLI exit codes remain based on
missing values, not review flags. The CLI prints a review count when findings exist.

## Where to review

The web result summary includes **Review duplicates**. Choose **Review duplicates** in
the Show selector to see flagged cells; search and pagination still apply. Each row shows
a review badge and details with the relevant word, location, and/or per-page counts.
Printable HTML and Excel reports include the same review findings and summary count.
History retains the count for new runs. Older history displays **Not recorded** because
those runs were never audited for duplicates; rerun their original files to check them.

## Counting rules

- All pages' extracted text is reviewed, including successful OCR text, even after an
  earlier exact match. There is no extra OCR pass for duplicate detection.
- The configured Unicode/case/whitespace, punctuation, digit, and diacritic normalization
  applies. Reported repeated words are normalized, so their casing may differ from the PDF.
- `occurrence_count` counts non-overlapping full-value phrases with word boundaries in
  that normalized text. Letters, digits, and underscore are word characters. It is not a
  fuzzy-occurrence count and does not include extra-word variants that disrupt the phrase.
- With reverse enabled, both word orders are counted; overlapping forward/reverse spans
  are counted once. Identical forward/reverse candidates are not counted twice.
- Adjacent equal words are collapsed only in a separate review index to locate repeated
  first, middle, or last words within an otherwise matching value. Normal exact/fuzzy
  matching always uses the original normalized text. Unrelated repetitions are ignored.
- Repeated words are reported once per distinct word and location (spreadsheet or PDF
  page), with the largest consecutive run length at that location. `count` in a repeated
  word finding means run length, not the number of separate problematic names on a page.
- Duplicate spreadsheet rows reuse computation and receive independent result lists.
  They do not increase the document occurrence count. The summary counts flagged cells,
  not distinct names or distinct people.

## Limits

Exact-match status retains the existing substring semantics for compatibility. A substring
inside a longer word can therefore be `EXACT` with zero full-value occurrences. Full-value
counting supplies additional evidence; it is not a new strict identity-matching mode.

Extraction/OCR can miss or duplicate text, join line breaks, or place separate visual
records next to one another. Review findings describe this extracted sequence; check the
PDF visually when repetition may be a layout or OCR artifact. No row/person association
or expected number of appearances is inferred. Values spanning page boundaries, approximate
duplicate spellings, and non-adjacent repeated words within a name are not enumerated as
duplicate findings. These require a separate matching/identity policy.

## Implementation and tests

`DuplicateAuditor` in `proofcheck/duplicates.py` shares already normalized pages and prepares
the repeated-word index once per run. `PreparedMatcher` caches the complete match and review
for each distinct original expected string. Exact matches still skip fuzzy scoring. Counts
are stored per page, keeping output smaller than returning every character offset.

`tests/test_duplicates.py` covers the examples, source repetitions, later-page findings,
normalization, Unicode/hyphenated words, substring boundaries, reverse overlap, blanks,
result isolation, legacy history, and real API/report downloads. The frontend and Chromium
suites verify badges, counts, filtering, escaping, search, pagination, and small-screen use.
Updated benchmarks include these checks and a dedicated duplicate-name workload; see
[PERFORMANCE.md](PERFORMANCE.md).
