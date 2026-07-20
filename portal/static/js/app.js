// Highlights the selected .pay-option label. Done in JS rather than CSS
// :has() — that selector isn't supported on older Android WebViews shipped
// with budget/"Android Go" phones, which many customers use.
function markSelectedPayOption() {
  document.querySelectorAll(".pay-option").forEach(function (el) {
    var input = el.querySelector("input[type=radio]");
    el.classList.toggle("selected", !!(input && input.checked));
  });
}

document.addEventListener("change", function (e) {
  if (e.target.matches && e.target.matches(".pay-option input[type=radio]")) {
    markSelectedPayOption();
  }
});
document.addEventListener("DOMContentLoaded", markSelectedPayOption);
document.body.addEventListener("htmx:afterSettle", markSelectedPayOption);

// Switch language in place rather than following the /lang/{code} link's
// server-side redirect — that redirect targets HTTP_REFERER, which the
// app's own Referrer-Policy: no-referrer header (set for every response)
// blanks out, so it always fell back to bouncing the user to /login. A
// still-logged-in customer landing on the login page reads as "changing
// language logged me out" even though the session itself never changed.
document.addEventListener("click", function (e) {
  var link = e.target.closest && e.target.closest(".lang-toggle a");
  if (!link) return;
  var match = link.getAttribute("href").match(/^\/lang\/([a-z]+)$/);
  if (!match) return;
  e.preventDefault();
  document.cookie = "lang=" + match[1] + "; path=/; max-age=" + (365 * 24 * 3600) + "; samesite=Lax";
  window.location.reload();
});

// Auto-insert "/" while typing DD/MM/YYYY into the plain-text DOB field
// (a native <input type="date"> renders in the browser's own locale format,
// not necessarily DD/MM/YYYY, so this field is deliberately type="text").
document.addEventListener("input", function (e) {
  if (!(e.target.matches && e.target.matches("#dob"))) return;
  var digits = e.target.value.replace(/\D/g, "").slice(0, 8);
  var parts = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 8)].filter(Boolean);
  e.target.value = parts.join("/");
});

// Ask the browser's own Geolocation permission prompt for the customer's
// device location (used for the audit trail — see device_geo.py); if
// denied, unsupported, or the customer just never answers, the server
// falls back to IP-based geolocation on its own — this is a pure best-
// effort enhancement, nothing here blocks any page from working.
//
// Skips the request entirely if a device_geo cookie already exists (set
// by a previous successful fix, valid for 1 hour) — getCurrentPosition
// has a real battery/latency cost on the budget phones this portal is
// built for, so there's no reason to re-invoke it on every navigation.
function hasDeviceGeoCookie() {
  return document.cookie.indexOf("device_geo=") !== -1;
}

function sendDeviceLocation(position) {
  var lat = position.coords.latitude;
  var lon = position.coords.longitude;
  new Image().src = "/device-location?lat=" + encodeURIComponent(lat) + "&lon=" + encodeURIComponent(lon);
}

function requestDeviceLocation() {
  if (!navigator.geolocation || hasDeviceGeoCookie()) return;
  navigator.geolocation.getCurrentPosition(
    sendDeviceLocation,
    function () {}, // denied/unavailable/timed out — IP fallback handles it server-side
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 }
  );
}

document.addEventListener("DOMContentLoaded", requestDeviceLocation);
