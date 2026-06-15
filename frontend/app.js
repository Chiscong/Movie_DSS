/* ============================================================
 * Movie Decision Support System — Frontend Logic
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4
 * ============================================================ */

const API_URL = 'https://v7bzd8fpr6.execute-api.ap-southeast-1.amazonaws.com/prod/recommend';


const GENRES = [
  'Action & Adventure Movies',
  'Anime Features',
  'Anime Series',
  'British TV Shows',
  'Children & Family Movies',
  'Classic Movies',
  'Comedies',
  'Crime TV Shows',
  'Cult Movies',
  'Documentaries',
  'Docuseries',
  'Dramas',
  'Faith & Spirituality',
  'Horror Movies',
  'Independent Movies',
  'International Movies',
  'International TV Shows',
  "Kids' TV",
  'Korean TV Shows',
  'LGBTQ Movies',
  'Music & Musicals',
  'Nature TV',
  'Reality TV',
  'Romantic Movies',
  'Romantic TV Shows',
  'Sci-Fi & Fantasy',
  'Science & Nature TV',
  'Spanish-Language TV Shows',
  'Sports Movies',
  'Stand-Up Comedy',
  'Stand-Up Comedy & Talk Shows',
  'Teen TV Shows',
  'Thrillers',
  'TV Action & Adventure',
  'TV Comedies',
  'TV Dramas',
  'TV Horror',
  'TV Mysteries',
  'TV Sci-Fi & Fantasy',
  'TV Thrillers',
];

const COUNTRIES = [
  'Argentina',
  'Australia',
  'Belgium',
  'Brazil',
  'Canada',
  'Chile',
  'China',
  'Colombia',
  'Czech Republic',
  'Denmark',
  'Egypt',
  'Finland',
  'France',
  'Germany',
  'Greece',
  'Hong Kong',
  'Hungary',
  'India',
  'Indonesia',
  'Iran',
  'Ireland',
  'Israel',
  'Italy',
  'Japan',
  'Jordan',
  'Malaysia',
  'Mexico',
  'Netherlands',
  'New Zealand',
  'Nigeria',
  'Norway',
  'Pakistan',
  'Philippines',
  'Poland',
  'Portugal',
  'Romania',
  'Russia',
  'Saudi Arabia',
  'Singapore',
  'South Africa',
  'South Korea',
  'Spain',
  'Sweden',
  'Switzerland',
  'Taiwan',
  'Thailand',
  'Turkey',
  'Ukraine',
  'United Kingdom',
  'United States',
  'Uruguay',
];

// ---------------------------------------------------------------------------
// initForm — populate genre and country <select> elements (Requirement 4.1)
// ---------------------------------------------------------------------------

function initForm() {
  const genreSelect = document.getElementById('genre');
  GENRES.forEach((genre) => {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    genreSelect.appendChild(option);
  });

  const countrySelect = document.getElementById('country');
  COUNTRIES.forEach((country) => {
    const option = document.createElement('option');
    option.value = country;
    option.textContent = country;
    countrySelect.appendChild(option);
  });
}

// ---------------------------------------------------------------------------
// validateForm — validate release_year; return array of error messages
// (Requirements 4.2, 4.3)
// ---------------------------------------------------------------------------

function validateForm() {
  const errors = [];
  const yearInput = document.getElementById('release_year');
  const yearValue = yearInput.value.trim();

  if (yearValue !== '') {
    const currentYear = new Date().getFullYear();
    const yearInt = parseInt(yearValue, 10);

    // Must be a four-digit integer
    const isFourDigitInt = /^\d{4}$/.test(yearValue);

    if (!isFourDigitInt || isNaN(yearInt) || yearInt < 1900 || yearInt > currentYear) {
      errors.push(`Release year must be a four-digit integer between 1900 and ${currentYear}.`);
    }
  }

  return errors;
}

// ---------------------------------------------------------------------------
// setLoading — disable/enable submit button and toggle loading visibility
// (Requirement 4.4)
// ---------------------------------------------------------------------------

function setLoading(isLoading) {
  const submitBtn = document.getElementById('submit-btn');
  const loadingDiv = document.getElementById('loading');

  submitBtn.disabled = isLoading;
  loadingDiv.hidden = !isLoading;
}

// ---------------------------------------------------------------------------
// renderError — show error area with message; clear results (Requirement 4.5)
// ---------------------------------------------------------------------------

