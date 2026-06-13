# Design Document: Movie DSS Web

## Overview

The Movie Decision Support System (DSS) is a serverless web application that recommends Netflix movies and TV shows based on user-supplied criteria. Users fill a form with content type, genre, country, release year, duration preference, and optional keywords. The system returns a ranked list of up to 10 matches with composite relevance scores.

The architecture is fully serverless on AWS: a static HTML/CSS/JS frontend hosted on S3 and served through CloudFront, an API Gateway HTTP endpoint, and a Python Lambda function that performs all recommendation logic. ML model artifacts are pre-computed offline and stored in S3, so each Lambda invocation is fast and cheap.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                          USER BROWSER                         │
│              (vanilla HTML / CSS / JavaScript)                │
└─────────────────────────────┬─────────────────────────────────┘
                              │  HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Amazon CloudFront                       │
│           CDN — caches static assets at edge nodes          │
└──────────┬──────────────────────────────────────────────────┘
           │  origin: S3 static website bucket
           ▼
┌─────────────────────────────┐
│        Amazon S3            │
│  (frontend hosting bucket)  │
│  index.html                 │
│  style.css                  │
│  app.js                     │
└─────────────────────────────┘

           User JS calls API Gateway
           │  POST /recommend  (JSON body)
           ▼
┌─────────────────────────────┐
│    Amazon API Gateway       │
│  HTTP API — /recommend      │
│  CORS enabled               │
└──────────┬──────────────────┘
           │  Lambda proxy integration
           ▼
┌─────────────────────────────┐
│       AWS Lambda            │
│  Python 3.11 runtime        │
│  lambda_function.py         │
│  scikit-learn, numpy,       │
│  joblib, boto3              │
└──────────┬──────────────────┘
           │  s3:GetObject (model artifacts)
           ▼
┌─────────────────────────────┐
│        Amazon S3            │
│  (artifacts bucket)         │
│  model/vectorizer.pkl       │
│  model/movie_vectors.pkl    │
│  model/movies_clean.json    │
└─────────────────────────────┘

