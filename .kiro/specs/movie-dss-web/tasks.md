# Implementation Plan: Movie DSS Web

## Overview

Implement the Movie Decision Support System as a serverless web application on AWS. The build order follows data dependencies: offline ML pipeline first, then the Lambda backend, then the static frontend, then tests, then deployment documentation.

All Python code targets **Python 3.11**. Tests use **pytest** and **Hypothesis** for property-based testing. Frontend is vanilla HTML/CSS/JS with no build toolchain.

---

## Tasks

- [x] 1. Set up project structure and Python test framework
  - Create empty `__init__.py` files so that `tests/unit/` and `tests/integration/` are importable packages
  - Create `tests/unit/test_preprocessor.py` and `tests/unit/test_recommender.py` as empty stubs
  - Create `tests/integration/test_api_integration.py` as an empty stub
  - Create `backend/requirements.txt` with pinned dependencies: `scikit-learn==1.4.2`, `numpy==1.26.4`, `joblib==1.4.2`, `boto3==1.34.84`, `scipy==1.13.0`
  - Create a top-level `requirements-dev.txt` with test dependencies: `pytest==8.2.0`, `hypothesis==6.100.1`, `pytest-cov==5.0.0`
  - _Requirements: 1.1–1.7, 2.1–2.14_

- [x] 2. Implement the offline preprocessor (`model/train_model.py`)
  - [x] 2.1 Implement CSV reading and null-row elimination
    - Read `data/netflix_full.csv` with `pandas.read_csv()`
    - Drop rows with null in `name`, `type`, `genres`, or `describle`
    - Wrap in a top-level try/except; on any exception print a descriptive error and call `sys.exit(1)`
    - _Requirements: 1.1, 1.7_

  - [x] 2.2 Implement whitespace normalization helper
    - Write a pure function `normalize_whitespace(text: str) -> str` that strips leading/trailing spaces and collapses any internal whitespace sequence to a single space using `re.sub(r'\s+', ' ', text.strip())`
    - Apply it to all eight text fields: `name`, `type`, `genres`, `country`, `year`, `time`, `describle`, `rating`
    - _Requirements: 1.2_

  - [ ]* 2.3 Write property test for whitespace normalization (Property 2)
    - **Property 2: Whitespace normalization**
    - *For any* text field value containing arbitrary whitespace sequences, the normalized output has no leading/trailing whitespace and no consecutive whitespace characters
    - Use `hypothesis.strategies.text()` with whitespace characters injected
    - **Validates: Requirements 1.2**
    - `# Feature: movie-dss-web, Property 2: Whitespace normalization`

  - [x] 2.4 Implement feature corpus construction
    - Write a pure function `build_feature_string(record: dict) -> str` that concatenates `type`, `genres`, `country`, `year`, and `describle` joined by a single space
    - _Requirements: 1.3_

  - [ ]* 2.5 Write property test for feature corpus construction (Property 3)
    - **Property 3: Feature corpus construction**
    - *For any* cleaned record, the feature string equals `f"{type} {genres} {country} {year} {describle}"` with no leading/trailing space
    - **Validates: Requirements 1.3**
    - `# Feature: movie-dss-web, Property 3: Feature corpus construction`

  - [x] 2.6 Implement TF-IDF training and artifact serialization
    - Instantiate `TfidfVectorizer(analyzer='word', ngram_range=(1,2), min_df=1, stop_words='english')`
    - Call `.fit(corpus)` and serialize with `joblib.dump` to `model/vectorizer.pkl`
    - Call `.transform(corpus)` and serialize the sparse matrix to `model/movie_vectors.pkl`
    - _Requirements: 1.4, 1.5_

  - [x] 2.7 Implement cleaned JSON export
    - Serialize the cleaned records as a JSON array to `model/movies_clean.json`
    - Each record must contain exactly these nine string fields: `id`, `type`, `name`, `genres`, `country`, `year`, `time`, `describle`, `rating`
    - _Requirements: 1.6_

  - [x] 2.8 Write property tests for null-row elimination and JSON round-trip (Properties 1 and 4)
    - **Property 1: Null-row elimination**
    - *For any* dataset with rows containing nulls in `name`, `type`, `genres`, or `describle`, after the Preprocessor runs the output contains zero records with a null in any of those four columns
    - **Property 4: movies_clean.json round-trip completeness**
    - *For any* cleaned record written to `movies_clean.json`, deserializing it produces an object with all nine required fields, each a non-null string
    - Use `hypothesis` to generate synthetic DataFrames with injected null rows
    - **Validates: Requirements 1.1, 1.6**
    - `# Feature: movie-dss-web, Property 1: Null-row elimination`
    - `# Feature: movie-dss-web, Property 4: movies_clean.json round-trip completeness`

