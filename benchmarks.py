"""
Published benchmarks used on the "Validation" tab.

Each entry pairs a published finding with a function that computes the closest
comparable number from this tool's data. Published values are paraphrased; see
the source link for exact wording and definitions. Update when sources change.
"""

SOURCES = {
    "fda2019": ("FDA Drug Shortages Task Force (2019, updated 2020). Drug Shortages: Root Causes and Potential Solutions.",
                "https://www.fda.gov/drugs/drug-shortages/report-drug-shortages-root-causes-and-potential-solutions"),
    "usp2024": ("USP (2024). Inaugural Drug Shortage Report, based on the USP Medicine Supply Map.",
                "https://www.usp.org/supply-chain/build-resilience-and-reduce-drug-shortages"),
    "iqvia2023": ("IQVIA Institute (2023). Drug Shortages in the US 2023: A Closer Look at Volume and Price Dynamics (as summarised by Pharmaceutical Commerce).",
                  "https://www.pharmaceuticalcommerce.com/view/an-examination-of-us-drug-shortages-impact-on-the-supply-chain"),
    "pmc2024": ("Research letter on essential generic drugs in shortage with limited competition, 2024 (PubMed Central PMC11534946).",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC11534946"),
    "cmaj2020": ("CMAJ Open (2020) 8(3):E535. Retrospective cohort of 3,470 Canadian drug markets.",
                 "https://cmajopen.ca/content/8/3/E535"),
    "ims2012": ("IMS Institute for Healthcare Informatics (2012), as summarised by GaBI Online.",
                "https://gabionline.net/reports/Suppliers-of-products-on-the-drug-shortages-list-in-the-US"),
    "ashp2026": ("ASHP / University of Utah Drug Information Service, Q2 2026 shortage statistics (as reported by AJMC).",
                 "https://www.ajmc.com/view/active-us-drug-shortages-rise-for-third-straight-quarter"),
}
