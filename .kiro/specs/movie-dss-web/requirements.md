# Requirements Document

## Introduction

The Movie Decision Support System (DSS) is a serverless web application that helps users choose movies based on personal criteria. The system applies Content-Based Filtering using TF-IDF and Cosine Similarity to recommend movies from the `netflix_full.csv` dataset. The frontend is a static HTML/CSS/JS site hosted on Amazon S3 and served via CloudFront. The backend is a Python AWS Lambda function exposed through API Gateway.

Users provide criteria such as content type, genre, country, release year, duration category, and description keywords. The system returns a ranked list of the top matching movies with a composite relevance score.

---

## Glossary

- **System**: The Movie DSS web application as a whole.
- **Frontend**: The static HTML/CSS/JavaScript website hosted on Amazon S3.
- **Backend**: The Python AWS Lambda function that performs recommendation logic.
- **Recommender**: The Lambda-based component that computes movie recommendations.
- **Preprocessor**: The offline Python script that cleans the dataset and trains the TF-IDF model.
- **API**: The Amazon API Gateway HTTP endpoint exposed to the Frontend.
- **Dataset**: The `netflix_full.csv` file containing Netflix movie and TV show records.
- **Model_Artifacts**: The pre-computed files `vectorizer.pkl`, `movie_vectors.pkl`, and `movies_clean.json` stored in S3.
- **Composite_Score**: The weighted final relevance score combining content similarity and metadata signals.
- **User_Query**: The JSON payload submitted by the user containing filter criteria and optional keyword.
- **Short_Duration**: A movie or show with duration less than 90 minutes.
- **Medium_Duration**: A movie or show with duration between 90 and 120 minutes inclusive.
- **Long_Duration**: A movie or show with duration greater than 120 minutes.

---

## Requirements

### Requirement 1: Offline Dataset Preprocessing

**User Story:** As a developer, I want to preprocess the raw CSV dataset offline, so that the Lambda function can load lightweight artifacts and respond quickly without processing raw data on every request.

#### Acceptance Criteria

1. WHEN the Preprocessor is executed, THE Preprocessor SHALL read `data/netflix_full.csv` and produce a cleaned dataset free of records with null values in the `name`, `type`, `genres`, or `describle` columns.
2. WHEN the Preprocessor cleans the dataset, THE Preprocessor SHALL normalize whitespace — collapsing any sequence of whitespace characters to a single space and stripping leading/trailing spaces — in the `name`, `type`, `genres`, `country`, `year`, `time`, `describle`, and `rating` text fields.
3. WHEN the Preprocessor builds the feature corpus, THE Preprocessor SHALL concatenate the `type`, `genres`, `country`, `year`, and `describle` columns into a single feature string for each record, joined by a single space character.
4. WHEN the feature corpus is ready, THE Preprocessor SHALL train a TF-IDF Vectorizer on the corpus and serialize it as `vectorizer.pkl` in the `model/` output directory.
5. WHEN the TF-IDF Vectorizer is trained, THE Preprocessor SHALL compute and serialize the full movie vector matrix as `movie_vectors.pkl` in the `model/` output directory.
6. WHEN the dataset is cleaned, THE Preprocessor SHALL serialize the cleaned records as `movies_clean.json` in the `model/` output directory, with fields: `id`, `type`, `name`, `genres`, `country`, `year`, `time`, `describle`, `rating`.
7. IF the input CSV file is missing, unreadable, or encounters any other processing error during execution, THEN THE Preprocessor SHALL print a descriptive error message identifying the failure reason and exit with a non-zero status code.

---

### Requirement 2: Movie Recommendation API

**User Story:** As a user, I want to submit my movie preferences via an API, so that I can receive a ranked list of movies that match my criteria.

#### Acceptance Criteria

1. WHEN a POST request is made to `/recommend` with a valid `User_Query`, THE Recommender SHALL return a JSON response with status `"success"` and a `results` array containing at most `top_k` movies, where `top_k` is a positive integer in the range [1, 10], capped at a maximum of 10 results regardless of the value supplied by the caller.
2. WHEN computing recommendations, THE Recommender SHALL load `vectorizer.pkl` and `movie_vectors.pkl` from S3 once per Lambda container lifetime and reuse them for subsequent requests.
3. WHEN building the query vector, THE Recommender SHALL concatenate the user-supplied `type`, `genre`, `country`, `release_year`, `duration`, and `keyword` fields into a single string and transform it using the loaded TF-IDF Vectorizer.
4. WHEN computing relevance, THE Recommender SHALL calculate the Composite_Score as: `0.7 × cosine_similarity + 0.1 × year_score + 0.1 × duration_score + 0.1 × metadata_score`.
5. WHEN `release_year` is provided in the User_Query, THE Recommender SHALL compute `year_score` as `1.0 - min(|movie_year - query_year|, 10) / 10`; IF `release_year` is absent, THEN `year_score` SHALL be `0.0`.
6. WHEN `duration` is provided as `"Short"`, `"Medium"`, or `"Long"`, THE Recommender SHALL compute `duration_score` as `1.0` if the movie duration category matches, and `0.0` otherwise; IF `duration` is absent or not one of the three allowed values, THEN `duration_score` SHALL be `0.0`.
7. WHEN `type` or `country` is provided, THE Recommender SHALL compute `metadata_score` as the count of provided metadata fields that exactly match the movie record divided by the total count of provided metadata fields; IF neither `type` nor `country` is provided, THEN `metadata_score` SHALL be `0.0`.
8. WHEN the results are ready, THE Recommender SHALL return them sorted by Composite_Score descending.
9. IF the `keyword` field is absent or empty, THEN THE Recommender SHALL use only the remaining fields to construct the query string.
10. IF the `top_k` field is absent, THEN THE Recommender SHALL default to returning 10 results.
11. IF the results array is empty after scoring, THEN THE Recommender SHALL return a response with status `"success"` and an empty `results` array.
12. IF the request body is missing one or more of the required fields (`type`, `genre`) or contains values of invalid types for any field, THEN THE Recommender SHALL return HTTP 400 with an `error` field describing the specific validation failure.
13. IF loading Model_Artifacts from S3 fails, THEN THE Recommender SHALL return HTTP 500 with an `error` field and log the exception to CloudWatch.
14. IF the `top_k` field is present but its value is outside the range [1, 10] or is not a positive integer, THEN THE Recommender SHALL return HTTP 400 with an `error` field describing the invalid `top_k` value.