- [ ] 3. Checkpoint — Preprocessor
  - Run `python model/train_model.py` and verify that `model/vectorizer.pkl`, `model/movie_vectors.pkl`, and `model/movies_clean.json` are created without errors
  - Run `pytest tests/unit/test_preprocessor.py -v` and ensure all tests pass
  - Ask the user if any questions arise before continuing

- [x] 4. Implement Lambda scoring pure functions (`backend/lambda_function.py` — scoring layer)
  - [x] 4.1 Implement `_categorize_duration(time_str: str) -> str | None`
    - Extract integer minutes with `re.search(r'(\d+)\s*min', time_str, re.IGNORECASE)`
    - Return `"Short"` if minutes < 90, `"Medium"` if 90–120, `"Long"` if > 120, `None` if no match
    - _Requirements: 2.6_

  - [x] 4.2 Implement `_compute_year_score(movie_year, query_year) -> float`
    - Return `0.0` if `query_year` is `None`
    - Otherwise return `1.0 - min(abs(int(movie_year) - int(query_year)), 10) / 10.0`
    - _Requirements: 2.5_

  - [ ]* 4.3 Write property test for year score (Property 7)
    - **Property 7: Year score monotonicity and bounds**
    - *For any* pair of integer years, the score is in [0.0, 1.0], equals 1.0 when years are identical, equals 0.0 when the absolute difference is ≥ 10, and decreases monotonically as the difference increases from 0 to 10
    - Use `@given(st.integers(1900, 2030), st.integers(1900, 2030))` with `@settings(max_examples=200)`
    - **Validates: Requirements 2.5**
    - `# Feature: movie-dss-web, Property 7: Year score monotonicity and bounds`

  - [x] 4.4 Implement `_compute_duration_score(movie_category, query_duration) -> float`
    - Return `1.0` if `movie_category == query_duration` and `query_duration in ("Short","Medium","Long")`; return `0.0` in all other cases
    - _Requirements: 2.6_

  - [x] 4.5 Write property test for duration score (Property 8)
    - **Property 8: Duration score exactness**
    - *For any* movie category and any query duration, the score is 1.0 iff both are equal and query_duration is one of the three allowed values; it is 0.0 in all other cases
    - **Validates: Requirements 2.6**
    - `# Feature: movie-dss-web, Property 8: Duration score exactness`

  - [x] 4.6 Implement `_compute_metadata_score(movie: dict, query: dict) -> float`
    - Collect `type` and `country` from query (only if non-empty); count how many match movie fields; divide by count
    - Return `0.0` if neither field is present
    - _Requirements: 2.7_

  - [x] 4.7 Write property test for metadata score (Property 9)
    - **Property 9: Metadata score fraction**
    - *For any* query providing one or both of `type` and `country`, and *for any* movie record, the score equals the fraction of provided fields that exactly match the movie and is in [0.0, 1.0]
    - **Validates: Requirements 2.7**
    - `# Feature: movie-dss-web, Property 9: Metadata score fraction`

  - [x] 4.8 Implement `_compute_composite_score(cos_sim, year_score, duration_score, metadata_score) -> float`
    - Return `0.7 * cos_sim + 0.1 * year_score + 0.1 * duration_score + 0.1 * metadata_score`
    - _Requirements: 2.4_

  - [ ]* 4.9 Write property test for composite score formula (Property 6)
    - **Property 6: Composite score formula invariant**
    - *For any* four floats each in [0, 1], the composite score equals exactly `0.7 * c + 0.1 * y + 0.1 * d + 0.1 * m` and is in [0.0, 1.0]
    - **Validates: Requirements 2.4**
    - `# Feature: movie-dss-web, Property 6: Composite score formula invariant`

- [ ] 5. Checkpoint — Scoring functions
  - Run `pytest tests/unit/test_recommender.py -v -k "score"` and ensure all scoring property tests pass
  - Ask the user if any questions arise before continuing

