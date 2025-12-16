const API_BASE = "http://localhost:5000/api";
let authToken = null;
let selectedRouteId = null;

/* ---------------------------------
      AUTHENTICATION HANDLING
----------------------------------*/
const authOverlay = document.getElementById("auth-overlay");
const authToggleBtns = document.querySelectorAll(".auth-toggle-btn");
const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");

authToggleBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    authToggleBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loginForm.classList.toggle("hidden", btn.dataset.auth !== "login");
    signupForm.classList.toggle("hidden", btn.dataset.auth !== "signup");
  });
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value.trim();

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Login failed");
    authToken = data.token;
    authOverlay.style.display = "none";
  } catch (err) {
    alert(err.message);
  }
});

signupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("signup-name").value.trim();
  const email = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value.trim();

  try {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Signup failed");
    authToken = data.token;
    authOverlay.style.display = "none";
  } catch (err) {
    alert(err.message);
  }
});

/* ---------------------------------
      TAB SYSTEM
----------------------------------*/
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".tab-btn")
      .forEach((b) => b.classList.remove("active"));
    document
      .querySelectorAll(".tab-panel")
      .forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

/* ---------------------------------
      MAP INITIALIZATION
----------------------------------*/
// MAPBOX_TOKEN comes from index.html
mapboxgl.accessToken = MAPBOX_TOKEN;

const map = new mapboxgl.Map({
  container: "map",
  style: "mapbox://styles/mapbox/light-v11",
  center: [77.6, 12.97],
  zoom: 11.5,
});

let routeLayers = [];
let currentRoutes = [];
let routeMarkers = [];

function clearMapLayers() {
  routeLayers.forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource(id)) map.removeSource(id);
  });
  routeLayers = [];

  routeMarkers.forEach((m) => m.remove());
  routeMarkers = [];
}

function addMarkers(route) {
  if (!route.source_coords || !route.dest_coords) return;
  const [lon, lat] = route.source_coords;
  const [lon2, lat2] = route.dest_coords;

  routeMarkers.push(
    new mapboxgl.Marker({ color: "#22c55e" }).setLngLat([lon, lat]).addTo(map)
  );
  routeMarkers.push(
    new mapboxgl.Marker({ color: "#ef4444" }).setLngLat([lon2, lat2]).addTo(map)
  );
}

function plotRoute(route, highlight = false) {
  const id = route.route_id;
  if (!route.geometry || !route.geometry.coordinates) return;

  const paintColor =
    route.safety_label === "safe"
      ? "#8ac7a2"
      : route.safety_label === "moderate"
      ? "#f9b26f"
      : "#ff7a88";

  map.addSource(id, {
    type: "geojson",
    data: { type: "Feature", geometry: route.geometry },
  });

  map.addLayer({
    id,
    type: "line",
    source: id,
    paint: {
      "line-color": paintColor,
      "line-width": highlight ? 6 : 4,
      "line-opacity": highlight ? 0.95 : 0.7,
    },
  });

  routeLayers.push(id);
}

function fitRouteView(route) {
  if (!route.geometry || !route.geometry.coordinates) return;
  const bounds = new mapboxgl.LngLatBounds();
  route.geometry.coordinates.forEach((c) => bounds.extend(c));
  map.fitBounds(bounds, { padding: 40 });
}

/* ---------------------------------
      ROUTE FETCH + DISPLAY
----------------------------------*/
const findRoutesBtn = document.getElementById("find-routes-btn");
const routesListEl = document.getElementById("routes-list");
const citySelect = document.getElementById("city-select");
const weatherSelect = document.getElementById("weather-weight");

const scoreToLabel = (s) =>
  s >= 3.5 ? "safe" : s >= 2.5 ? "moderate" : "unsafe";

