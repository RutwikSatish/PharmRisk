"""
PharmNet Risk — analysis layer (no UI code here, so it can be unit-tested).

Unit of analysis
----------------
A "market" is (active-ingredient set, route family), built from the FDA Orange
Book RX section. Oral and injectable versions of the same molecule are not
substitutes for a hospital pharmacist, so they are analysed separately.

Concentration measure
---------------------
The Orange Book contains no sales or volume data, so true market-share HHI
cannot be computed from it. The primary measure here is the number of distinct
application holders (parent-consolidated where an alias rule exists) with an
approved, non-discontinued RX product in the market. An *equal-share* HHI
(10,000 / N) is reported only as a structural proxy on the DOJ/FTC 0–10,000
scale; it is a function of N and carries no extra information.

What this does NOT measure (see README "Limitations")
-----------------------------------------------------
- Application holder ≠ manufacturing site ≠ API source.
- Approved ≠ actually marketed / shipping product today.
- Biologics (BLA, Purple Book) are absent from the Orange Book.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_FILES = ["Drugshortages.csv", "products.txt", "exclusivity.txt", "patent.txt"]


def missing_files(data_dir: str) -> list[str]:
    return [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(data_dir, f))]


def load_raw(data_dir: str) -> dict[str, pd.DataFrame]:
    shortage = pd.read_csv(os.path.join(data_dir, "Drugshortages.csv"), dtype=str)
    products = pd.read_csv(os.path.join(data_dir, "products.txt"), sep="~", dtype=str)
    exclusivity = pd.read_csv(os.path.join(data_dir, "exclusivity.txt"), sep="~", dtype=str)
    patents = pd.read_csv(os.path.join(data_dir, "patent.txt"), sep="~", dtype=str)
    for df in (shortage, products, exclusivity, patents):
        df.columns = [c.strip() for c in df.columns]
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].str.strip()
    return dict(shortage=shortage, products=products, exclusivity=exclusivity, patents=patents)


def load_manifest(data_dir: str) -> dict:
    path = os.path.join(data_dir, "data_manifest.json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Name normalisation and matching
# ─────────────────────────────────────────────────────────────────────────────

# Dosage-form / packaging words that appear at the END of FDA shortage names.
FORM_WORDS = {
    "INJECTION", "INJECTABLE", "INJECTIONS", "TABLET", "TABLETS", "CAPSULE", "CAPSULES",
    "SOLUTION", "SUSPENSION", "CREAM", "OINTMENT", "GEL", "PATCH", "SPRAY", "INHALER",
    "INFUSION", "ORAL", "EXTENDED", "DELAYED", "RELEASE", "CONCENTRATE", "INTRAVENOUS",
    "POWDER", "FOR", "FILM", "COATED", "OPHTHALMIC", "IRRIGANT", "IRRIGATION", "INSERT",
    "EMULSION", "CHEWABLE", "ORALLY", "DISINTEGRATING", "LYOPHILIZED", "KIT", "SYRUP",
    "ELIXIR", "AEROSOL", "NASAL", "TOPICAL", "TRANSDERMAL", "SYSTEM", "VIAL", "VIALS",
    "PREMIX", "PREMIXED", "PREFILLED", "SYRINGE", "BAG", "USP", "IN", "AND", "LIQUID",
    "DROPS", "LOTION", "SUPPOSITORY", "SUBCUTANEOUS", "INTRAMUSCULAR", "PEN", "AUTO-INJECTOR",
    "AUTOINJECTOR", "INHALATION", "RECONSTITUTION", "STERILE-FILLED",
}
HYDRATE_WORDS = {"MONOHYDRATE", "DIHYDRATE", "TRIHYDRATE", "HEMIHYDRATE", "SESQUIHYDRATE",
                 "PENTAHYDRATE", "HEPTAHYDRATE", "ANHYDROUS", "HYDRATE"}
# Trailing salt words dropped ONLY in the fallback "base-name" match.
SALT_WORDS = {"HYDROCHLORIDE", "HCL", "SODIUM", "POTASSIUM", "CALCIUM", "SULFATE", "ACETATE",
              "PHOSPHATE", "CITRATE", "TARTRATE", "BITARTRATE", "MALEATE", "MESYLATE",
              "BESYLATE", "SUCCINATE", "FUMARATE", "BROMIDE", "HYDROBROMIDE", "MAGNESIUM",
              "TROMETHAMINE", "DISODIUM", "LACTATE", "GLUCONATE", "NITRATE", "DECANOATE"}
# Small, explicit alias table for names that differ between the two FDA systems.
# Applied to shortage-side names only.
NAME_ALIASES = {
    "AMINO ACID": "AMINO ACIDS",
}

_STRENGTH = re.compile(
    r"\b\d+(\.\d+)?\s*(%|MG|MCG|G|ML|MEQ|UNITS?|IU|MMOL)(\s*/\s*\d*\.?\d*\s*(ML|G|L|MG))?\b"
)
_PARENS = re.compile(r"\([^)]*\)")
_SPACES = re.compile(r"\s+")


def _norm_component(c: str, shortage_side: bool) -> str:
    c = _PARENS.sub(" ", c.upper())
    toks = [t for t in _SPACES.split(c) if t and t not in HYDRATE_WORDS]
    if not shortage_side:  # Orange Book Ingredient field is already a clean name
        if toks and toks[-1] == "KIT":  # radiopharmaceutical kits, e.g. "... PYROPHOSPHATE KIT"
            toks = toks[:-1]
        return " ".join(toks)
    c = _STRENGTH.sub(" ", " ".join(toks))
    c = re.sub(r"\b\d+(\.\d+)?%", " ", c)
    toks = [t for t in _SPACES.split(c) if t]
    while toks and toks[-1] in FORM_WORDS:
        toks.pop()
    out = " ".join(toks).strip(" ,.-")
    return NAME_ALIASES.get(out, out)


def _base_component(c: str) -> str:
    toks = c.split()
    while len(toks) > 1 and toks[-1] in SALT_WORDS:
        toks.pop()
    return " ".join(toks)


def ingredient_key(name: str, source: str) -> frozenset[str]:
    """Normalised set of active-ingredient components.

    source='ob'       Orange Book: components separated by ';' (commas can be
                      part of a chemical name, e.g. 'POTASSIUM PHOSPHATE, DIBASIC').
    source='shortage' FDA shortage list: components separated by ';', ',' or '/';
                      segments that are pure dosage-form text are dropped.
    """
    if not isinstance(name, str) or not name.strip():
        return frozenset()
    pattern = r";" if source == "ob" else r"[;,/]"
    parts = {_norm_component(p, source == "shortage") for p in re.split(pattern, name)} - {""}
    if source == "shortage" and "STERILE WATER" in parts:
        # The shortage list says "Sterile Water"; the Orange Book names the route.
        sw = "STERILE WATER FOR IRRIGATION" if "IRRIGA" in name.upper() else "STERILE WATER FOR INJECTION"
        parts = (parts - {"STERILE WATER"}) | {sw}
    return frozenset(parts)


def base_key(key: frozenset[str]) -> frozenset[str]:
    return frozenset(_base_component(c) for c in key)


def key_label(key: frozenset[str]) -> str:
    return "; ".join(sorted(key))


# ─────────────────────────────────────────────────────────────────────────────
# Route families
# ─────────────────────────────────────────────────────────────────────────────

ROUTE_FAMILIES = {
    "Injectable": ["INJECTION", "INTRAVENOUS", "SUBCUTANEOUS", "INTRAMUSCULAR", "IM-IV",
                   "INTRATHECAL", "INTRA-ARTERIAL", "SPINAL", "INTRAVITREAL", "INTRAOSSEOUS",
                   "INTRADERMAL", "INTRAPERITONEAL", "INTRACAVITARY", "INTRAVESICAL",
                   "PERFUSION", "INTRA-ARTICULAR", "PERIARTICULAR", "INTRALYMPHATIC",
                   "INTRACRANIAL", "INTRAPLEURAL", "INTERSTITIAL", "ENDOTRACHEAL",
                   "IMPLANTATION", "INTRAUTERINE"],
    "Oral": ["ORAL", "SUBLINGUAL", "BUCCAL", "ENTERAL"],
    "Ophthalmic/Otic": ["OPHTHALMIC", "INTRAOCULAR", "INTRACAMERAL", "OTIC"],
    "Respiratory/Nasal": ["INHALATION", "NASAL"],
    "Topical/Local": ["TOPICAL", "TRANSDERMAL", "DENTAL", "VAGINAL", "RECTAL", "INTRA-ANAL",
                      "URETHRAL", "ENDOCERVICAL", "PERIODONTAL", "PYELOCALYCEAL"],
    "Irrigation": ["IRRIGATION"],
}


def ob_route_families(df_route: str, ingredient: str = "") -> list[str]:
    route = str(df_route).split(";")[-1].upper()
    fams = [fam for fam, kws in ROUTE_FAMILIES.items() if any(k in route for k in kws)]
    if not fams:  # route "N/A": fall back to hints in the ingredient name
        ing = str(ingredient).upper()
        if "FOR INJECTION" in ing:
            fams = ["Injectable"]
        elif "FOR IRRIGATION" in ing:
            fams = ["Irrigation"]
    return fams or ["Other"]


def shortage_route_family(generic_name: str, presentation: str) -> str | None:
    """Best-effort route family for a shortage record; None if undetermined."""
    t = f"{generic_name} {presentation}".upper()
    if "IRRIGA" in t:
        return "Irrigation"
    if "OPHTHALMIC" in t or " OTIC" in t:
        return "Ophthalmic/Otic"
    if any(k in t for k in ["INJECT", "INFUSION", "INTRAVENOUS", "VIAL", "SYRINGE",
                            "FOR SOLUTION", "AMPULE", "AMPOULE", "PREMIX"]):
        return "Injectable"
    if any(k in t for k in ["INHAL", "NASAL", "NEBUL", "SPRAY"]):
        return "Respiratory/Nasal"
    if any(k in t for k in ["TABLET", "CAPSULE", "ORAL", "SYRUP", "ELIXIR", "SUBLINGUAL"]):
        return "Oral"
    if any(k in t for k in ["CREAM", "OINTMENT", "TOPICAL", "PATCH", "TRANSDERMAL", "GEL", "LOTION", "FILM, EXTENDED"]):
        return "Topical/Local"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Parent-company consolidation (deliberately small and explicit)
# ─────────────────────────────────────────────────────────────────────────────

# (regex on Applicant_Full_Name, parent label). Extend with sourced rules only.
PARENT_RULES = [
    (r"\bPFIZER\b|^HOSPIRA\b|PARKE-DAVIS DIV", "PFIZER (incl. Hospira)"),
]


def parent_of(applicant: str) -> str:
    a = str(applicant).upper()
    for pat, parent in PARENT_RULES:
        if re.search(pat, a):
            return parent
    return a


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────


def applicant_tier(n: int) -> str:
    if n <= 1:
        return "1 · Sole source"
    if n == 2:
        return "2 · Duopoly"
    if n <= 4:
        return "3–4 · Few sources"
    return "5+ · Multi-source"


LIMITED_COMPETITION_MAX = 3   # "3 or fewer manufacturers" threshold used in the literature
MATURE_YEARS = 20             # first approval ≥ 20 years ago: proxy for an old, low-price generic

FLAG_LABELS = {
    "flag_injectable": "Injectable (manufacturing complexity)",
    "flag_limited": "≤3 approved applicants (limited competition)",
    "flag_mature_offpatent": "Off-patent, first approved ≥20 yrs ago (low-price proxy)",
    "flag_discontinuation": "A company has announced discontinuation",
}

TIER_ORDER = ["1 · Sole source", "2 · Duopoly", "3–4 · Few sources", "5+ · Multi-source"]


@dataclass
class Results:
    as_of: pd.Timestamp
    markets: pd.DataFrame          # one row per (ingredient set, route family)
    current: pd.DataFrame          # current shortage records with match info
    shortage_drugs: pd.DataFrame   # one row per shortage Generic Name
    companies: pd.DataFrame        # sole-source exposure per parent
    shortage_all: pd.DataFrame
    notes: dict = field(default_factory=dict)


def _parse_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", format="mixed")


def build(raw: dict[str, pd.DataFrame], as_of: str | None = None) -> Results:
    shortage = raw["shortage"].copy()
    products = raw["products"].copy()

    # Data vintage: default to the most recent update in the shortage export.
    shortage["Date of Update"] = _parse_date(shortage["Date of Update"])
    shortage["Initial Posting Date"] = _parse_date(shortage["Initial Posting Date"])
    as_of_ts = pd.Timestamp(as_of) if as_of else shortage["Date of Update"].max()

    # ── Protected applications (unexpired patent or exclusivity at as_of) ─────
    pat = raw["patents"].copy()
    exc = raw["exclusivity"].copy()
    pat["exp"] = _parse_date(pat["Patent_Expire_Date_Text"])
    exc["exp"] = _parse_date(exc["Exclusivity_Date"])
    pat_appl = set(pat.loc[pat["exp"] > as_of_ts, "Appl_No"].str.zfill(6))
    exc_appl = set(exc.loc[exc["exp"] > as_of_ts, "Appl_No"].str.zfill(6))

    # ── Orange Book RX → markets ──────────────────────────────────────────────
    rx = products[products["Type"] == "RX"].copy()
    rx["Appl_No"] = rx["Appl_No"].str.zfill(6)
    rx["key"] = rx["Ingredient"].apply(lambda s: ingredient_key(s, "ob"))
    rx["route_family"] = [ob_route_families(r, i) for r, i in zip(rx["DF;Route"], rx["Ingredient"])]
    rx = rx.explode("route_family")
    rx["parent"] = rx["Applicant_Full_Name"].apply(parent_of)
    rx["protected"] = rx["Appl_No"].isin(pat_appl | exc_appl)
    rx["approval"] = _parse_date(
        rx["Approval_Date"].str.replace("Approved Prior to Jan 1, 1982", "Jan 1, 1981", regex=False))

    markets = (
        rx.groupby(["key", "route_family"])
        .agg(
            n_applicants=("parent", "nunique"),
            n_products=("Appl_No", "size"),
            n_applications=("Appl_No", "nunique"),
            any_protected=("protected", "any"),
            has_generic=("Appl_Type", lambda s: (s == "A").any()),
            applicants=("parent", lambda s: "; ".join(sorted(set(s)))),
            first_approval=("approval", "min"),
        )
        .reset_index()
    )
    anda = rx[rx["Appl_Type"] == "A"].groupby(["key", "route_family"])["parent"].nunique()
    markets["n_generic_holders"] = [int(anda.get((k, r), 0)) for k, r in zip(markets["key"], markets["route_family"])]
    markets["years_on_market"] = ((as_of_ts - markets["first_approval"]).dt.days / 365.25).round(1)
    markets["limited_competition"] = markets["n_applicants"] <= LIMITED_COMPETITION_MAX
    markets["Ingredient"] = markets["key"].apply(key_label)
    markets["tier"] = markets["n_applicants"].apply(applicant_tier)
    markets["hhi_equal_share"] = (10_000 / markets["n_applicants"]).round(0).astype(int)
    markets["sole_source_type"] = np.where(
        markets["n_applicants"] > 1, "",
        np.where(markets["any_protected"], "Protected (patent/exclusivity)", "Off-patent sole source"),
    )
    markets["base"] = markets["key"].apply(base_key)

    # ── Current shortages → markets ──────────────────────────────────────────
    current = shortage[shortage["Status"] == "Current"].copy()
    current["key"] = current["Generic Name"].apply(lambda s: ingredient_key(s, "shortage"))
    current["base"] = current["key"].apply(base_key)
    current["route_family"] = [
        shortage_route_family(g, p)
        for g, p in zip(current["Generic Name"], current.get("Presentation", ""))
    ]

    exact_keys = set(markets["key"])
    base_keys = set(markets["base"])
    discn = products[products["Type"] == "DISCN"]["Ingredient"].apply(lambda s: ingredient_key(s, "ob"))
    discn_keys, discn_base = set(discn), {base_key(k) for k in discn}

    def match_status(row) -> str:
        if row["key"] in exact_keys:
            return "Exact"
        if row["base"] in base_keys:
            return "Base name (salt-stripped)"
        if row["key"] in discn_keys or row["base"] in discn_base:
            return "Only discontinued approvals"
        return "Not in Orange Book (biologic or naming gap)"

    current["match"] = current.apply(match_status, axis=1)

    rx["base"] = rx["key"].apply(base_key)
    # Applicant sets per (key, route) and (base, route) so we can take unions.
    sets_key = rx.groupby(["key", "route_family"])["parent"].agg(set).to_dict()
    sets_base = rx.groupby(["base", "route_family"])["parent"].agg(set).to_dict()
    prot_key = rx.groupby(["key", "route_family"])["protected"].any().to_dict()
    routes_by_key: dict = {}
    for (k, rf) in sets_key:
        routes_by_key.setdefault(k, []).append(rf)
    routes_by_base: dict = {}
    for (b, rf) in sets_base:
        routes_by_base.setdefault(b, []).append(rf)

    def _union(sets: dict, k, routes) -> set:
        out: set = set()
        for rf in routes:
            out |= sets.get((k, rf), set())
        return out

    def lookup(row):
        """Applicants in the shortage's route family; if the route can't be
        determined (or has no listing), the union across all routes, labelled."""
        empty = {"n_applicants": np.nan, "n_applicants_any_salt": np.nan,
                 "any_protected": np.nan, "route_used": None}
        if row["match"] == "Exact":
            k, sets, routes = row["key"], sets_key, routes_by_key.get(row["key"], [])
        elif row["match"].startswith("Base"):
            k, sets, routes = row["base"], sets_base, routes_by_base.get(row["base"], [])
        else:
            return pd.Series(empty)
        rf = row["route_family"]
        use = [rf] if rf in routes else routes
        label = rf if rf in routes else "All routes (route not determined)"
        apps = _union(sets, k, use)
        apps_salt = _union(sets_base, row["base"], [r for r in use if (row["base"], r) in sets_base])
        prot = any(prot_key.get((row["key"], r), False) for r in use)
        return pd.Series({"n_applicants": len(apps), "n_applicants_any_salt": len(apps_salt | apps),
                          "any_protected": prot, "route_used": label})

    current = pd.concat([current, current.apply(lookup, axis=1)], axis=1)
    current["tier"] = current["n_applicants"].apply(lambda n: applicant_tier(int(n)) if pd.notna(n) else "Unmatched")
    current["days_in_shortage"] = (as_of_ts - current["Initial Posting Date"]).dt.days

    shortage_drugs = (
        current.groupby("Generic Name")
        .agg(
            presentations=("Generic Name", "size"),
            companies=("Company Name", lambda s: s.nunique()),
            match=("match", "first"),
            route=("route_used", "first"),
            n_applicants=("n_applicants", "first"),
            n_applicants_any_salt=("n_applicants_any_salt", "first"),
            protected=("any_protected", "first"),
            tier=("tier", "first"),
            first_posted=("Initial Posting Date", "min"),
            days_in_shortage=("days_in_shortage", "max"),
            category=("Therapeutic Category", "first"),
            reason=("Reason for Shortage",
                    lambda s: s.dropna().replace("", np.nan).dropna().mode().iat[0]
                    if s.dropna().replace("", np.nan).dropna().size else "Not reported"),
        )
        .reset_index()
        .sort_values(["n_applicants", "presentations"], ascending=[True, False])
    )

    # Flag markets with a current shortage (for the association check).
    hit = current[current["match"] == "Exact"][["key", "route_family"]].dropna().drop_duplicates()
    hit["in_shortage"] = True
    markets = markets.merge(hit, on=["key", "route_family"], how="left")
    markets["in_shortage"] = markets["in_shortage"].fillna(False).astype(bool)

    # ── Pending discontinuations ("To Be Discontinued" status) ───────────────
    tbd = shortage[shortage["Status"] == "To Be Discontinued"].copy()
    tbd["key"] = tbd["Generic Name"].apply(lambda s: ingredient_key(s, "shortage"))
    tbd["route_family"] = [shortage_route_family(g, p) for g, p in zip(tbd["Generic Name"], tbd.get("Presentation", ""))]
    tbd = tbd[tbd["key"].isin(exact_keys)]
    # unknown route → attribute to every route of that ingredient
    rmap = markets.groupby("key")["route_family"].apply(list).to_dict()
    tbd["route_family"] = [[rf] if rf in rmap.get(k, []) else rmap.get(k, []) for k, rf in zip(tbd["key"], tbd["route_family"])]
    tbd = tbd.explode("route_family")
    disc = (tbd.groupby(["key", "route_family"])
               .agg(discontinuing_companies=("Company Name", "nunique"),
                    discontinuing_names=("Company Name", lambda s: "; ".join(sorted(set(s.dropna())))))
               .reset_index())
    markets = markets.merge(disc, on=["key", "route_family"], how="left")
    markets["discontinuing_companies"] = markets["discontinuing_companies"].fillna(0).astype(int)
    markets["pending_discontinuation"] = markets["discontinuing_companies"] > 0
    # Salt-pooled applicant count for the same route (e.g. METHOTREXATE + METHOTREXATE SODIUM).
    markets["n_applicants_any_salt"] = [
        len(sets_base.get((b, rf), set())) for b, rf in zip(markets["base"], markets["route_family"])]

    # ── Transparent watchlist flags (research-informed, not a fitted model) ──
    markets["flag_injectable"] = markets["route_family"] == "Injectable"
    markets["flag_limited"] = markets["limited_competition"]
    markets["flag_mature_offpatent"] = (~markets["any_protected"]) & (markets["years_on_market"] >= MATURE_YEARS)
    markets["flag_discontinuation"] = markets["pending_discontinuation"]
    markets["watch_score"] = markets[list(FLAG_LABELS)].sum(axis=1)
    # Structural score excludes the discontinuation flag, which comes from the same
    # FDA database as the shortage outcome and would leak into any validation.
    markets["structural_score"] = markets[["flag_injectable", "flag_limited", "flag_mature_offpatent"]].sum(axis=1)

    # ── Company sole-source exposure ──────────────────────────────────────────
    sole = markets[markets["n_applicants"] == 1]
    companies = (
        sole.assign(parent=sole["applicants"])
        .groupby("parent")
        .agg(
            sole_source_markets=("Ingredient", "size"),
            off_patent_sole=("sole_source_type", lambda s: (s == "Off-patent sole source").sum()),
            protected_sole=("sole_source_type", lambda s: (s == "Protected (patent/exclusivity)").sum()),
            off_patent_injectable=("route_family",
                                   lambda s: ((s == "Injectable") &
                                              (sole.loc[s.index, "sole_source_type"] == "Off-patent sole source")).sum()),
        )
        .reset_index()
    )
    portfolio = rx.groupby("parent").apply(lambda g: g[["key", "route_family"]].drop_duplicates().shape[0])
    companies["total_markets"] = companies["parent"].map(portfolio).astype(int)
    companies = companies.sort_values(["off_patent_sole", "sole_source_markets"], ascending=False)

    notes = dict(
        n_rx_products=len(products[products["Type"] == "RX"]),
        protected_appl=len(pat_appl | exc_appl),
    )
    return Results(as_of_ts, markets, current, shortage_drugs, companies, shortage, notes)


def association_table(markets: pd.DataFrame, off_patent_only: bool = True) -> pd.DataFrame:
    """Share of markets with a current (exactly matched) shortage, by applicant tier.

    Descriptive only: a single snapshot, small counts, and heavily confounded by
    route (sterile injectables) and price. Not evidence of causation.
    """
    m = markets[~markets["any_protected"]].copy() if off_patent_only else markets.copy()
    m["injectable"] = np.where(m["route_family"] == "Injectable", "Injectable", "Non-injectable")
    t = (m.groupby(["injectable", "tier"])
           .agg(markets=("in_shortage", "size"), in_shortage=("in_shortage", "sum"))
           .reset_index())
    t["shortage_rate_%"] = (100 * t["in_shortage"] / t["markets"]).round(2)
    t["tier"] = pd.Categorical(t["tier"], TIER_ORDER, ordered=True)
    return t.sort_values(["injectable", "tier"])


def rate_by(markets: pd.DataFrame, col: str, bins=None, labels=None, off_patent_only=True) -> pd.DataFrame:
    """Share of markets in shortage by an arbitrary column (optionally binned)."""
    m = markets[~markets["any_protected"]].copy() if off_patent_only else markets.copy()
    g = pd.cut(m[col], bins=bins, labels=labels, right=False) if bins is not None else m[col]
    t = m.groupby(g, observed=False)["in_shortage"].agg(markets="size", in_shortage="sum").reset_index()
    t["shortage_rate_%"] = (100 * t["in_shortage"] / t["markets"].where(t["markets"] > 0)).round(2)
    return t


def route_representation(markets: pd.DataFrame, shortage_drugs: pd.DataFrame) -> pd.DataFrame:
    """Share of all RX markets vs share of shortage drugs, by route family."""
    all_ = markets["route_family"].value_counts(normalize=True)
    r = shortage_drugs["route"].dropna()
    r = r[~r.str.startswith("All routes")]
    sh = r.value_counts(normalize=True)
    out = pd.DataFrame({"share_of_markets_%": 100 * all_, "share_of_shortage_drugs_%": 100 * sh}).fillna(0)
    out["over_representation"] = (out["share_of_shortage_drugs_%"] / out["share_of_markets_%"]).round(2)
    return out.round(1).sort_values("share_of_shortage_drugs_%", ascending=False)


def funnel(markets: pd.DataFrame) -> list[tuple[str, int]]:
    m = markets
    steps = [("All RX markets (ingredient × route)", m)]
    m = m[~m["any_protected"]]; steps.append(("Off-patent (no unexpired patent/exclusivity)", m))
    m = m[m["limited_competition"]]; steps.append(("…with ≤3 approved applicants", m))
    m = m[m["route_family"] == "Injectable"]; steps.append(("…that are injectable", m))
    m = m[m["pending_discontinuation"] | m["in_shortage"]]; steps.append(("…in shortage or facing a discontinuation", m))
    return [(label, len(df)) for label, df in steps]
