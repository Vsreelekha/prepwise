/*
Authentication client (Phase 1 placeholder).

Phase 2 will implement:
- token storage in localStorage
- redirect guards for protected pages
- signup/login requests to backend
*/

function saveToken(token) {
  localStorage.setItem("prepwise_token", token);
}

function getToken() {
  return localStorage.getItem("prepwise_token");
}

function removeToken() {
  localStorage.removeItem("prepwise_token");
}