Offline (developer machine):
┌──────────────────────────────────────────────────┐
│  model/train_model.py  (Preprocessor)            │
│  Reads data/netflix_full.csv                     │
│  Outputs vectorizer.pkl, movie_vectors.pkl,      │
│           movies_clean.json  →  upload to S3     │
└──────────────────────────────────────────────────┘
```

### Data flow summary

1. Developer runs `train_model.py` locally; artifacts are uploaded to S3.
2. User opens the CloudFront URL; the browser fetches static files from S3.
3. User submits the form; `app.js` POSTs a JSON `User_Query` to API Gateway.
4. API Gateway proxies the request to the Lambda function.
5. Lambda loads cached model artifacts (warm container) or fetches them from S3 (cold start).
6. Lambda computes cosine similarities and composite scores, sorts, and returns JSON.
7. `app.js` renders result cards in the DOM.

---

## Components and Interfaces

### Preprocessor (`model/train_model.py`)

An offline Python script executed once by the developer before deployment. It has no runtime interface — it reads from the filesystem and writes to the filesystem.

**Inputs:**
- `data/netflix_full.csv` — raw Netflix dataset

**Outputs (written to `model/`):**
- `vectorizer.pkl` — trained `sklearn.feature_extraction.text.TfidfVectorizer`
- `movie_vectors.pkl` — sparse matrix of shape `(n_movies, n_features)` produced by `vectorizer.transform(corpus)`
- `movies_clean.json` — JSON array of cleaned movie record objects

**Key responsibilities:**
1. Drop rows with null in `name`, `type`, `genres`, or `describle`.
2. Normalize whitespace in all text fields.
3. Build feature corpus: `type + " " + genres + " " + country + " " + year + " " + describle`.
4. Train TF-IDF vectorizer on the corpus.
5. Compute and serialize the full movie vector matrix.
6. Serialize the cleaned records to JSON.
7. On any error, print a descriptive message and exit with a non-zero code.

---

### Lambda Recommender (`backend/lambda_function.py`)

The only runtime compute component. Exposed through API Gateway as an HTTP Lambda proxy integration.

**Entry point:** `lambda_handler(event, context)`

**Runtime interface (via API Gateway proxy integration):**
- Reads `event["body"]` — JSON string of the `User_Query`
- Returns a dict with `statusCode`, `headers`, `body`

**Container-lifetime cached state (module-level globals):**
```python
_vectorizer = None      # TfidfVectorizer loaded from S3
_movie_vectors = None   # scipy sparse matrix loaded from S3
_movies = None          # list[dict] loaded from movies_clean.json
```

**Internal function boundaries:**
- `_load_artifacts()` — loads all three artifacts from S3 if not already loaded
- `_validate_request(body)` — validates required fields and types; raises `ValidationError`
- `_build_query_string(query)` — concatenates user fields into a feature string
- `_compute_year_score(movie_year, query_year)` — returns float in [0, 1]
- `_compute_duration_score(movie_duration_category, query_duration)` — returns 0.0 or 1.0
- `_compute_metadata_score(movie, query)` — returns float in [0, 1]
- `_compute_composite_score(cos_sim, year_score, dur_score, meta_score)` — returns float
- `_categorize_duration(time_str)` — parses raw `time` field and returns `"Short"`, `"Medium"`, or `"Long"`

---

### API Gateway

HTTP API (not REST API) for lower cost and simpler setup.

- Single route: `POST /recommend`
- Lambda proxy integration (passes the full event to Lambda, returns Lambda's response directly)
- CORS configuration: allow origin `*`, methods `GET, POST, OPTIONS`, header `Content-Type`
- Integration timeout: 29 seconds

---

### Frontend (`frontend/`)

A single-page application built in vanilla HTML/CSS/JS with no build toolchain.

**Files:**
- `index.html` — markup: header, form, results section, error section
- `style.css` — layout, card styles, loading spinner, error banner
- `app.js` — form handling, fetch call, DOM rendering

**Internal module structure of `app.js`:**
- `initForm()` — populates genre and country `<select>` elements from a static list
- `validateForm()` — validates `release_year`; returns an array of error messages
- `handleSubmit(event)` — orchestrates validation → loading state → fetch → render
- `callApi(payload)` — wraps `fetch()` call to the API Gateway URL; returns parsed JSON
- `renderResults(results)` — clears results area and renders result cards
- `renderError(message)` — displays error message in the error area
- `setLoading(isLoading)` — toggles submit button disabled state and loading indicator

---

### S3 Buckets

Two logical S3 buckets (may be one physical bucket with separate prefixes or two separate buckets):

| Bucket | Purpose | Public access |
|--------|---------|---------------|
| `movie-dss-frontend` | Static website hosting (index.html, style.css, app.js) | Public via CloudFront OAC |
| `movie-dss-artifacts` | Model artifacts (model/vectorizer.pkl, model/movie_vectors.pkl, model/movies_clean.json) | Private — Lambda IAM role only |

---

### CloudFront Distribution

- Origin: S3 frontend bucket (via Origin Access Control, not public S3 URL)
- Default root object: `index.html`
- Custom error response: 404 → `index.html` (status 200) to support the SPA layout
- Viewer protocol policy: HTTPS only
- Cache-Control on S3 objects: `max-age=86400` (24 hours minimum)

---

## Data Models

### User_Query (POST /recommend request body)

```json
{
  "type":         "Movie",         // required, string: "Movie" | "TV Show"
  "genre":        "Action",        // required, string (must be non-empty)
  "country":      "United States", // optional, string
  "release_year": 2018,            // optional, integer in [1900, current_year]
  "duration":     "Medium",        // optional, string: "Short" | "Medium" | "Long"
  "keyword":      "hero adventure",// optional, string (may be empty or absent)
  "top_k":        10               // optional, integer in [1, 10], default 10
}
```

Validation rules:
- `type` and `genre`: required, must be non-empty strings.
- `release_year`: optional; if present, must be a positive integer in [1900, current_year].
- `duration`: optional; if present, must be one of `"Short"`, `"Medium"`, `"Long"` (case-sensitive).
- `top_k`: optional; if present, must be an integer in [1, 10]; otherwise defaults to 10.
- Any field with a wrong type (e.g., `release_year: "abc"`) triggers HTTP 400.

---

### API Success Response

```json
{
  "status": "success",
  "results": [
    {
      "rank":         1,
      "name":         "Inception",
      "type":         "Movie",
      "country":      "United States",
      "year":         2010,
      "time":         "148 min",
      "genres":       "Action & Adventure Movies, Sci-Fi & Fantasy, Thrillers",
      "describle":    "A thief who steals corporate secrets through dream-sharing technology...",
      "score":        0.934
    }
  ]
}
```

Field notes:
- `rank`: 1-based integer position in the result list.
- `score`: the raw `Composite_Score` float (the frontend formats it as a percentage to 1 decimal place).
- `time`: the raw string from `movies_clean.json` (e.g., `"148 min"` or `"2 Seasons"`).
- All other fields are strings taken directly from the cleaned dataset record.

---

### API Error Response

```json
{
  "error": "Missing required field: genre"
}
```

HTTP 400 for validation errors, HTTP 500 for internal errors.
For unhandled exceptions the body is always exactly `{"error": "Internal server error"}`.

---

### movies_clean.json Record Schema

Each element in the JSON array:

```json
{
  "id":       "81416533",
  "type":     "Movie",
  "name":     "Heart of Stone",
  "genres":   "Drama Movies, Action & Adventure Movies, Spy Movies",
  "country":  "United States",
  "year":     "2023",
  "time":     "125 min",
  "describle":"An intelligence operative for a shadowy global peacekeeping agency...",
  "rating":   "TV-PG"
}
```

All fields are stored as strings. Numeric operations (year arithmetic, duration parsing) are performed at query time in Lambda using type coercion.

---

### CSV Source Fields (netflix_full.csv)

The raw CSV columns that map to the cleaned JSON fields:

| CSV column  | JSON field  | Notes                              |
|-------------|-------------|------------------------------------|
| `id`        | `id`        | String identifier                  |
| `type`      | `type`      | `"Movie"` or `"TV Show"`           |
| `name`      | `name`      | Movie/show title                   |
| `genres`    | `genres`    | Comma-separated genre labels       |
| `country`   | `country`   | Production country                 |
| `year`      | `year`      | 4-digit release year string        |
| `time`      | `time`      | Raw duration string (see below)    |
| `describle` | `describle` | Plot description (note: typo kept) |
| `rating`    | `rating`    | Age rating (e.g., `TV-PG`)         |

The CSV columns `creator` and `starring` are not included in the feature corpus or the API response.

---

## ML Pipeline Design

### Offline Training (`train_model.py`)

```
netflix_full.csv
      │
      ▼
