/*
API client (Phase 1 placeholder).

Phase 2 will implement:
- BASE_URL and all fetch() wrappers
- JWT auth header handling
- error handling (toast + safe fallback)
- MOCK_MODE to provide demo data when the backend is down
*/

const BASE_URL = "http://localhost:8000/api";
const MOCK_MODE = true;

function getAuthHeader() {
  // Placeholder: Phase 2 will read token from localStorage.
  return {};
}

async function handleApiError(err) {
  // Placeholder: Phase 2 will show a toast and return safe mock data.
  console.error("API error:", err);
  return { error: "API request failed" };
}

