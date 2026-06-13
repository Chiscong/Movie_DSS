# Unit and property tests for the Lambda recommender (backend/lambda_function.py)
# Feature: movie-dss-web
# Requirements: 2.1–2.14

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from lambda_function import _compute_duration_score, _compute_metadata_score

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Property 8: Duration score exactness
# Validates: Requirements 2.6
# Feature: movie-dss-web, Property 8: Duration score exactness
# ---------------------------------------------------------------------------

ALLOWED_DURATIONS = ("Short", "Medium", "Long")

# Strategy for any string that may or may not be an allowed duration value
any_string = st.one_of(
    st.just("Short"),
    st.just("Medium"),
    st.just("Long"),
    st.just(None),
    st.text(),
)

# Strategy specifically for allowed duration values
allowed_duration_st = st.sampled_from(ALLOWED_DURATIONS)

# Strategy for movie categories (same three allowed values plus None)
movie_category_st = st.one_of(
    st.sampled_from(["Short", "Medium", "Long"]),
    st.just(None),
)


@given(movie_category=movie_category_st, query_duration=allowed_duration_st)
@settings(max_examples=200)
def test_property8_score_is_1_iff_exact_match_and_valid_query(movie_category, query_duration):
    """Property 8: Duration score exactness — match branch.

    When query_duration is one of the three allowed values, the score is 1.0
    iff movie_category == query_duration, and 0.0 otherwise.

    Validates: Requirements 2.6
    """
    score = _compute_duration_score(movie_category, query_duration)
    if movie_category == query_duration:
        assert score == 1.0, (
            f"Expected 1.0 for matching category={movie_category!r} "
            f"and query={query_duration!r}, got {score}"
        )
    else:
        assert score == 0.0, (
            f"Expected 0.0 for non-matching category={movie_category!r} "
            f"and query={query_duration!r}, got {score}"
        )


@given(movie_category=movie_category_st, query_duration=any_string)
@settings(max_examples=200)
def test_property8_score_is_0_when_query_not_in_allowed_values(movie_category, query_duration):
    """Property 8: Duration score exactness — invalid/absent query branch.

    When query_duration is None or not one of the three allowed values,
    the score is always 0.0 regardless of movie_category.

    Validates: Requirements 2.6
    """
    assume(query_duration not in ALLOWED_DURATIONS)

    score = _compute_duration_score(movie_category, query_duration)
    assert score == 0.0, (
        f"Expected 0.0 for invalid/absent query_duration={query_duration!r} "
        f"with category={movie_category!r}, got {score}"
    )


@given(
    movie_category=movie_category_st,
    query_duration=allowed_duration_st,
)
@settings(max_examples=200)
def test_property8_score_is_binary(movie_category, query_duration):
    """Property 8: Duration score exactness — score is always 0.0 or 1.0.

    The function must only return exactly 0.0 or 1.0; no intermediate values.

    Validates: Requirements 2.6
    """
    score = _compute_duration_score(movie_category, query_duration)
    assert score in (0.0, 1.0), (
        f"Expected score to be 0.0 or 1.0, got {score} for "
        f"category={movie_category!r}, query={query_duration!r}"
    )


# ---------------------------------------------------------------------------
# Property 9: Metadata score fraction
# Validates: Requirements 2.7
# Feature: movie-dss-web, Property 9: Metadata score fraction
# ---------------------------------------------------------------------------

# Strategy for non-empty strings (field values in query / movie records)
nonempty_text_st = st.text(min_size=1, max_size=30).filter(lambda s: s.strip() != "")

# Strategy for a query that provides at least one of type/country (non-empty)
query_with_metadata_st = st.fixed_dictionaries(
    {},
    optional={
        "type": nonempty_text_st,
        "country": nonempty_text_st,
    },
).filter(lambda q: bool(q.get("type")) or bool(q.get("country")))

# Strategy for a movie record that always has type and country fields
movie_record_st = st.fixed_dictionaries(
    {
        "type": nonempty_text_st,
        "country": nonempty_text_st,
    }
)


@given(query=query_with_metadata_st, movie=movie_record_st)
@settings(max_examples=200)
def test_property9_metadata_score_is_fraction_of_matching_fields(query, movie):
    """Property 9: Metadata score fraction — correct fraction.

    For any query providing one or both of `type` and `country`, and for any
    movie record, the score equals the count of provided fields that exactly
    match the movie divided by the total count of provided fields.

    Validates: Requirements 2.7
    """
    # Compute the expected score manually
    provided_fields = [f for f in ("type", "country") if query.get(f)]
    matches = sum(1 for f in provided_fields if movie.get(f) == query[f])
    expected = matches / len(provided_fields)

    score = _compute_metadata_score(movie, query)

    assert score == pytest.approx(expected), (
        f"Expected metadata_score={expected} for query={query!r} "
        f"and movie={movie!r}, got {score}"
    )


@given(query=query_with_metadata_st, movie=movie_record_st)
@settings(max_examples=200)
def test_property9_metadata_score_in_bounds(query, movie):
    """Property 9: Metadata score fraction — score is in [0.0, 1.0].

    For any query providing one or both of `type` and `country`, the
    metadata score is always a float in the closed interval [0.0, 1.0].

    Validates: Requirements 2.7
    """
    score = _compute_metadata_score(movie, query)
    assert 0.0 <= score <= 1.0, (
        f"Expected score in [0.0, 1.0], got {score} for "
        f"query={query!r} and movie={movie!r}"
    )


@given(movie=movie_record_st, extra=st.dictionaries(nonempty_text_st, nonempty_text_st))
@settings(max_examples=200)
def test_property9_metadata_score_zero_when_no_fields(movie, extra):
    """Property 9: Metadata score fraction — returns 0.0 when neither type nor country provided.

    When the query does not contain a non-empty `type` or `country`, the
    metadata score must be 0.0 regardless of any other fields present.

    Validates: Requirements 2.7
    """
    # Build a query that explicitly has no type or country
    query = {k: v for k, v in extra.items() if k not in ("type", "country")}
    score = _compute_metadata_score(movie, query)
    assert score == 0.0, (
        f"Expected 0.0 when neither type nor country provided, "
        f"got {score} for query={query!r}"
    )