findRoutesBtn.addEventListener("click", async () => {
  const src = document.getElementById("source-input").value.trim();
  const dst = document.getElementById("dest-input").value.trim();
  const city = citySelect.value.toLowerCase();
  const weatherWeight = weatherSelect.value.toLowerCase();

  if (!src || !dst) {
    alert("Enter both source and destination.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/routes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({
        source_text: src,
        dest_text: dst,
        city,
        weather_weight: weatherWeight,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to fetch routes");

    currentRoutes = data.routes || [];
    if (!currentRoutes.length) {
      alert("No routes found. Try another location.");
      routesListEl.innerHTML = "";
      clearMapLayers();
      return;
    }

    // Relative normalization (visual only) on *final* backend score:
    // best route → closer to 5, worst → closer to 1
    const scores = currentRoutes.map((r) => r.avg_safety_score);
    const maxScore = Math.max(...scores);
    const minScore = Math.min(...scores);

    currentRoutes.forEach((r) => {
      const base = r.avg_safety_score;
      let scaled;
      if (maxScore > minScore) {
        scaled = 1 + 4 * ((base - minScore) / (maxScore - minScore));
      } else {
        scaled = 3.0;
      }
      r.adjusted_score = Math.min(5, Math.max(1, scaled));
      r.safety_label = scoreToLabel(r.adjusted_score);
    });

    selectedRouteId = currentRoutes[0].route_id;

    renderRoutes(currentRoutes);

    clearMapLayers();
    currentRoutes.forEach((r, i) => plotRoute(r, i === 0));
    addMarkers(currentRoutes[0]);
    fitRouteView(currentRoutes[0]);
  } catch (err) {
    alert(err.message);
  }
});

function renderRoutes(routes) {
  routesListEl.innerHTML = "";

  routes.forEach((route) => {
    const colorClass =
      route.safety_label === "safe"
        ? "badge-safe"
        : route.safety_label === "moderate"
        ? "badge-moderate"
        : "badge-unsafe";

    // Explanations from backend (dataset + feedback reasons)
    const explanations = route.explanations || [];
    const explanationHtml = explanations.length
      ? `
        <div class="route-why">
          <button type="button" class="why-btn">Why this score?</button>
          <div class="why-panel hidden">
            <ul>
              ${explanations.map((e) => `<li>${e}</li>`).join("")}
            </ul>
          </div>
        </div>
      `
      : "";

    const div = document.createElement("div");
    div.className = "route-card";

    const adjusted = route.adjusted_score ?? route.avg_safety_score;
    const raw = route.raw_safety_score ?? route.avg_safety_score;

    div.innerHTML = `
      <div class="route-card-header">
        <div class="route-title">${route.name}</div>
        <div class="badge-score ${colorClass}">
          ${adjusted.toFixed(2)} / 5
          <span class="original-score">(Orig: ${raw.toFixed(2)})</span>
        </div>
      </div>

      <div class="route-meta">
        ${route.distance_km.toFixed(1)} km • ${route.duration_min.toFixed(1)} min
      </div>

      ${explanationHtml}
    `;

    // Clicking the whole card highlights route on map
    div.addEventListener("click", () => {
      selectedRouteId = route.route_id;
      clearMapLayers();
      currentRoutes.forEach((r) => plotRoute(r, r.route_id === route.route_id));
      addMarkers(route);
      fitRouteView(route);
    });

    // "Why this score?" toggle (if present)
    const whyBtn = div.querySelector(".why-btn");
    const whyPanel = div.querySelector(".why-panel");
    if (whyBtn && whyPanel) {
      whyBtn.addEventListener("click", (ev) => {
        ev.stopPropagation(); // don’t trigger card click
        whyPanel.classList.toggle("hidden");
      });
    }

    routesListEl.appendChild(div);
  });
}

/* ---------------------------------
      FEEDBACK MODAL + FORM
----------------------------------*/
const feedbackBtn = document.getElementById("feedback-btn");
const feedbackModal = document.getElementById("feedback-modal");
const closeFeedback = document.getElementById("close-feedback");
const feedbackForm = document.getElementById("feedback-form");

const ratingSelect = document.getElementById("feedback-rating");
const streetInput = document.getElementById("feedback-street");
const issueSelect = document.getElementById("feedback-issue");

feedbackBtn.addEventListener("click", () => {
  feedbackModal.classList.remove("hidden");
});

closeFeedback.addEventListener("click", () => {
  feedbackModal.classList.add("hidden");
});

feedbackModal
  .querySelector(".modal-backdrop")
  .addEventListener("click", () => feedbackModal.classList.add("hidden"));

// Toggle required based on rating (1–3 => require details)
ratingSelect.addEventListener("change", () => {
  const rating = parseInt(ratingSelect.value, 10);
  const needsDetails = rating && rating <= 3;
  streetInput.required = needsDetails;
  issueSelect.required = needsDetails;
});

feedbackForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedRouteId) {
    alert("Please select a route first.");
    return;
  }

  const rating = parseInt(ratingSelect.value, 10);
  let streetName = streetInput.value.trim();
  let issueType = issueSelect.value.trim();
  const comments = document.getElementById("feedback-comments").value.trim();
  const city = citySelect.value.toLowerCase();

  if (!rating) {
    alert("Please choose a safety rating.");
    return;
  }

  if (rating <= 3) {
    if (!streetName || !issueType) {
      alert(
        "For ratings 1–3, please specify where you felt unsafe and select an issue type."
      );
      return;
    }
  } else {
    if (!streetName) streetName = "none";
    if (!issueType) issueType = "none";
  }

  try {
    const res = await fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({
        route_id: selectedRouteId,
        rating,
        street_name: streetName,
        issue_type: issueType,
        comments,
        city,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to submit feedback");

    alert("Thank you! Your feedback has been recorded.");
    feedbackModal.classList.add("hidden");
    feedbackForm.reset();
  } catch (err) {
    alert(err.message);
  }
});