---

### Requirement 3: API Gateway Configuration

**User Story:** As a developer, I want the API to be accessible from the Frontend, so that the browser can call the recommendation endpoint without cross-origin errors.

#### Acceptance Criteria

1. THE API SHALL expose a single HTTP POST endpoint at path `/recommend`.
2. THE API SHALL enable CORS, allowing requests from any origin (`*`), with `Content-Type` in the allowed headers, and with `GET`, `POST`, and `OPTIONS` in the allowed HTTP methods.
3. WHEN a preflight OPTIONS request is received, THE API SHALL respond with HTTP 200 and SHALL include the CORS response headers `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, and `Access-Control-Allow-Headers` in the response.
4. THE API SHALL have a timeout of at most 29 seconds to stay within API Gateway limits; WHEN the Lambda integration exceeds this timeout, THE API SHALL return HTTP 504 to the caller.

---

### Requirement 4: Frontend — Movie Selection Form

**User Story:** As a user, I want a clear and easy-to-use form on the website, so that I can specify my movie preferences without confusion.

#### Acceptance Criteria

1. THE Frontend SHALL display a form containing: a `type` selector (Movie / TV Show), a `genre` selector, a `country` selector, a `release_year` numeric input, a `duration` selector (Short / Medium / Long), a `keyword` text input, and a `top_k` selector (5 / 10); the `type` and `genre` fields SHALL be required while all other fields SHALL be optional.
2. WHEN the user submits the form with a `release_year` value, THE Frontend SHALL validate that the value is a four-digit integer between 1900 and the current calendar year.
3. IF the `release_year` value fails validation, THEN THE Frontend SHALL display an inline error message immediately below the `release_year` input field and prevent the form from being submitted.
4. WHEN the user submits a valid form, THE Frontend SHALL both disable the submit button and display a loading indicator simultaneously until the API response is received; WHEN the response is received, THE Frontend SHALL re-enable the submit button and remove the loading indicator.
5. WHEN the API returns an error response, THE Frontend SHALL display a human-readable error message in a dedicated error area visible without scrolling.

---

### Requirement 5: Frontend — Results Display

**User Story:** As a user, I want to see a ranked list of recommended movies with key details, so that I can make an informed viewing decision.

#### Acceptance Criteria

1. WHEN the API returns a successful response, THE Frontend SHALL display each result as a card showing: 1-based rank integer, movie name, type, country, release year, duration, genre list, description, and Composite_Score formatted as a percentage rounded to one decimal place.
2. WHEN the results array is empty, THE Frontend SHALL display a message informing the user that no movies matched their criteria.
3. WHEN a new search is submitted, THE Frontend SHALL clear the previous results before displaying the new ones.
4. THE Frontend SHALL display results in the order returned by the API (descending by Composite_Score).

---

### Requirement 6: Static Website Hosting

**User Story:** As a developer, I want the Frontend to be hosted on Amazon S3 with CloudFront distribution, so that users can access the website over HTTPS with low latency.

#### Acceptance Criteria

1. THE Frontend files (`index.html`, `style.css`, `app.js`) SHALL be deployable to an Amazon S3 bucket configured for static website hosting.
2. WHERE CloudFront is configured, THE System SHALL serve the Frontend exclusively through the CloudFront distribution URL using HTTPS.
3. WHEN a user requests any path not found in S3, THE System SHALL return `index.html` as the error document so the single-page layout is preserved.
4. THE Frontend files SHALL include `Cache-Control: max-age=86400` metadata (or a higher value) to allow CloudFront edge caching for at least 24 hours.

---

### Requirement 7: IAM and Security

**User Story:** As a developer, I want the Lambda function to access S3 using least-privilege IAM permissions, so that the backend cannot perform unintended operations on S3.

#### Acceptance Criteria

1. THE Recommender SHALL access S3 using an IAM execution role that grants only `s3:GetObject` on the specific Model_Artifacts bucket prefix (e.g., `arn:aws:s3:::movie-dss-bucket/model/*`).
2. THE Recommender SHALL NOT have `s3:PutObject`, `s3:DeleteObject`, or any other write permissions on any S3 resource.
3. THE API SHALL NOT expose any AWS credentials or internal ARNs in its response payloads.

---

### Requirement 8: Observability and Error Handling

**User Story:** As a developer, I want Lambda logs to be available in CloudWatch, so that I can diagnose errors and monitor performance.

#### Acceptance Criteria

1. WHEN the Recommender handles a request, THE Recommender SHALL log to CloudWatch Logs the following fields: `type`, `genre`, `country`, `release_year`, `duration`, `top_k`, and the count of results returned; the `keyword` field SHALL NOT be logged.
2. WHEN an unhandled exception occurs in the Recommender, THE Recommender SHALL log the full exception traceback to CloudWatch Logs and return HTTP 500 with a response body containing only `{"error": "Internal server error"}` to the caller.
3. THE Recommender SHALL log the time taken to load Model_Artifacts and the time taken to compute recommendations for each request, both expressed in milliseconds.
