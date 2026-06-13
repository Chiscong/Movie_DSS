from __future__ import annotations

import datetime
import io
import json
import logging
import os
import re
import sys
import time
import traceback

import boto3
import botocore.exceptions
import joblib
from sklearn.metrics.pairwise import cosine_similarity


# ---------------------------------------------------------------------------
# Module-level cached artifacts (one load per Lambda container lifetime)
# ---------------------------------------------------------------------------

_vectorizer = None      # TfidfVectorizer loaded from S3
_movie_vectors = None   # scipy sparse matrix loaded from S3
_movies = None          # list[dict] loaded from movies_clean.json

# CORS headers included on every response
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a request body fails validation."""

# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def _categorize_duration(time_str: str) -> str | None:
    """Parse a raw ``time`` field and return a duration category.

    Rules:
      - Extract the integer before " min" (case-insensitive).
      - If no " min" pattern is found (e.g. "3 Seasons"), return ``None``.
      - minutes < 90              → "Short"
      - 90 <= minutes <= 120      → "Medium"
      - minutes > 120             → "Long"

    Args:
        time_str: Raw duration string from the dataset (e.g. "125 min").

    Returns:
        "Short", "Medium", "Long", or ``None`` if the pattern is not found.
    """
    match = re.search(r'(\d+)\s*min', time_str, re.IGNORECASE)
    if not match:
        return None
    minutes = int(match.group(1))
    if minutes < 90:
        return "Short"
    elif minutes <= 120:
        return "Medium"
    else:
        return "Long"


def _compute_year_score(movie_year: str | int, query_year: int | None) -> float:
    """Compute a proximity score between the movie release year and the query year.

    Returns a float in [0.0, 1.0].

    - If ``query_year`` is ``None``, returns 0.0.
    - Otherwise: ``1.0 - min(abs(movie_year - query_year), 10) / 10.0``

    Examples::

        same year       → 1.0
        1 year apart    → 0.9
        5 years apart   → 0.5
        10+ years apart → 0.0

    Args:
        movie_year: Release year of the movie (coerced to int).
        query_year: User-supplied year preference, or ``None`` if absent.

    Returns:
        Float in [0.0, 1.0].
    """
    if query_year is None:
        return 0.0
    diff = abs(int(movie_year) - int(query_year))
    return 1.0 - min(diff, 10) / 10.0


def _compute_duration_score(
    movie_category: str | None,
    query_duration: str | None,
) -> float:
    """Return 1.0 if the movie duration category exactly matches the query duration.

    Returns 0.0 in all other cases, including when ``query_duration`` is absent,
    ``None``, or not one of the three allowed values.

    Args:
        movie_category: One of "Short", "Medium", "Long", or ``None``.
        query_duration: User-supplied duration preference, or ``None`` if absent.

    Returns:
        1.0 on exact match, 0.0 otherwise.
    """
    if not query_duration or query_duration not in ("Short", "Medium", "Long"):
        return 0.0
    return 1.0 if movie_category == query_duration else 0.0


def _compute_metadata_score(movie: dict, query: dict) -> float:
    """Compute a metadata match fraction for ``type`` and ``country`` fields.

    Counts how many of the provided metadata fields exactly match the movie
    record, then divides by the total number of provided fields.

    Returns 0.0 if neither ``type`` nor ``country`` is present in the query.

    Examples::

        query has type="Movie", country="US"; movie matches both → 1.0
        query has type="Movie" only;          movie matches      → 1.0
        query has type="Movie", country="US"; only type matches  → 0.5
        query has type="Movie", country="US"; neither matches    → 0.0

    Args:
        movie: Cleaned movie record dict (from ``movies_clean.json``).
        query: Validated user query dict.

    Returns:
        Float in [0.0, 1.0].
    """
    fields: list[tuple[str, str]] = []
    if query.get("type"):
        fields.append(("type", query["type"]))
    if query.get("country"):
        fields.append(("country", query["country"]))
    if not fields:
        return 0.0
    matches = sum(1 for field, value in fields if movie.get(field) == value)
    return matches / len(fields)


def _compute_composite_score(
    cos_sim: float,
    year_score: float,
    duration_score: float,
    metadata_score: float,
) -> float:
    """Combine sub-scores into the final composite relevance score.

    Formula::

        score = 0.7 * cos_sim
              + 0.1 * year_score
              + 0.1 * duration_score
              + 0.1 * metadata_score

    All inputs are expected to be in [0, 1]; the output is therefore also in [0, 1].

    Args:
        cos_sim:        TF-IDF cosine similarity score.
        year_score:     Year proximity score from ``_compute_year_score``.
        duration_score: Duration match score from ``_compute_duration_score``.
        metadata_score: Metadata match score from ``_compute_metadata_score``.

    Returns:
        Weighted composite float in [0.0, 1.0].
    """
    return (
        0.7 * cos_sim
        + 0.1 * year_score
        + 0.1 * duration_score
        + 0.1 * metadata_score
    )


# ---------------------------------------------------------------------------
# Validation layer
# ---------------------------------------------------------------------------

def _validate_request(body: dict) -> dict:
    """Validate and coerce an incoming request body.

    Required fields
    ---------------
    - ``type``  — must be present and non-empty.
    - ``genre`` — must be present and non-empty.

    Optional fields (validated only when present)
    ----------------------------------------------
    - ``release_year`` — integer in [1900, current_year].
    - ``duration``     — one of ``"Short"``, ``"Medium"``, ``"Long"``.
    - ``top_k``        — integer in [1, 10].

    Args:
        body: Raw decoded JSON dict from the request.

    Returns:
        The validated (and coerced where appropriate) body dict.

    Raises:
        ValidationError: On any validation failure.
    """
    # --- required fields ---------------------------------------------------
    if not body.get("type"):
        raise ValidationError("Missing required field: type")
    if not body.get("genre"):
        raise ValidationError("Missing required field: genre")

    # --- release_year (optional) -------------------------------------------
    if "release_year" in body and body["release_year"] != "" and body["release_year"] is not None:
        current_year = datetime.datetime.utcnow().year
        try:
            year = int(body["release_year"])
        except (ValueError, TypeError):
            raise ValidationError(
                f"release_year must be an integer in [1900, {current_year}]"
            )
        if year < 1900 or year > current_year:
            raise ValidationError(
                f"release_year must be an integer in [1900, {current_year}]"
            )
        body["release_year"] = year

    # --- duration (optional) -----------------------------------------------
    if "duration" in body and body["duration"] != "" and body["duration"] is not None:
        allowed = ("Short", "Medium", "Long")
        if body["duration"] not in allowed:
            raise ValidationError(
                f"duration must be one of {allowed}"
            )

    # --- top_k (optional) --------------------------------------------------
    if "top_k" in body and body["top_k"] != "" and body["top_k"] is not None:
        try:
            top_k = int(body["top_k"])
        except (ValueError, TypeError):
            raise ValidationError("top_k must be an integer in [1, 10]")
        if top_k < 1 or top_k > 10:
            raise ValidationError("top_k must be an integer in [1, 10]")
        body["top_k"] = top_k

    return body


# ---------------------------------------------------------------------------
# Query-building layer
# ---------------------------------------------------------------------------

def _build_query_string(query: dict) -> str:
    """Build a whitespace-joined query string from validated query fields.

    Collects values from ``type``, ``genre``, ``country``, ``release_year``,
    ``duration``, and ``keyword`` (in that order).  Each value is cast to
    ``str`` and stripped; absent, ``None``, or empty values are skipped.

    Args:
        query: Validated user-query dict (output of ``_validate_request``).

    Returns:
        A single space-joined string of the non-empty field values.
    """
    field_names = ("type", "genre", "country", "release_year", "duration", "keyword")
    tokens: list[str] = []
    for field in field_names:
        value = query.get(field)
        if value is None:
            continue
        token = str(value).strip()
        if token:
            tokens.append(token)
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Artifact loading layer  (Task 7.1)
# ---------------------------------------------------------------------------

def _load_artifacts() -> None:
    """Load ML artifacts from S3 into module-level globals (once per container).

    Reads ``ARTIFACTS_BUCKET`` and ``MODEL_PREFIX`` from environment variables.
    The ``MODEL_PREFIX`` is expected to include a trailing slash, e.g. ``"model/"``.

    Artifacts loaded:
    - ``{MODEL_PREFIX}vectorizer.pkl``     → ``_vectorizer``
    - ``{MODEL_PREFIX}movie_vectors.pkl``  → ``_movie_vectors``
    - ``{MODEL_PREFIX}movies_clean.json``  → ``_movies``

    Globals are set only when currently ``None`` to enable container-lifetime
    caching (warm Lambda re-use).

    Raises:
        botocore.exceptions.ClientError: Re-raised after logging the full
            traceback so the caller can return HTTP 500.
    """
    global _vectorizer, _movie_vectors, _movies

    if _vectorizer is not None and _movie_vectors is not None and _movies is not None:
        return  # already loaded — warm container, skip S3 calls

    bucket = os.environ["ARTIFACTS_BUCKET"]
    prefix = os.environ["MODEL_PREFIX"]  # e.g. "model/"

    s3 = boto3.client("s3")

    t_start = time.time()
    try:
        # --- vectorizer.pkl ------------------------------------------------
        if _vectorizer is None:
            obj = s3.get_object(Bucket=bucket, Key=f"{prefix}vectorizer.pkl")
            _vectorizer = joblib.load(io.BytesIO(obj["Body"].read()))

        # --- movie_vectors.pkl ---------------------------------------------
        if _movie_vectors is None:
            obj = s3.get_object(Bucket=bucket, Key=f"{prefix}movie_vectors.pkl")
            _movie_vectors = joblib.load(io.BytesIO(obj["Body"].read()))

        # --- movies_clean.json ---------------------------------------------
        if _movies is None:
            obj = s3.get_object(Bucket=bucket, Key=f"{prefix}movies_clean.json")
            _movies = json.loads(obj["Body"].read().decode("utf-8"))

    except botocore.exceptions.ClientError:
        print(
            f"[ERROR] Failed to load artifacts from s3://{bucket}/{prefix}\n"
            + traceback.format_exc()
        )
        raise  # propagate → caller returns HTTP 500

    elapsed_ms = (time.time() - t_start) * 1000
    print(
        f"[INFO] Artifacts loaded in {elapsed_ms:.1f} ms "
        f"from s3://{bucket}/{prefix}"
    )


# ---------------------------------------------------------------------------
# Lambda entry point  (Task 7.2)
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point.

    Handles ``POST /recommend`` requests forwarded by API Gateway (Lambda proxy
    integration).  Loads ML artifacts on first invocation (cold start) and
    reuses them on subsequent warm invocations.

    Args:
        event:   API Gateway proxy event dict.
        context: Lambda context object (unused).

    Returns:
        API Gateway proxy response dict (``statusCode``, ``headers``, ``body``).
    """
    try:
        # ------------------------------------------------------------------ #
        # 1. Handle CORS pre-flight                                           #
        # ------------------------------------------------------------------ #
        if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS" \
                or event.get("httpMethod") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": "",
            }

        # ------------------------------------------------------------------ #
        # 2. Parse request body                                               #
        # ------------------------------------------------------------------ #
        raw_body = event.get("body") or "{}"
        try:
            body: dict = json.loads(raw_body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Request body is not valid JSON"}),
            }

        # ------------------------------------------------------------------ #
        # 3. Validate request                                                 #
        # ------------------------------------------------------------------ #
        try:
            query = _validate_request(body)
        except ValidationError as exc:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": str(exc)}),
            }

        # ------------------------------------------------------------------ #
        # 4. Load artifacts (once per container lifetime)                     #
        # ------------------------------------------------------------------ #
        _load_artifacts()

        # ------------------------------------------------------------------ #
        # 5. Build query vector                                               #
        # ------------------------------------------------------------------ #
        t_infer_start = time.time()

        q = _build_query_string(query)
        query_vector = _vectorizer.transform([q])

        # ------------------------------------------------------------------ #
        # 6. Cosine similarity against all movies                             #
        # ------------------------------------------------------------------ #
        cos_scores = cosine_similarity(query_vector, _movie_vectors).flatten()

        # ------------------------------------------------------------------ #
        # 7. Compute composite scores                                         #
        # ------------------------------------------------------------------ #
        top_k: int = int(query.get("top_k") or 10)

        scored: list[dict] = []
        for idx, movie in enumerate(_movies):
            cos_sim = float(cos_scores[idx])
            year_score = _compute_year_score(movie["year"], query.get("release_year"))
            duration_score = _compute_duration_score(
                _categorize_duration(movie["time"]), query.get("duration")
            )
            metadata_score = _compute_metadata_score(movie, query)
            composite = _compute_composite_score(
                cos_sim, year_score, duration_score, metadata_score
            )
            scored.append({**movie, "score": composite})

        # ------------------------------------------------------------------ #
        # 8. Sort descending by score and take top_k                         #
        # ------------------------------------------------------------------ #
        scored.sort(key=lambda m: m["score"], reverse=True)
        top_results = scored[:top_k]

        # ------------------------------------------------------------------ #
        # 9. Attach 1-based rank                                              #
        # ------------------------------------------------------------------ #
        results = []
        for rank, movie in enumerate(top_results, start=1):
            results.append({**movie, "rank": rank})

        # ------------------------------------------------------------------ #
        # 10. Structured logging (no keyword field)                           #
        # ------------------------------------------------------------------ #
        elapsed_infer_ms = (time.time() - t_infer_start) * 1000
        print(
            f"[INFO] recommendation request — "
            f"type={query.get('type')!r} "
            f"genre={query.get('genre')!r} "
            f"country={query.get('country')!r} "
            f"release_year={query.get('release_year')!r} "
            f"duration={query.get('duration')!r} "
            f"top_k={top_k} "
            f"result_count={len(results)} "
            f"compute_ms={elapsed_infer_ms:.1f}"
        )

        # ------------------------------------------------------------------ #
        # 11. Return success response                                         #
        # ------------------------------------------------------------------ #
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "success", "results": results}),
        }

    except Exception:  # noqa: BLE001
        # Top-level safety net — log full traceback to CloudWatch, return 500
        print("[ERROR] Unhandled exception in lambda_handler\n" + traceback.format_exc())
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Internal server error"}),
        }
