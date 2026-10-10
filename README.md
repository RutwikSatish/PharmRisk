# PharmNet Risk

A Streamlit dashboard that shows **who is approved to make each US prescription drug** and how that supplier structure relates to drugs on the FDA shortage list.

## What it does

It joins two public FDA datasets. The Orange Book lists every approved prescription product and the company holding each approval; the Drug Shortages Database lists drugs FDA considers in shortage and products companies plan to discontinue. For every drug *market* (one active ingredient by one route), the tool counts approved suppliers, checks patent and exclusivity status, measures how long the drug has been on the market, and flags shortages and discontinuation notices. It then shows which of those features shortages tend to share, and compares the results with published research.

## How it helps

- **Hospital and health-system pharmacy:** look up a drug's supplier base and use the early-warning watchlist (off-patent, limited-competition injectables; markets with discontinuation notices) to prioritise buffer stock or alternate sourcing.
- **Policy, procurement and research:** a free, reproducible view of which structural factors line up with shortages, and where supplier-count metrics fall short.
- **Journalists, students and the public:** fact-check "only one company makes this" claims, and see why that usually reflects a patent rather than fragility.

It is **not** a forecast, a market-share analysis or clinical guidance. It cannot see prices, sales volumes, manufacturing sites or API sources, which research identifies as among the most predictive factors.

## Dashboard tabs

