import pandas as pd
import pytest

from lucky.edgar import eps_facts, normalize_name, ttm_eps, unit_factors


def fact(start, end, val, filed, form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form, "accn": filed}


def company(*facts):
    return {
        "facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": list(facts)}}}}
    }


YEAR1 = [
    fact("2019-01-01", "2019-03-31", 1.0, "2019-05-01"),
    fact("2019-04-01", "2019-06-30", 1.0, "2019-08-01"),
    fact("2019-07-01", "2019-09-30", 1.0, "2019-11-01"),
    fact("2019-01-01", "2019-12-31", 5.0, "2020-02-20", "10-K"),
]


def test_fourth_quarter_comes_from_the_annual_figure_and_ttm_starts_then():
    t = ttm_eps(eps_facts(company(*YEAR1)))
    assert len(t) == 1
    row = t.iloc[0]
    assert row["end"] == pd.Timestamp("2019-12-31")
    assert row["eps_ttm"] == 5.0
    assert row["available"] == pd.Timestamp("2020-02-21")  # the business day after filing


def test_rolling_ttm_from_four_quarters():
    nxt = [
        fact("2020-01-01", "2020-03-31", 2.0, "2020-05-01"),
        fact("2019-01-01", "2019-03-31", 1.0, "2020-05-01"),  # comparative, same value
    ]
    t = ttm_eps(eps_facts(company(*YEAR1, *nxt)))
    last = t.iloc[-1]
    assert last["end"] == pd.Timestamp("2020-03-31")
    assert last["eps_ttm"] == pytest.approx(1 + 1 + 2 + 2)  # Q2, Q3, Q4 (5-3), new Q1


def test_a_split_converts_old_eps_to_todays_units():
    # A 2-for-1 split after year 1: the next 10-K restates year 1 at half.
    year2 = [
        fact("2020-01-01", "2020-12-31", 3.0, "2021-02-20", "10-K"),
        fact("2019-01-01", "2019-12-31", 2.5, "2021-02-20", "10-K"),
    ]
    facts = eps_facts(company(*YEAR1, *year2))
    u = unit_factors(facts)
    assert u[pd.Timestamp("2020-02-20")] == 2.0 and u[pd.Timestamp("2021-02-20")] == 1.0
    t = ttm_eps(facts).set_index("end")
    # As first reported (5.0) but in post-split units, so it matches split-adjusted prices.
    assert t.loc[pd.Timestamp("2019-12-31"), "eps_ttm"] == pytest.approx(2.5)
    # Known on its original date: the conversion doesn't move when it was known.
    assert t.loc[pd.Timestamp("2019-12-31"), "available"] == pd.Timestamp("2020-02-21")


def test_restatements_are_not_mistaken_for_splits():
    year2 = [
        fact("2020-01-01", "2020-12-31", 3.0, "2021-02-20", "10-K"),
        fact("2019-01-01", "2019-12-31", 4.6, "2021-02-20", "10-K"),  # restated down 8%
    ]
    u = unit_factors(eps_facts(company(*YEAR1, *year2)))
    assert (u == 1.0).all()


def test_first_reported_value_wins_over_later_restatement():
    year2 = [
        fact("2020-01-01", "2020-12-31", 3.0, "2021-02-20", "10-K"),
        fact("2019-01-01", "2019-12-31", 4.6, "2021-02-20", "10-K"),
    ]
    t = ttm_eps(eps_facts(company(*YEAR1, *year2))).set_index("end")
    assert t.loc[pd.Timestamp("2019-12-31"), "eps_ttm"] == 5.0


def test_names_normalize_across_sources():
    assert normalize_name("Twitter, Inc. COM") == normalize_name("TWITTER INC")
    assert normalize_name("XILINX INC /DE/") == "XILINX"
    assert normalize_name("AT&T Inc.") == "AT AND T"