- [ ] 6. Implement Lambda request validation and query building (`backend/lambda_function.py` — validation layer)
  - [x] 6.1 Implement `ValidationError` exception class and `_validate_request(body: dict) -> dict`
    - Raise `ValidationError("Missing required field: type")` if `type` absent or empty
    - Raise `ValidationError("Missing required field: genre")` if `genre` absent or empty
    - Validate `release_year` is an integer in [1900, current_year] if present; raise `ValidationError` otherwise
    - Validate `duration` is one of `"Short"`, `"Medium"`, `"Long"` if present; raise `ValidationError` otherwise
    - Validate `top_k` is an integer in [1, 10] if present; raise `ValidationError` with the message `"top_k must be an integer in [1, 10]"` otherwise
    - Return the validated and coerced body dict
    - _Requirements: 2.12, 2.14_

  - [ ]* 6.2 Write property tests for validation (Properties 11 and 12)
    - **Property 11: HTTP 400 for invalid required fields**
    - *For any* request body missing `type` or `genre`, or containing wrong-typed fields, the Recommender returns HTTP 400 with a non-empty `error` field
    - **Property 12: HTTP 400 for out-of-range top_k**
    - *For any* request body with `top_k` not a positive integer or outside [1, 10], the Recommender returns HTTP 400 with an `error` field describing the invalid value
    - **Validates: Requirements 2.12, 2.14**
    - `# Feature: movie-dss-web, Property 11: HTTP 400 for invalid required fields`
    - `# Feature: movie-dss-web, Property 12: HTTP 400 for out-of-range top_k`

  - [x] 6.3 Implement `_build_query_string(query: dict) -> str`
    - Concatenate `type`, `genre`, `country`, `release_year`, `duration`, `keyword` (each cast to str); skip absent or empty optional fields
    - Join non-empty tokens with a single space
    - _Requirements: 2.3, 2.9_

- [x] 7. Implement Lambda artifact loading and inference pipeline (`backend/lambda_function.py` — runtime layer)
  - [x] 7.1 Implement module-level globals and `_load_artifacts()`
    - Declare `_vectorizer = None`, `_movie_vectors = None`, `_movies = None` at module level
    - In `_load_artifacts()`, read `ARTIFACTS_BUCKET` and `MODEL_PREFIX` from environment variables
    - Use `boto3.client('s3').get_object(...)` to download each artifact; deserialize `.pkl` files with `joblib.load(io.BytesIO(...))` and `.json` with `json.loads(...)`
    - Set globals only if they are currently `None` (container-lifetime caching)
    - Log artifact load time in milliseconds to CloudWatch
    - On `botocore.exceptions.ClientError`, log the full traceback and raise to propagate as HTTP 500
    - _Requirements: 2.2, 2.13, 8.3_

  - [x] 7.2 Implement the full inference loop inside `lambda_handler`
    - Call `_load_artifacts()`; call `_validate_request(body)` inside a try/except for `ValidationError` → return HTTP 400
    - Build query string with `_build_query_string(query)`; transform with `vectorizer.transform([q])`
    - Compute `cosine_similarity(query_vector, movie_vectors)` → flatten to 1-D array
    - For each movie compute all four sub-scores and the composite score
    - Sort by composite score descending; take `top_k` results; attach 1-based rank
    - Log structured fields (`type`, `genre`, `country`, `release_year`, `duration`, `top_k`, `result_count`) and compute time in milliseconds; do NOT log `keyword`
    - Return HTTP 200 with `{"status": "success", "results": [...]}`; include `CORS_HEADERS` on all responses
    - Wrap the entire handler body in a top-level try/except to catch unhandled exceptions → log traceback → return HTTP 500 with `{"error": "Internal server error"}`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.13, 3.3, 8.1, 8.2, 8.3_

  - [ ]* 7.3 Write property tests for result count and ordering (Properties 5 and 10)
    - **Property 5: Result count bounded by top_k**
    - *For any* valid User_Query with `top_k` in [1, 10], the results array length ≤ `min(top_k, total_movies)` and never exceeds 10
    - **Property 10: Results sorted by composite score descending**
    - *For any* valid User_Query, every adjacent pair in the results satisfies `results[i].score >= results[i+1].score`
    - Mock S3 artifact loading with `pytest` fixtures that inject small in-memory data
    - **Validates: Requirements 2.1, 2.8**
    - `# Feature: movie-dss-web, Property 5: Result count bounded by top_k`
    - `# Feature: movie-dss-web, Property 10: Results sorted by composite score descending`

  - [ ]* 7.4 Write property test for unhandled exception safe 500 response (Property 16)
    - **Property 16: Unhandled exception produces safe 500 response**
    - *For any* unhandled exception raised inside the Lambda handler, the HTTP response status is 500 and the body is exactly `{"error": "Internal server error"}`
    - Patch internal functions to raise arbitrary exceptions and call `lambda_handler` directly
    - **Validates: Requirements 8.2**
    - `# Feature: movie-dss-web, Property 16: Unhandled exception produces safe 500 response`