| Tab | Question it answers |
|---|---|
| Start here | What is this, who is it for, what are the headline findings? |
| What drives shortages | How do route, product age, supplier count and combined flags relate to shortage rates? |
| Early-warning watchlist | Which markets carry the most observable risk factors right now? |
| Supplier concentration | How many approved suppliers does a given drug have? |
| Current shortages | What is on the list, for how long, and why? |
| Company exposure | Whose disruption would leave markets with no approved alternative? |
| Validation & methods | Do the results agree with published research? How was it built? |

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
pytest -q            # 25 unit tests + pipeline invariants
```

Data files are expected next to `app.py` (or in the folder set by `PHARMNET_DATA_DIR`).

## Data

| File | Source | Notes |
|---|---|---|
| `products.txt`, `patent.txt`, `exclusivity.txt` | [FDA Orange Book data files](https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files) | `~`-delimited; updated monthly by FDA |
| `Drugshortages.csv` | [FDA Drug Shortages Database](https://www.accessdata.fda.gov/scripts/drugshortages/) export | Contains Current, To Be Discontinued, and a small number of Resolved entries |

Record the download date of each file in `data_manifest.json`. The app shows these dates in the sidebar. The **analysis as-of date** (used to decide whether a patent or exclusivity has expired) defaults to the latest "Date of Update" in the shortage export and can be overridden in the manifest.

## Methodology

**Unit of analysis — the "market".** A market is an *active-ingredient set* × *route family* (Injectable, Oral, Ophthalmic/Otic, Respiratory/Nasal, Topical/Local, Irrigation, Other), built from RX rows of the Orange Book. Oral and injectable versions of the same molecule are not substitutes for a hospital, so they are separate markets. Combination products are keyed by their full set of components. Salt forms are kept distinct (e.g. *epinephrine bitartrate* vs *epinephrine*); a second count that pools salt forms is reported for shortage drugs as a sensitivity check.

**Concentration measure.** The primary measure is the number of distinct application holders in the market. Holders are consolidated to a parent company only where an explicit rule exists in `analysis.PARENT_RULES` (currently Pfizer/Hospira). Tiers: 1 (sole source), 2 (duopoly), 3–4 (few sources), 5+ (multi-source).

**About HHI.** The Herfindahl–Hirschman Index needs market shares (sales or volume). The Orange Book has none, so a true HHI cannot be computed from it. An *equal-share* HHI (10,000 ÷ applicants) is shown only to place markets on the familiar 0–10,000 scale; it is a direct function of the applicant count and carries no additional information. For reference, the 2023 DOJ/FTC Merger Guidelines treat markets with HHI above 1,800 as highly concentrated; under equal shares that corresponds to five or fewer firms.

**Sole-source split.** A sole-source market is labelled *Protected* if any application in it has an unexpired Orange Book patent or exclusivity at the as-of date, otherwise *Off-patent sole source*. Most sole-source markets are protected brands. The off-patent group, where generic entry is legally possible but has not occurred, is the structurally fragile set.

**Shortage matching.** Shortage names are normalised (strengths, hydrate words and trailing dosage-form words removed; components split on `;`, `,` and `/`) and matched to Orange Book ingredient sets. Order of attempts: exact set match; salt-stripped base-name match; otherwise the drug is classified as *only discontinued approvals* or *not in the Orange Book* (biologics, naming gaps). The shortage's route family is inferred from its name and presentation; if it cannot be inferred, the union of applicants across all routes is used and labelled as such. Every unmatched drug is shown in the app, not dropped.

**Shortage rates by factor.** For every market the app records whether it has a current (exactly matched) shortage, then reports the share of markets in shortage by route, product age (years since the earliest approval in the market, a proxy for low price), approved-applicant count, and number of structural flags. Patent-protected markets are excluded from the age and applicant comparisons so brand monopolies don't distort them. All of this is descriptive, in-sample and cross-sectional.

**Watchlist flags.** One point each for: injectable route (manufacturing complexity); ≤3 approved applicants (the "limited competition" threshold used in the literature); off-patent and first approved ≥20 years ago (low-price proxy); and a "To Be Discontinued" notice in the market. The *structural score* omits the discontinuation flag because it comes from the same database as the shortage outcome. These flags are a transparent checklist, not a fitted or validated prediction model.

**Validation.** `benchmarks.py` lists published findings (FDA 2019, USP 2024, IQVIA 2023, CMAJ Open 2020, IMS 2012, a 2024 Orange Book–based research letter, ASHP 2026). The Validation tab places each next to the closest number this tool can compute and states whether they agree.

## Findings in the bundled snapshot

These are properties of one snapshot and should be re-checked whenever the data are refreshed.

- About 70% of sole-source markets are patent- or exclusivity-protected, so a raw "single-source" count mostly measures intellectual-property monopolies, not supply fragility.
- Injectables are about 74% of route-matched shortage drugs but about 29% of RX markets, in line with IQVIA's finding that roughly two-thirds of FDA-listed shortages were injectable.
- Among off-patent markets, about 8.6% of those first approved 40+ years ago are in shortage, versus under 1% of those approved within 20 years — consistent with FDA's link between shortages and low-price older generics.
- Approved-applicant count on its own shows a weak, non-monotonic relationship with shortage. Published work that finds a stronger link (e.g. CMAJ Open 2020 in Canada) uses marketed products; the IMS (2012) finding that most shortage drugs have one or two suppliers *by volume* suggests the gap is between approvals on paper and actual production.
- Markets with all three structural flags show a shortage rate around five times that of markets with none.

## Limitations

- **Application holder ≠ manufacturer ≠ API source.** Many holders use contract manufacturers, and many finished products depend on a few active-ingredient plants. Concentration upstream is invisible here.
- **Approved ≠ marketed.** An approval can stay in the RX section while the product is not actually being shipped, so applicant counts overstate active suppliers. Cross-checking against the FDA NDC Directory marketing status would tighten this.
- **No volumes or prices.** Without them there is no true market share and no way to separate a 95/5 market from a 50/50 one.
- **Biologics are excluded.** BLA products are in the Purple Book, not the Orange Book.
- **Single snapshot.** The shortage export largely omits resolved shortages, so it cannot support trend analysis or survival modelling without historical pulls.
- **Name matching is heuristic.** Spot-check matches in the "Shortage × concentration" tab before citing any individual drug.
- **Parent consolidation is minimal.** Subsidiary names are mostly treated as separate holders, which understates concentration at the corporate level.

## Suggested extensions

1. Add NDC Directory marketing status to count *active* rather than approved suppliers.
2. Link manufacturing sites and API sources (e.g. FDA establishment registrations, DMF holders) to measure upstream concentration.
3. Pull the shortage list on a schedule to build a history, then model time-to-resolution or shortage onset against market structure, controlling for route and product age.
4. Expand `PARENT_RULES` from sourced corporate-ownership data.
5. Compare against ASHP's shortage list, which uses a broader definition than FDA.

## References

- IQVIA Institute (2023). *Drug Shortages in the US 2023: A Closer Look at Volume and Price Dynamics.*
- USP (2024). *Drug Shortage Report* (USP Medicine Supply Map).
- CMAJ Open (2020), 8(3):E535 — factors associated with drug shortages in Canadian markets.
- IMS Institute for Healthcare Informatics (2012) — suppliers of products on the US shortage list.
- Research letter on essential generics in shortage with limited competition (2024), PubMed Central PMC11534946.
- ASHP / University of Utah Drug Information Service, quarterly shortage statistics.
- FDA Drug Shortages Task Force (2019, updated 2020). *Drug Shortages: Root Causes and Potential Solutions.* U.S. Food and Drug Administration.
- U.S. Department of Justice & Federal Trade Commission (2023). *Merger Guidelines.*
- Herfindahl, O. C. (1950). *Concentration in the Steel Industry* (PhD dissertation, Columbia University).
- Hirschman, A. O. (1945). *National Power and the Structure of Foreign Trade.* University of California Press.

## Disclaimer

Independent academic project. Not affiliated with or endorsed by FDA. Not intended for clinical, procurement or investment decisions.

Author: Rutwik Satish · MS Engineering Management, Northeastern University