1. Read with pandas.read_csv()
      │
      ▼
2. Drop rows with null in [name, type, genres, describle]
      │
      ▼
3. Normalize whitespace in all 8 text fields
   (strip + re.sub(r'\s+', ' ', ...))
      │
      ▼
4. Build feature corpus per record:
   corpus[i] = f"{type} {genres} {country} {year} {describle}"
      │
      ▼
5. TfidfVectorizer(
       analyzer='word',
       ngram_range=(1, 2),
       min_df=1,
       stop_words='english'
   ).fit(corpus)
      │
      ├─── vectorizer.pkl   (joblib.dump)
      │
      ▼
6. vectorizer.transform(corpus) → sparse matrix (n_movies × n_features)
      │
      └─── movie_vectors.pkl  (joblib.dump)

7. Export cleaned records to movies_clean.json
   (fields: id, type, name, genres, country, year, time, describle, rating)
```

Rationale for `ngram_range=(1, 2)`: bi-grams capture genre phrases like "action adventure" and "romantic comedy" that are more discriminative than individual tokens.

---

### Online Inference (`lambda_function.py`)

```
User_Query JSON
      │
      ▼
1. Validate required fields (type, genre) and types
      │
      ▼
2. Build query string:
   q = f"{type} {genre} {country} {release_year} {duration} {keyword}"
   (absent/empty optional fields are skipped)
      │
      ▼
3. query_vector = vectorizer.transform([q])   # shape (1, n_features)
      │
      ▼
4. cosine_scores = cosine_similarity(query_vector, movie_vectors)
   → flat array of shape (n_movies,)
      │
      ▼
5. For each movie i, compute:
   year_score_i     = _compute_year_score(movies[i].year, release_year)
   duration_score_i = _compute_duration_score(_categorize_duration(movies[i].time), duration)
   metadata_score_i = _compute_metadata_score(movies[i], query)
   composite_i      = 0.7 * cosine_scores[i]
                    + 0.1 * year_score_i
                    + 0.1 * duration_score_i
                    + 0.1 * metadata_score_i
      │
      ▼
6. Sort by composite score descending
      │
      ▼