/* ---------------------------------
            SOS BUTTON
----------------------------------*/
const sosBtn = document.getElementById("sos-btn");
sosBtn.addEventListener("click", () => {
  window.location.href = "tel:112"; // India emergency number
});

/* ---------------------------------
          LIVE SAFETY TAB
----------------------------------*/
const liveSafetyBtn = document.getElementById("live-safety-btn");
const liveSafetyResult = document.getElementById("live-safety-result");
const radiusSelect = document.getElementById("radius-select");

liveSafetyBtn.addEventListener("click", () => {
  if (!navigator.geolocation) {
    alert("Geolocation not supported in this browser.");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const radius_km = radiusSelect.value;
      const city = citySelect.value.toLowerCase();

      try {
        const res = await fetch(
          `${API_BASE}/live-safety?lat=${lat}&lon=${lon}&radius_km=${radius_km}&city=${city}`
        );
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to compute safety");

        const label = scoreToLabel(data.safety_score);
        const color =
          label === "unsafe"
            ? "#ff7a88"
            : label === "moderate"
            ? "#f9b26f"
            : "#8ac7a2";

        liveSafetyResult.innerHTML = `
          <div>Lat: ${data.lat.toFixed(4)}, Lon: ${data.lon.toFixed(4)}</div>
          <div>Radius: ${data.radius_km} km</div>
          <div>Safety score:
            <strong>${data.safety_score.toFixed(2)} / 5</strong>
            <span style="margin-left:6px; font-weight:600; color:${color}">
              (${
                label === "unsafe"
                  ? "Unsafe"
                  : label === "moderate"
                  ? "Moderate"
                  : "Very safe"
              })
            </span>
          </div>
        `;
      } catch (err) {
        alert(err.message);
      }
    },
    () => alert("Unable to get your location.")
  );
});

/* ---------------------------------
              WEATHER TAB
----------------------------------*/
const weatherBtn = document.getElementById("weather-btn");
const weatherResult = document.getElementById("weather-result");

weatherBtn.addEventListener("click", async () => {
  const locationText = document
    .getElementById("weather-location")
    .value.trim();

  if (!locationText) {
    alert("Enter a location (e.g. Jayanagar, Bengaluru).");
    return;
  }

  try {
    // 1) Geocode address -> lat, lon using Mapbox
    const geoRes = await fetch(
      `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
        locationText
      )}.json?limit=1&access_token=${MAPBOX_TOKEN}`
    );
    const geoData = await geoRes.json();

    if (!geoData.features || !geoData.features.length) {
      alert("Could not find that location. Try a more specific address.");
      return;
    }

    const feature = geoData.features[0];
    const [lon, lat] = feature.center;
    const placeName = feature.place_name;

    // 2) Call backend weather endpoint with lat/lon
    const res = await fetch(`${API_BASE}/weather?lat=${lat}&lon=${lon}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to fetch weather");

    const tempK = data.main.temp;
    const tempC = tempK - 273.15;
    const desc = data.weather[0].description;

    weatherResult.innerHTML = `
      <div><strong>${placeName}</strong></div>
      <div>${tempC.toFixed(1)} °C • ${desc}</div>
      <div class="muted" style="margin-top:4px">
        Safety score can be reduced slightly at night or during heavy rain.
      </div>
    `;
  } catch (err) {
    alert(err.message);
  }
});
