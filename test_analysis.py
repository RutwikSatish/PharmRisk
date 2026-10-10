"""Run with:  pytest -q"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analysis as a  # noqa: E402

DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Name normalisation ──────────────────────────────────────────────────────
@pytest.mark.parametrize("name,expected", [
    ("Bupivacaine Hydrochloride Injection", {"BUPIVACAINE HYDROCHLORIDE"}),
    ("Dextrose Monohydrate 5% Injection", {"DEXTROSE"}),
    ("Sodium Chloride 0.9% Injection", {"SODIUM CHLORIDE"}),
    ("Cefotaxime Sodium Powder, for Solution", {"CEFOTAXIME SODIUM"}),
    ("Rifapentine Tablet, Film Coated", {"RIFAPENTINE"}),
    ("Quinapril/Hydrochlorothiazide Tablet", {"QUINAPRIL", "HYDROCHLOROTHIAZIDE"}),
    ("Acetaminophen; Oxycodone Hydrochloride Tablet", {"ACETAMINOPHEN", "OXYCODONE HYDROCHLORIDE"}),
    ("Sterile Water Injection", {"STERILE WATER FOR INJECTION"}),
    ("Sterile Water Irrigant", {"STERILE WATER FOR IRRIGATION"}),
])
def test_shortage_key(name, expected):
    assert a.ingredient_key(name, "shortage") == frozenset(expected)


def test_combination_products_are_not_reduced_to_first_component():
    # The original app split on ';'/',' and kept only the first component,
    # so this combination matched plain EPINEPHRINE BITARTRATE.
    k = a.ingredient_key("Epinephrine Bitartrate, Lidocaine Hydrochloride Injection", "shortage")
    assert k == frozenset({"EPINEPHRINE BITARTRATE", "LIDOCAINE HYDROCHLORIDE"})


def test_ob_key_keeps_commas_inside_chemical_names():
    k = a.ingredient_key("DEXTROSE; POTASSIUM PHOSPHATE, DIBASIC", "ob")
    assert k == frozenset({"DEXTROSE", "POTASSIUM PHOSPHATE, DIBASIC"})


def test_base_key_strips_trailing_salts_only():
    assert a.base_key(frozenset({"QUINAPRIL HYDROCHLORIDE"})) == frozenset({"QUINAPRIL"})
    # single-word names are never emptied
    assert a.base_key(frozenset({"SODIUM"})) == frozenset({"SODIUM"})


# ── Route families ──────────────────────────────────────────────────────────
def test_route_families():
    assert a.ob_route_families("TABLET;ORAL") == ["Oral"]
    assert a.ob_route_families("INJECTABLE;INTRAMUSCULAR, INTRAVENOUS") == ["Injectable"]
    assert a.ob_route_families("LIQUID;N/A", "STERILE WATER FOR INJECTION") == ["Injectable"]
    assert a.shortage_route_family("Lorazepam Injection", "") == "Injectable"
    assert a.shortage_route_family("Clonazepam Tablet", "") == "Oral"


def test_tiers():
    assert a.applicant_tier(1).startswith("1")
    assert a.applicant_tier(2).startswith("2")
    assert a.applicant_tier(4).startswith("3")
    assert a.applicant_tier(9).startswith("5")


# ── Pipeline invariants on the bundled snapshot ─────────────────────────────
@pytest.fixture(scope="module")
def res():
    if a.missing_files(DATA_DIR):
        pytest.skip("data files not present")
    return a.build(a.load_raw(DATA_DIR))


def test_markets_unique(res):
    assert not res.markets.duplicated(["key", "route_family"]).any()


def test_equal_share_hhi_consistent(res):
    m = res.markets
    assert ((m["hhi_equal_share"] == 10_000) == (m["n_applicants"] == 1)).all()


def test_sole_source_split_is_exhaustive(res):
    sole = res.markets[res.markets["n_applicants"] == 1]
    assert set(sole["sole_source_type"]) <= {"Protected (patent/exclusivity)", "Off-patent sole source"}


def test_shortage_match_rate_floor(res):
    # Regression guard: the original matcher reached ~76% of unique drugs.
    d = res.shortage_drugs
    assert d["n_applicants"].notna().mean() >= 0.85


def test_shortage_drug_rows_unique(res):
    assert not res.shortage_drugs["Generic Name"].duplicated().any()


# ── New metrics ─────────────────────────────────────────────────────────────
def test_watch_score_is_sum_of_flags(res):
    m = res.markets
    assert (m["watch_score"] == m[list(a.FLAG_LABELS)].sum(axis=1)).all()
    assert m["structural_score"].between(0, 3).all()


def test_salt_pooled_count_is_superset(res):
    assert (res.markets["n_applicants_any_salt"] >= res.markets["n_applicants"]).all()


def test_funnel_is_monotone(res):
    counts = [n for _, n in a.funnel(res.markets)]
    assert counts == sorted(counts, reverse=True)


def test_route_representation_shares_sum_to_100(res):
    rr = a.route_representation(res.markets, res.shortage_drugs)
    assert abs(rr["share_of_markets_%"].sum() - 100) < 1
    assert abs(rr["share_of_shortage_drugs_%"].sum() - 100) < 1


def test_rate_by_counts_match(res):
    t = a.rate_by(res.markets, "structural_score", off_patent_only=False)
    assert t["markets"].sum() == len(res.markets)
    assert t["in_shortage"].sum() == res.markets["in_shortage"].sum()


def test_years_on_market_non_negative(res):
    assert (res.markets["years_on_market"].dropna() >= 0).all()