7. Take top_k results
      │
      ▼
8. Build response: attach rank (1-based), include all movie fields + score
      │
      ▼
9. Return JSON response  { "status": "success", "results": [...] }
```

---

### Key Algorithms

#### Duration Categorization (`_categorize_duration`)

The raw `time` field from the CSV contains strings like `"125 min"` or `"2 Seasons"`.

```python
def _categorize_duration(time_str: str) -> str | None:
    """
    Returns "Short", "Medium", "Long", or None if not parseable.
    
    Rules:
      - Extract the integer before " min" (case-insensitive).
      - If no " min" pattern found (e.g., "3 Seasons"), return None.
      - minutes < 90              → "Short"
      - 90 <= minutes <= 120      → "Medium"
      - minutes > 120             → "Long"
    """
    import re
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
```

TV shows (e.g., `"2 Seasons"`) always return `None`, meaning their `duration_score` is 0.0 unless the user also omits the duration filter.

---

#### Year Score (`_compute_year_score`)

```python
def _compute_year_score(movie_year: str | int, query_year: int | None) -> float:
    """
    Returns a float in [0.0, 1.0].
    
    If query_year is None → return 0.0.
    Otherwise:
        diff  = abs(int(movie_year) - query_year)
        score = 1.0 - min(diff, 10) / 10
    
    Examples:
        same year      → 1.0
        1 year apart   → 0.9
        5 years apart  → 0.5
        10+ years apart → 0.0
    """
    if query_year is None:
        return 0.0
    diff = abs(int(movie_year) - int(query_year))
    return 1.0 - min(diff, 10) / 10.0
```

---

#### Duration Score (`_compute_duration_score`)

```python
def _compute_duration_score(movie_category: str | None, query_duration: str | None) -> float:
    """
    Returns 1.0 if movie_category == query_duration (exact string match),
    0.0 otherwise (including when either is None or query_duration is absent).
    """
    if not query_duration or query_duration not in ("Short", "Medium", "Long"):
        return 0.0
    return 1.0 if movie_category == query_duration else 0.0
```

---

#### Metadata Score (`_compute_metadata_score`)

```python
def _compute_metadata_score(movie: dict, query: dict) -> float:
    """
    Counts how many of the provided metadata fields (type, country)
    exactly match the movie record, divided by the number of provided fields.
    
    If neither type nor country is in query → return 0.0.
    
    Examples:
        query has type=Movie, country=US; movie matches both → 2/2 = 1.0
        query has type=Movie only; movie matches           → 1/1 = 1.0
        query has type=Movie, country=US; only type matches → 1/2 = 0.5
        query has type=Movie, country=US; neither matches  → 0/2 = 0.0
    """
    fields = []
    if "type" in query and query["type"]:
        fields.append(("type", query["type"]))
    if "country" in query and query["country"]:
        fields.append(("country", query["country"]))
    if not fields:
        return 0.0
    matches = sum(1 for field, value in fields if movie.get(field) == value)
    return matches / len(fields)
```

---

#### Composite Score (`_compute_composite_score`)

```python
def _compute_composite_score(cos_sim: float, year_score: float,
                              duration_score: float, metadata_score: float) -> float:
    """
    Weighted combination:
        score = 0.7 * cos_sim
              + 0.1 * year_score
              + 0.1 * duration_score
              + 0.1 * metadata_score
    
    All inputs are in [0, 1]; output is in [0, 1].
    """
    return (0.7 * cos_sim
            + 0.1 * year_score
            + 0.1 * duration_score
            + 0.1 * metadata_score)
```

---

## Frontend Component Design

### Page Structure (`index.html`)

```
<body>
  <header>                        ← site title + brief description
  <main>
    <section id="search-section"> ← form container
      <form id="recommend-form">
        <div class="form-group">  ← type selector (required)
        <div class="form-group">  ← genre selector (required)
        <div class="form-group">  ← country selector (optional)
        <div class="form-group">  ← release_year number input (optional)
          <span id="year-error">  ← inline validation error
        <div class="form-group">  ← duration selector (optional)
        <div class="form-group">  ← keyword text input (optional)
        <div class="form-group">  ← top_k selector: 5 / 10
        <button id="submit-btn">  ← "Find Movies" — disabled during fetch
        <div id="loading">        ← spinner (hidden by default)

    <div id="error-area">         ← API/network error banner (hidden by default)

    <section id="results-section">
      <div id="results-list">    ← result cards injected here