- [ ] 8. Checkpoint — Lambda backend
  - Run `pytest tests/unit/test_recommender.py -v` and ensure all tests pass
  - Run a local smoke test by calling `lambda_handler` directly with a valid payload and a missing-genre payload; verify HTTP 200 and HTTP 400 respectively
  - Ask the user if any questions arise before continuing

- [x] 9. Implement the static frontend (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`)
  - [x] 9.1 Create `frontend/index.html`
    - Write the full HTML structure with `<header>`, `<main>`, `<section id="search-section">`, `<div id="error-area">`, `<section id="results-section">`
    - Include the form with all seven fields as specified in the design: `type` select (required), `genre` select (required), `country` select (optional), `release_year` number input (optional) with `<span id="year-error">` below it, `duration` select (optional), `keyword` text input (optional), `top_k` select (5/10, default 10)
    - Add `<button id="submit-btn">Find Movies</button>` and `<div id="loading" hidden>`
    - Link `style.css` and `app.js`
    - _Requirements: 4.1_

  - [x] 9.2 Create `frontend/style.css`
    - Style the header, form layout (responsive single-column on mobile, two-column on desktop), `.form-group`, `.result-card`, `.rank`, `.badge`, `.score`, `.description`
    - Implement the loading spinner using a CSS `@keyframes` animation on `#loading`
    - Style `#error-area` as a visible error banner (red/orange background, positioned above results)
    - Style `#year-error` as a small inline red text beneath the year input
    - Apply `Cache-Control`-compatible design (no inline styles or dynamic assets)
    - _Requirements: 4.3, 4.4, 5.1_

  - [x] 9.3 Create `frontend/app.js` — initialization and form utilities
    - Implement `initForm()`: populate `genre` and `country` `<select>` elements from static arrays matching the dataset values
    - Implement `validateForm() -> string[]`: validate that `release_year` (if non-empty) is a four-digit integer in [1900, currentYear]; return an array of error messages
    - Implement `setLoading(isLoading: bool)`: disable/enable `submit-btn` and toggle `#loading` visibility simultaneously
    - Implement `renderError(message: string)`: show `#error-area` with the given message; clear results
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [x] 9.4 Create `frontend/app.js` — API call and results rendering
    - Implement `callApi(payload) -> Promise<object>`: `fetch()` the API Gateway URL (stored in a `const API_URL` constant at the top of the file) with method `POST`, `Content-Type: application/json`, and the serialized payload; return the parsed JSON
    - Implement `renderResults(results: array)`: clear `#results-list`; if empty show "No movies matched your criteria. Try adjusting your filters."; otherwise inject one `.result-card` per result using the card template from the design, formatting `score` as `(score * 100).toFixed(1) + "%"`
    - Implement `handleSubmit(event)`: call `validateForm()` → show inline year error and return if invalid → `setLoading(true)` → `callApi(payload)` → `setLoading(false)` → `renderResults()` or `renderError()` depending on response; wrap in try/catch for network failures
    - Attach `handleSubmit` to the form's `submit` event; call `initForm()` on `DOMContentLoaded`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4_

- [ ] 10. Checkpoint — Frontend
  - Open `frontend/index.html` in a browser (with a local static server or via `file://`) and verify: form renders correctly, submit with empty genre shows browser required-field validation, year outside range shows inline error, loading spinner appears and disappears on submit
  - Ask the user if any questions arise before continuing

- [ ] 11. Write integration / smoke tests (`tests/integration/test_api_integration.py`)
  - [ ] 11.1 Implement live API smoke tests
    - Read the API Gateway URL from an environment variable `API_URL` (skip all tests with `pytest.skip` if not set)
    - Test 1: POST `/recommend` with a valid full payload returns HTTP 200 and `{"status": "success"}`
    - Test 2: POST `/recommend` with missing `genre` returns HTTP 400 and an `error` field
    - Test 3: POST `/recommend` with `top_k=0` returns HTTP 400
    - _Requirements: 2.1, 2.12, 3.1, 3.2_

  - [ ]* 11.2 Write additional integration checks
    - Test 4: GET the CloudFront URL returns HTTP 200 and `Content-Type: text/html` (requires `CLOUDFRONT_URL` env var)
    - Test 5: Direct GET on the artifacts S3 bucket URL returns HTTP 403 (bucket is not public); requires `ARTIFACTS_BUCKET_URL` env var
    - _Requirements: 6.1, 6.2, 7.2_

- [x] 12. Create deployment documentation (`docs/deployment.md`)
  - Write step-by-step instructions covering:
    1. **Prerequisites**: Python 3.11, AWS CLI configured, `pip install -r requirements-dev.txt`
    2. **Step 1 — Preprocess**: `python model/train_model.py`; verify output files exist in `model/`
    3. **Step 2 — Create S3 buckets**: create `movie-dss-artifacts` (private) and `movie-dss-frontend` (for CloudFront OAC); include exact `aws s3api create-bucket` commands
    4. **Step 3 — Upload model artifacts**: `aws s3 cp` commands for `vectorizer.pkl`, `movie_vectors.pkl`, `movies_clean.json` to `s3://movie-dss-artifacts/model/`
    5. **Step 4 — Build Lambda deployment package**: `pip install -r backend/requirements.txt -t backend/package/`, copy `lambda_function.py`, zip to `lambda_deployment.zip`
    6. **Step 5 — Create Lambda function**: runtime Python 3.11, handler `lambda_function.lambda_handler`, memory 512 MB, timeout 29 s, environment variables `ARTIFACTS_BUCKET` and `MODEL_PREFIX`, IAM role with `s3:GetObject` on `arn:aws:s3:::movie-dss-artifacts/model/*`
    7. **Step 6 — Create API Gateway HTTP API**: single route `POST /recommend`, Lambda proxy integration, CORS (`*`, `Content-Type`, `GET POST OPTIONS`), 29 s timeout
    8. **Step 7 — Update `API_URL` in `frontend/app.js`**: replace the placeholder with the API Gateway invoke URL
    9. **Step 8 — Upload frontend**: `aws s3 sync frontend/ s3://movie-dss-frontend/ --cache-control "max-age=86400"`
    10. **Step 9 — Create CloudFront distribution**: OAC origin to `movie-dss-frontend`, HTTPS only, default root `index.html`, custom error pages 403/404 → `index.html` (200), PriceClass_100
    11. **Step 10 — Run smoke tests**: set `API_URL` env var and run `pytest tests/integration/ -v`
  - _Requirements: 1.4, 1.5, 2.2, 3.1, 3.2, 6.1, 6.2, 6.4, 7.1, 7.2_

- [ ] 13. Final checkpoint — full test suite
  - Run `pytest tests/unit/ -v --tb=short` and verify all unit and property tests pass
  - Run `pytest tests/integration/ -v` (with `API_URL` set) and verify smoke tests pass
  - Ensure all tests pass before marking the implementation complete; ask the user if any questions arise

---

## Notes

- Tasks marked `*` are optional (property/integration tests) and can be skipped for a faster MVP, but are strongly recommended for correctness assurance
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major layer
- Property tests use **Hypothesis** with `@settings(max_examples=200)` for scoring functions and the default (100) elsewhere
- The `API_URL` constant in `app.js` must be updated after the API Gateway is created (Step 8 in deployment guide)
- `backend/package/` is excluded from version control (add to `.gitignore`); only `lambda_deployment.zip` needs to be uploaded
- All 16 Correctness Properties from the design document are covered: Properties 1–4 in `test_preprocessor.py`, Properties 5–12 and 16 in `test_recommender.py`, Properties 13–15 are frontend JS properties (to be covered in `tests/unit/test_frontend.js` using Jest if a JS test runner is set up)


---

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"] },
    { "wave": 2, "tasks": ["2.1", "2.2", "2.4", "2.6", "2.7", "2.3", "2.5", "2.8"] },
    { "wave": 3, "tasks": ["3"] },
    { "wave": 4, "tasks": ["4.1", "4.2", "4.4", "4.6", "4.8", "4.3", "4.5", "4.7", "4.9"] },
    { "wave": 5, "tasks": ["5"] },
    { "wave": 6, "tasks": ["6.1", "6.3", "6.2"] },
    { "wave": 7, "tasks": ["7.1", "7.2", "7.3", "7.4"] },
    { "wave": 8, "tasks": ["8"] },
    { "wave": 9, "tasks": ["9.1", "9.2", "9.3", "9.4"] },
    { "wave": 10, "tasks": ["10"] },
    { "wave": 11, "tasks": ["11.1", "11.2"] },
    { "wave": 12, "tasks": ["12"] },
    { "wave": 13, "tasks": ["13"] }
  ]
}
```
