"""
Offline preprocessor for the Movie DSS Web application.

Reads data/netflix_full.csv, cleans and normalises the data, trains a
TF-IDF vectorizer, and writes three artifacts to model/:

    vectorizer.pkl      – trained TfidfVectorizer
    movie_vectors.pkl   – sparse TF-IDF matrix  (n_movies × n_features)
    movies_clean.json   – JSON array of cleaned movie records
"""

import json
import os
import re
import sys

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file so the script is runnable from any cwd)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)

CSV_PATH = os.path.join(_REPO_ROOT, "data", "netflix_full.csv")
VECTORIZER_PATH = os.path.join(_HERE, "vectorizer.pkl")
VECTORS_PATH = os.path.join(_HERE, "movie_vectors.pkl")
JSON_PATH = os.path.join(_HERE, "movies_clean.json")

# CSV columns that must be present in the cleaned output
_REQUIRED_COLUMNS = ["name", "type", "genres", "describle"]

# The nine string fields written to movies_clean.json (order preserved)
_JSON_FIELDS = ["id", "type", "name", "genres", "country", "year", "time", "describle", "rating"]

# All eight text fields that receive whitespace normalisation
_TEXT_FIELDS = ["name", "type", "genres", "country", "year", "time", "describle", "rating"]


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def normalize_whitespace(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal runs to a single space.

    Requirements: 1.2
    """
    return re.sub(r"\s+", " ", text.strip())


def build_feature_string(record: dict) -> str:
    """Concatenate type, genres, country, year, and describle joined by one space.

    Requirements: 1.3
    """
    return (
        f"{record['type']} {record['genres']} {record['country']} "
        f"{record['year']} {record['describle']}"
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    # ------------------------------------------------------------------
    # 2.1  Read CSV and drop null rows
    # ------------------------------------------------------------------
    print(f"Reading CSV from: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, dtype=str)

    before = len(df)
    df.dropna(subset=_REQUIRED_COLUMNS, inplace=True)
    after = len(df)
    print(f"Rows after null-row elimination: {after} (dropped {before - after})")

    # ------------------------------------------------------------------
    # 2.2  Whitespace normalisation for all eight text fields
    # ------------------------------------------------------------------
    for field in _TEXT_FIELDS:
        if field in df.columns:
            # fillna("") so that optional fields (country, rating, …) don't
            # raise on NaN values that survived the dropna filter.
            df[field] = df[field].fillna("").apply(normalize_whitespace)

    # ------------------------------------------------------------------
    # 2.4  Build feature corpus
    # ------------------------------------------------------------------
    records = df.to_dict(orient="records")
    corpus = [build_feature_string(r) for r in records]
    print(f"Feature corpus built: {len(corpus)} entries")

    # ------------------------------------------------------------------
    # 2.6  Train TF-IDF vectorizer and serialise artifacts
    # ------------------------------------------------------------------
    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        stop_words="english",
    )
    vectorizer.fit(corpus)
    joblib.dump(vectorizer, VECTORIZER_PATH)
    print(f"Vectorizer saved to: {VECTORIZER_PATH}")

    movie_vectors = vectorizer.transform(corpus)
    joblib.dump(movie_vectors, VECTORS_PATH)
    print(f"Movie vectors saved to: {VECTORS_PATH}  shape={movie_vectors.shape}")

    # ------------------------------------------------------------------
    # 2.7  Export cleaned JSON
    # ------------------------------------------------------------------
    clean_records = [
        {field: str(r.get(field, "") or "") for field in _JSON_FIELDS}
        for r in records
    ]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(clean_records, fh, ensure_ascii=False, indent=2)
    print(f"Cleaned records saved to: {JSON_PATH}  ({len(clean_records)} records)")

    print("Preprocessing complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"ERROR: Preprocessing failed — {exc}", file=sys.stderr)
        sys.exit(1)