```

### Form Fields

| Field | Element | Values | Required |
|-------|---------|--------|----------|
| `type` | `<select>` | Movie, TV Show | Yes |
| `genre` | `<select>` | Populated from static genre list | Yes |
| `country` | `<select>` | Populated from static country list + empty option | No |
| `release_year` | `<input type="number">` | 1900 – current year | No |
| `duration` | `<select>` | (blank), Short, Medium, Long | No |
| `keyword` | `<input type="text">` | Free text | No |
| `top_k` | `<select>` | 5, 10 | No (default 10) |

### Result Card Template

Each card rendered by `renderResults()`:

```html
<div class="result-card">
  <div class="rank">#1</div>
  <div class="movie-info">
    <h3 class="movie-name">Inception</h3>
    <div class="meta-row">
      <span class="badge type">Movie</span>
      <span class="badge country">United States</span>
      <span class="year">2010</span>
      <span class="duration">148 min</span>
    </div>
    <div class="genres">Action & Adventure, Sci-Fi & Fantasy, Thrillers</div>
    <p class="description">A thief who steals corporate secrets...</p>
  </div>
  <div class="score">93.4%</div>
</div>
```

Score formatting: `(score * 100).toFixed(1) + "%"`

### UI States

| State | submit button | loading div | error-area | results-list |
|-------|--------------|-------------|------------|--------------|
| Idle (initial) | enabled | hidden | hidden | empty |
| Loading | disabled | visible | hidden | unchanged |
| Success | enabled | hidden | hidden | populated |
| API error | enabled | hidden | visible | cleared |
| Validation error | enabled | hidden | hidden | unchanged |
| Empty results | enabled | hidden | hidden | "no results" message |

---

## File and Directory Structure

```
Movie_DSS/
│
├── frontend/
│   ├── index.html          ← single HTML page (form + results)
│   ├── style.css           ← all styles, card layout, loading spinner
│   ├── app.js              ← form logic, API call, DOM rendering
│   └── assets/             ← optional: favicon, logo image
│
├── backend/
│   ├── lambda_function.py  ← Lambda handler + all recommendation logic
│   ├── requirements.txt    ← scikit-learn, numpy, joblib, boto3
│   └── package/            ← Lambda deployment package (zipped dependencies)
│
├── data/
│   └── netflix_full.csv    ← raw Netflix dataset (source only, not in Lambda)
│
├── model/
│   ├── train_model.py      ← offline preprocessing + training script
│   ├── vectorizer.pkl      ← serialized TfidfVectorizer (upload to S3)
│   ├── movie_vectors.pkl   ← serialized sparse matrix (upload to S3)
│   └── movies_clean.json   ← cleaned movie records array (upload to S3)
│
└── .kiro/
    └── specs/
        └── movie-dss-web/
            ├── requirements.md
            ├── design.md
            └── tasks.md
```

S3 bucket layout:

```
movie-dss-frontend/          ← public via CloudFront OAC
  index.html
  style.css
  app.js
  assets/

movie-dss-artifacts/         ← private, Lambda IAM role only
  model/
    vectorizer.pkl
    movie_vectors.pkl
    movies_clean.json
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

The following properties are derived from the acceptance criteria that have been classified as PROPERTY in the prework analysis. They cover the Preprocessor logic and the Lambda Recommender logic — the two components with pure-function behavior where property-based testing provides high value. Infrastructure, UI rendering, and configuration criteria are covered by example-based and integration tests (see Testing Strategy).

**Property reflection:** After reviewing all candidate properties, the following consolidations were made:
- Properties 1.2 (whitespace normalization) and 1.3 (feature string concatenation) are kept separate because they test distinct invariants that could fail independently.
- Properties 2.4 (composite formula), 2.5 (year score), 2.6 (duration score), and 2.7 (metadata score) are kept separate because each sub-score function can be wrong in isolation.
- Properties 2.1 (top_k cap) and 2.8 (ordering) are kept separate because they test length vs. order, two orthogonal invariants.
- Properties 2.12 (400 on bad required fields) and 2.14 (400 on bad top_k) test different validation branches and are kept separate.

---

### Property 1: Null-row elimination

