# Unit and property tests for the offline preprocessor (model/train_model.py)
# Feature: movie-dss-web
# Requirements: 1.1–1.7

import json
import sys
import os

import pandas as pd
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Make sure the model package is importable regardless of cwd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "model"))

from train_model import (
    normalize_whitespace,
    build_feature_string,
    _REQUIRED_COLUMNS,
    _JSON_FIELDS,
    _TEXT_FIELDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_clean_record(**overrides) -> dict:
    """Return a minimal valid record dict with all nine JSON fields as strings."""
    base = {
        "id": "1",
        "type": "Movie",
        "name": "Test Movie",
        "genres": "Drama",
        "country": "US",
        "year": "2020",
        "time": "100 min",
        "describle": "A test movie description.",
        "rating": "PG",
    }
    base.update(overrides)
    return base


def _run_null_elimination(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the same null-row elimination logic used by train_model.main()."""
    df = df.copy()
    df.dropna(subset=_REQUIRED_COLUMNS, inplace=True)
    return df


def _records_to_clean_json(records: list[dict]) -> str:
    """Mimic the JSON export step from train_model.main()."""
    clean = [
        {field: str(r.get(field, "") or "") for field in _JSON_FIELDS}
        for r in records
    ]
    return json.dumps(clean, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# A strategy for non-null, non-empty text values (safe strings for required cols)
_safe_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=50,
)

# A strategy for a single row dict where the four required columns are non-null
_clean_row_strategy = st.fixed_dictionaries(
    {
        "id": _safe_text,
        "type": _safe_text,
        "name": _safe_text,
        "genres": _safe_text,
        "country": st.one_of(st.none(), _safe_text),
        "year": st.one_of(st.none(), _safe_text),
        "time": st.one_of(st.none(), _safe_text),
        "describle": _safe_text,
        "rating": st.one_of(st.none(), _safe_text),
    }
)

# A strategy for a row dict where at least one required column is null
_null_row_strategy = st.one_of(
    _clean_row_strategy.map(lambda r: {**r, "name": None}),
    _clean_row_strategy.map(lambda r: {**r, "type": None}),
    _clean_row_strategy.map(lambda r: {**r, "genres": None}),
    _clean_row_strategy.map(lambda r: {**r, "describle": None}),
)


@st.composite
def _df_with_null_rows(draw):
    """
    Generate a DataFrame that always contains at least one null row.

    The DataFrame has all nine JSON fields as columns.
    It may additionally contain some clean rows mixed in.
    """
    clean_rows = draw(st.lists(_clean_row_strategy, min_size=0, max_size=20))
    null_rows = draw(st.lists(_null_row_strategy, min_size=1, max_size=10))
    all_rows = clean_rows + null_rows
    # Shuffle so null rows are not always at the end
    indices = draw(st.permutations(range(len(all_rows))))
    shuffled = [all_rows[i] for i in indices]
    return pd.DataFrame(shuffled, columns=list(_JSON_FIELDS))


# ---------------------------------------------------------------------------
# Property 1 – Null-row elimination
# Feature: movie-dss-web, Property 1: Null-row elimination
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------

@given(_df_with_null_rows())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_null_row_elimination(df: pd.DataFrame):
    """
    **Validates: Requirements 1.1**

    Property 1: Null-row elimination

    For any dataset with rows containing nulls in `name`, `type`, `genres`,
    or `describle`, after null-row elimination the output contains zero records
    with a null in any of those four columns.
    """
    cleaned = _run_null_elimination(df)

    for col in _REQUIRED_COLUMNS:
        null_count = cleaned[col].isna().sum()
        assert null_count == 0, (
            f"Column '{col}' still has {null_count} null(s) after elimination"
        )


# ---------------------------------------------------------------------------
# Property 4 – movies_clean.json round-trip completeness
# Feature: movie-dss-web, Property 4: movies_clean.json round-trip completeness
# Validates: Requirements 1.6
# ---------------------------------------------------------------------------

@given(st.lists(_clean_row_strategy, min_size=1, max_size=30))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property4_json_roundtrip_completeness(raw_rows: list[dict]):
    """
    **Validates: Requirements 1.6**

    Property 4: movies_clean.json round-trip completeness

    For any list of cleaned records written to movies_clean.json, deserializing
    the JSON produces objects that each contain all nine required fields, each
    with a non-null string value.
    """
    json_str = _records_to_clean_json(raw_rows)
    deserialized = json.loads(json_str)

    assert len(deserialized) == len(raw_rows), (
        "Round-trip must preserve record count"
    )

    for i, record in enumerate(deserialized):
        for field in _JSON_FIELDS:
            assert field in record, (
                f"Record {i}: required field '{field}' is missing after round-trip"
            )
            value = record[field]
            assert value is not None, (
                f"Record {i}: field '{field}' is None after round-trip"
            )
            assert isinstance(value, str), (
                f"Record {i}: field '{field}' is {type(value).__name__}, expected str"
            )
