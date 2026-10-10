# Audit of the original PharmNet Risk app

Findings were reproduced by re-running the original pipeline against the bundled data snapshot (shortage export last updated 2026-05-11).

## A. Methodological problems (affect what the numbers mean)

| # | Issue | Evidence | Fix in this version |
|---|---|---|---|
| A1 | "HHI" was computed from each applicant's share of **Orange Book rows** (strengths/pack listings), not market share. A firm with 12 lisinopril strengths counted 12× one with a single strength. | `value_counts(normalize=True)` on product rows | Primary measure is now applicant count; equal-share HHI shown only as a labelled proxy |
| A2 | Markets were defined by ingredient only, pooling oral and injectable forms. | 284 ingredients looked multi-source overall but had at least one single-applicant dosage form | Market = ingredient set × route family |
| A3 | "Single source" mostly measured patents, not fragility. | 505 of 714 single-source ingredients (71%) had an unexpired patent or exclusivity; `patent.txt` and `exclusivity.txt` were loaded but never used | Sole-source split into Protected vs Off-patent |
| A4 | The app's own data contradicted its framing. | 42 of 56 matched shortage drugs fell in the "Competitive" tier | Hypothesis is now tested explicitly and the result reported, whichever way it goes |
| A5 | Combination products were reduced to their first component. | "Epinephrine Bitartrate, Lidocaine…" matched plain EPINEPHRINE BITARTRATE (a false single-source hit) | Full ingredient-set matching |
| A6 | 24% of shortage drugs were silently dropped, including IV fluids. | 18 of 74 unmatched (dextrose, 0.9% sodium chloride, sterile water…) | 68 of 74 matched; the rest are listed with a reason |
| A7 | Root-cause pie hid missing data. | 63% of current records have no reason recorded | "Not reported" slice + caption |
| A8 | "Records by year" chart implied a trend from a survivorship-biased export. | Only 29 Resolved rows in the file | Replaced by "time listed" distribution |
| A9 | "Network criticality" language with no network analysis. | Simple counts | Relabelled as holder sole-source exposure |

## B. Bugs

- **B1** Vulnerability KPIs counted shortage *records* while labelled as drugs: "Single Source" showed 29, the real number of drugs was 5.
- **B2** Search used regex matching; input like `(` would raise an error. Now `regex=False`.
- **B3** Hard-coded captions ("1,838 unique RX ingredients", "over 27%") go stale on refresh. All captions are now computed.
- **B4** Invalid CSS (`visibility:!important`).
- **B5** Multi-category therapeutic labels (330 records with `;`) were counted as their own categories.

## C. Credibility issues

- **C1** Wrong citation: *Drug Shortages: Root Causes and Potential Solutions* is the FDA Drug Shortages Task Force report (2019), not GAO (2014).
- **C2** A truncated "Research context" citation was left in the docstring.
- **C3** "Live FDA drug shortage records" — the data are a static snapshot with no recorded download date. Added `data_manifest.json` and sidebar vintage display.
- **C4** No README, methodology, limitations, tests, or pinned dependencies.
- **C5** No disclaimer distinguishing the project from FDA.

## D. Still open (needs your input or new data)

- Record actual download dates in `data_manifest.json`.
- Add a LICENSE file (code) — data are US-government public domain.
- Expand parent-company rules from a sourced ownership dataset.
- Use NDC Directory marketing status to count active, not just approved, suppliers.

## E. Second pass: research comparison (corrections to the first rewrite)

- **E1 — my first rewrite overstated a conclusion.** It said the data "do not support" the idea that fewer suppliers mean more shortages, based on comparing all markets, including patent-protected brands, which almost never go short. Restricted to off-patent markets the picture is mixed rather than reversed, and published work (CMAJ Open 2020; IMS 2012) does find more shortage risk with fewer *active* or *volume* suppliers. The dashboard now says applicant count is a weak signal on its own and attributes the gap to approved-vs-active suppliers.
- **E2 — missing drivers.** Research consistently names price, manufacturing complexity, geographic concentration and quality (FDA 2019; USP 2024). The first version used none of them. Added route (complexity) and product age (price proxy), which both line up with shortages as published work predicts.
- **E3 — unused forward-looking data.** 188 drugs in the file carry "To Be Discontinued" notices; these were ignored. Now surfaced as a watchlist flag, with a caveat that a notice may cover only some strengths.
- **E4 — leakage risk.** The discontinuation flag comes from the same database as the shortage outcome, so it is excluded from the structural score used to compare shortage rates.
- **E5 — validation.** Classification of unlinkable drugs (cefotaxime as discontinued-only, triamcinolone hexacetonide as not in the Orange Book) matches an independent 2024 Orange Book study.