*For any* CSV dataset containing rows with null values in `name`, `type`, `genres`, or `describle`, after the Preprocessor runs, the cleaned output SHALL contain zero records that have a null value in any of those four columns.

**Validates: Requirements 1.1**

---

### Property 2: Whitespace normalization

*For any* text field value from the dataset containing arbitrary sequences of whitespace characters (including tabs, newlines, multiple spaces, or leading/trailing spaces), the normalized output SHALL have no leading or trailing whitespace and SHALL contain no consecutive whitespace characters.

**Validates: Requirements 1.2**

---

### Property 3: Feature corpus construction

*For any* cleaned record, the feature string produced by the Preprocessor SHALL equal the concatenation of `type`, `genres`, `country`, `year`, and `describle` joined by exactly one space character, with no leading or trailing space.

**Validates: Requirements 1.3**

---

### Property 4: movies_clean.json round-trip completeness

*For any* cleaned record written to `movies_clean.json`, deserializing that record SHALL produce an object containing all nine required fields: `id`, `type`, `name`, `genres`, `country`, `year`, `time`, `describle`, and `rating`, each with a non-null string value.

**Validates: Requirements 1.6**

---

### Property 5: Result count bounded by top_k

*For any* valid User_Query with a `top_k` value in [1, 10], the Recommender SHALL return a results array whose length is at most `min(top_k, total_matching_movies)` and never exceeds 10.

**Validates: Requirements 2.1**

---

### Property 6: Composite score formula invariant

*For any* combination of cosine similarity, year score, duration score, and metadata score — each a float in [0, 1] — the composite score computed by the Recommender SHALL equal exactly `0.7 * cos_sim + 0.1 * year_score + 0.1 * duration_score + 0.1 * metadata_score`.

**Validates: Requirements 2.4**

---

### Property 7: Year score monotonicity and bounds

*For any* pair of integer years (movie_year, query_year), the year score SHALL be in [0.0, 1.0], SHALL equal 1.0 when the years are identical, SHALL equal 0.0 when the absolute difference is ≥ 10, and SHALL decrease monotonically as the absolute difference increases from 0 to 10.

**Validates: Requirements 2.5**

---

### Property 8: Duration score exactness

*For any* movie duration category (`"Short"`, `"Medium"`, `"Long"`, or `None`) and any query duration value, the duration score SHALL be 1.0 if and only if the movie category equals the query duration string exactly; it SHALL be 0.0 in all other cases including when query duration is absent or not one of the three allowed values.

**Validates: Requirements 2.6**

---

### Property 9: Metadata score fraction

*For any* User_Query that provides one or both of `type` and `country`, and *for any* movie record, the metadata score SHALL equal the number of provided fields whose values exactly match the movie record divided by the total number of provided fields, and SHALL be a float in [0.0, 1.0].

**Validates: Requirements 2.7**

---

### Property 10: Results sorted by composite score descending

*For any* valid User_Query, the Recommender's result array SHALL be in non-increasing order of composite score — that is, for every adjacent pair of results at positions i and i+1, `results[i].score >= results[i+1].score`.

**Validates: Requirements 2.8**

---

### Property 11: HTTP 400 for invalid required fields

*For any* request body missing `type` or `genre`, or containing wrong types for any field, the Recommender SHALL return HTTP status 400 and a response body containing an `error` field with a non-empty description of the specific validation failure.

**Validates: Requirements 2.12**

---

### Property 12: HTTP 400 for out-of-range top_k

*For any* request body containing a `top_k` value that is not a positive integer or is outside [1, 10], the Recommender SHALL return HTTP status 400 and a response body containing an `error` field describing the invalid `top_k` value.

**Validates: Requirements 2.14**

---

### Property 13: Frontend year validation accepts valid range and rejects invalid

*For any* integer value submitted as `release_year`, the frontend validator SHALL accept values in [1900, current_calendar_year] and SHALL reject all other values (values below 1900, values above the current year, zero, negative numbers, and non-numeric input).

**Validates: Requirements 4.2**

---

### Property 14: Result card contains all required fields

*For any* result object returned by the API, the DOM card rendered by the frontend SHALL contain the movie's rank, name, type, country, year, duration, genres, description, and composite score formatted as a percentage rounded to one decimal place.

**Validates: Requirements 5.1**

---

### Property 15: Displayed result order matches API order