function renderError(message) {
  const errorArea = document.getElementById('error-area');
  errorArea.textContent = message;
  errorArea.hidden = false;

  // Clear any previous results
  document.getElementById('results-list').innerHTML = '';
}

// ---------------------------------------------------------------------------
// callApi — POST to API_URL with JSON payload; return parsed JSON
// (Requirements 4.1, 5.1)
// ---------------------------------------------------------------------------

async function callApi(payload) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();

  if (!response.ok) {
    // Surface the API's error message when available
    const message = data.error || `Request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return data;
}

// ---------------------------------------------------------------------------
// renderResults — clear results list and inject result cards
// (Requirements 5.1, 5.2, 5.3, 5.4)
// ---------------------------------------------------------------------------

function renderResults(results) {
  const resultsList = document.getElementById('results-list');
  resultsList.innerHTML = '';

  // Hide any previous error
  const errorArea = document.getElementById('error-area');
  errorArea.hidden = true;
  errorArea.textContent = '';

  if (!results || results.length === 0) {
    const msg = document.createElement('p');
    msg.className = 'no-results';
    msg.textContent = 'No movies matched your criteria. Try adjusting your filters.';
    resultsList.appendChild(msg);
    return;
  }

  // Results are rendered in API order (descending composite score) — Req 5.4
  results.forEach((result) => {
    const scorePercent = (result.score * 100).toFixed(1) + '%';

    const card = document.createElement('div');
    card.className = 'result-card';

    card.innerHTML = `
      <div class="rank">#${result.rank}</div>
      <div class="movie-info">
        <h3 class="movie-name">${escapeHtml(result.name)}</h3>
        <div class="meta-row">
          <span class="badge type">${escapeHtml(result.type)}</span>
          <span class="badge country">${escapeHtml(result.country || '')}</span>
          <span class="year">${escapeHtml(String(result.year || ''))}</span>
          <span class="duration">${escapeHtml(result.time || '')}</span>
        </div>
        <div class="genres">${escapeHtml(result.genres || '')}</div>
        <p class="description">${escapeHtml(result.describle || '')}</p>
      </div>
      <div class="score">${scorePercent}</div>
    `;

    resultsList.appendChild(card);
  });
}

// ---------------------------------------------------------------------------
// handleSubmit — orchestrates validation → loading → API call → render
// (Requirements 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4)
// ---------------------------------------------------------------------------

async function handleSubmit(event) {
  event.preventDefault();

  // --- Validation (Req 4.2, 4.3) ---
  const errors = validateForm();
  const yearError = document.getElementById('year-error');

  if (errors.length > 0) {
    yearError.textContent = errors[0];
    return; // Prevent submission
  }

  // Clear any previous inline year error
  yearError.textContent = '';

  // Hide previous error banner
  const errorArea = document.getElementById('error-area');
  errorArea.hidden = true;
  errorArea.textContent = '';

  // --- Build payload with only non-empty fields ---
  const typeVal = document.getElementById('type').value;
  const genreVal = document.getElementById('genre').value;
  const countryVal = document.getElementById('country').value;
  const yearVal = document.getElementById('release_year').value.trim();
  const durationVal = document.getElementById('duration').value;
  const keywordVal = document.getElementById('keyword').value.trim();
  const topKVal = document.getElementById('top_k').value;

  const payload = {
    type: typeVal,
    genre: genreVal,
    top_k: parseInt(topKVal, 10),
  };

  if (countryVal) {
    payload.country = countryVal;
  }

  if (yearVal !== '') {
    payload.release_year = parseInt(yearVal, 10);
  }

  if (durationVal) {
    payload.duration = durationVal;
  }

  if (keywordVal !== '') {
    payload.keyword = keywordVal;
  }

  // --- Loading state (Req 4.4) ---
  setLoading(true);

  try {
    const data = await callApi(payload);
    setLoading(false);
    renderResults(data.results);
  } catch (err) {
    setLoading(false);

    // Distinguish network failures from API error responses
    if (err instanceof TypeError) {
      // TypeError is thrown by fetch() on network failure
      renderError('Could not reach the server. Please check your connection and try again.');
    } else {
      // API-level error with a message
      const msg = err.message || 'An unexpected error occurred. Please try again.';
      renderError(msg);
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Escape HTML special characters to prevent XSS when setting innerHTML.
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------

document.getElementById('recommend-form').addEventListener('submit', handleSubmit);

document.addEventListener('DOMContentLoaded', initForm);