*For any* API response with N results, the frontend SHALL render the cards in the same order as the results array — card at DOM position i SHALL display the data from `results[i-1]`.

**Validates: Requirements 5.4**

---

### Property 16: Unhandled exception produces safe 500 response

*For any* unhandled exception raised inside the Lambda handler, the HTTP response SHALL have status 500 and the response body SHALL be exactly `{"error": "Internal server error"}` with no additional fields.

**Validates: Requirements 8.2**

---

## Error Handling

### Lambda error taxonomy

| Scenario | HTTP status | Response body | CloudWatch log |
|----------|-------------|---------------|----------------|
| Missing `type` or `genre` | 400 | `{"error": "Missing required field: <name>"}` | Warning |
| Wrong field type (e.g., `release_year: "abc"`) | 400 | `{"error": "Invalid type for field: <name>"}` | Warning |
| `top_k` out of range or not integer | 400 | `{"error": "top_k must be an integer in [1, 10]"}` | Warning |
| S3 GetObject fails (missing artifact) | 500 | `{"error": "Internal server error"}` | Exception + traceback |
| Unhandled exception in inference | 500 | `{"error": "Internal server error"}` | Exception + traceback |
| API Gateway timeout (>29 s) | 504 | API Gateway default | N/A |

### Preprocessor error handling

- Missing or unreadable CSV: `print(f"ERROR: Cannot read input file: {path} — {e}")` then `sys.exit(1)`.
- Any unexpected exception during processing: caught at the top level, same pattern, `sys.exit(1)`.

### Frontend error handling

| Scenario | User-visible behavior |
|----------|-----------------------|
| `release_year` outside valid range | Inline error below the field; form not submitted |
| API returns 4xx | Error banner above results: "Could not process your request: [error message]" |
| API returns 5xx | Error banner: "An internal error occurred. Please try again." |
| Network failure (no response) | Error banner: "Could not reach the server. Please check your connection." |
| Empty results array | Message in results area: "No movies matched your criteria. Try adjusting your filters." |

### CORS pre-flight handling

Lambda must include CORS headers on every response path, including error responses:

```python
CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}
```

An explicit `OPTIONS` route in API Gateway returns HTTP 200 with these headers without invoking Lambda.

---

## Testing Strategy

### Dual testing approach

The testing strategy combines property-based tests (for universal correctness properties over pure functions) with example-based unit tests (for specific behaviors, edge cases, and integration points) and integration checks (for infrastructure).

### Property-based testing (Python: Hypothesis)

Use the [Hypothesis](https://hypothesis.readthedocs.io/) library for all properties listed in the Correctness Properties section.

Configuration:
- Minimum 100 examples per test (Hypothesis default; increase with `@settings(max_examples=200)` for scoring functions).
- Each test is tagged with a comment: `# Feature: movie-dss-web, Property N: <property title>`.
- Properties 1–4 test the Preprocessor (`model/train_model.py` logic extracted into testable functions).
- Properties 5–12 test the Lambda Recommender pure functions (no S3 calls — use fixtures or monkeypatching).
- Properties 13–15 test frontend logic extracted into pure JS functions (using a JS test runner like Jest or via Python for any shared logic).
- Property 16 tests the Lambda top-level exception handler.

Example structure:

```python
from hypothesis import given, settings
import hypothesis.strategies as st

# Feature: movie-dss-web, Property 7: Year score monotonicity and bounds
@given(
    movie_year=st.integers(min_value=1900, max_value=2030),
    query_year=st.integers(min_value=1900, max_value=2030),
)
@settings(max_examples=200)
def test_year_score_bounds_and_monotonicity(movie_year, query_year):
    score = _compute_year_score(movie_year, query_year)
    assert 0.0 <= score <= 1.0
    if movie_year == query_year:
        assert score == 1.0
    if abs(movie_year - query_year) >= 10:
        assert score == 0.0
```

### Example-based unit tests (pytest)

Focus areas:
- Preprocessor: file-not-found exits with code 1, null-row drop with a specific fixture CSV.
- Recommender: default `top_k=10`, empty results array, S3 failure returns 500 (mock boto3).
- Recommender: keyword absent → query string does not contain the keyword token.
- API OPTIONS preflight → 200 with CORS headers.
- Frontend JS: genre/country selects populated, loading state toggled, empty-results message shown.

### Integration tests

Minimal integration tests (1–3 real executions against deployed infrastructure):
- POST `/recommend` with a known valid payload returns 200 and `status: "success"`.
- POST `/recommend` with missing `genre` returns 400.
- CloudFront URL returns 200 for `index.html`.
- S3 artifact bucket is not publicly accessible (returns 403 without credentials).

### Test file layout

```
tests/
├── unit/
│   ├── test_preprocessor.py     ← PBT Properties 1–4, example tests for Preprocessor
│   ├── test_recommender.py      ← PBT Properties 5–12, 16; example tests for Lambda logic
│   └── test_frontend.js         ← PBT Properties 13–15 (Jest); example UI tests
└── integration/
    └── test_api_integration.py  ← live API smoke tests (run after deployment)
```

### What property tests do NOT cover

The following are handled by example tests or deployment checks, not property tests:
- S3/CloudFront/API Gateway infrastructure configuration (Requirements 3, 6, 7)
- CloudWatch log field presence (Requirement 8.1, 8.3)
- Lambda artifact caching across warm container invocations (Requirement 2.2)
- CSS styling and visual layout

---

## Deployment Notes

### S3 buckets

| Bucket | Configuration |
|--------|--------------|
| `movie-dss-frontend` | Static website hosting enabled; `index.html` as both index and error document; public access blocked (accessed via CloudFront OAC only) |
| `movie-dss-artifacts` | No static hosting; all public access blocked; bucket policy grants `s3:GetObject` to Lambda execution role only |

Upload commands (after training):
```bash
aws s3 cp model/vectorizer.pkl   s3://movie-dss-artifacts/model/vectorizer.pkl
aws s3 cp model/movie_vectors.pkl s3://movie-dss-artifacts/model/movie_vectors.pkl
aws s3 cp model/movies_clean.json s3://movie-dss-artifacts/model/movies_clean.json
aws s3 sync frontend/             s3://movie-dss-frontend/ \
    --cache-control "max-age=86400"
```

### Lambda configuration

| Setting | Value |
|---------|-------|
| Runtime | Python 3.11 |
| Handler | `lambda_function.lambda_handler` |
| Memory | 512 MB (scikit-learn sparse matrix fits comfortably; adjust after profiling) |
| Timeout | 29 seconds (matches API Gateway limit) |
| Environment variables | `ARTIFACTS_BUCKET=movie-dss-artifacts`, `MODEL_PREFIX=model/` |
| Layers or deployment package | All dependencies (scikit-learn, numpy, joblib, boto3) bundled in `backend/package/` and zipped |

Lambda deployment package build:
```bash
pip install -r backend/requirements.txt -t backend/package/
cp backend/lambda_function.py backend/package/
cd backend/package && zip -r ../lambda_deployment.zip .
aws lambda update-function-code \
    --function-name movie-dss-recommender \
    --zip-file fileb://backend/lambda_deployment.zip
```

### API Gateway

- Type: HTTP API (lower cost, lower latency than REST API)
- Route: `POST /recommend`
- Integration: Lambda proxy (pass-through)
- CORS: configured at the API level (not in Lambda responses) for `*` origin, `Content-Type` header, `GET, POST, OPTIONS` methods
- Timeout: 29 seconds

### IAM execution role

Policy summary for the Lambda execution role (`movie-dss-lambda-role`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::movie-dss-artifacts/model/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

No `s3:PutObject`, `s3:DeleteObject`, or any other write permissions are granted. No cross-account access.

### CloudFront distribution

- Origin: S3 frontend bucket via Origin Access Control (OAC) — not the S3 website endpoint
- Viewer protocol policy: Redirect HTTP to HTTPS
- Default root object: `index.html`
- Custom error pages: 403 and 404 → `/index.html` (HTTP 200) to support the SPA single-page layout
- Price class: PriceClass_100 (North America + Europe) or PriceClass_All depending on target audience
- Cache behaviour: default behaviour with TTL matching `Cache-Control: max-age=86400` on S3 objects

### Observability

- Lambda logs structured fields per request to CloudWatch: `type`, `genre`, `country`, `release_year`, `duration`, `top_k`, `result_count` (keyword is excluded).
- Artifact load time and recommendation compute time are logged in milliseconds.
- CloudWatch Log Group: `/aws/lambda/movie-dss-recommender`
- Recommended: set a CloudWatch alarm on Lambda error rate > 5% over 5 minutes.
