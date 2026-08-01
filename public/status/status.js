async function loadManifest() {
  const response = await fetch("/status/manifest.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`manifest ${response.status}`);
  }
  return response.json();
}

function healthClass(state) {
  return state || "unknown";
}

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function renderCoverage(root, coverage) {
  if (!coverage) {
    root.innerHTML = '<p class="muted">No snapshot yet.</p>';
    return;
  }
  const items = [
    ["Coverage", coverage.percent != null ? `${coverage.percent.toFixed(1)}%` : "—"],
    ["Passed", coverage.passed ?? 0],
    ["Failed", coverage.failed ?? 0],
    ["Skipped", coverage.skipped ?? 0],
  ];
  root.innerHTML = items
    .map(
      ([label, value]) =>
        `<div class="stat"><div class="value">${value}</div><div class="label">${label}</div></div>`,
    )
    .join("");
}

function renderComponents(root, components) {
  if (!components?.length) {
    root.innerHTML = '<p class="muted">No components configured.</p>';
    return;
  }
  root.innerHTML = components
    .map(
      (item) => `
      <article class="component-card">
        <header>
          <strong>${item.label}</strong>
          <span class="badge ${healthClass(item.health)}">${item.health}</span>
        </header>
        <p class="muted">Layer: ${item.layer} · ID: ${item.id}</p>
      </article>`,
    )
    .join("");
}

function renderTimeline(root, incidents) {
  if (!incidents?.length) {
    root.innerHTML = '<p class="muted">No incidents recorded.</p>';
    return;
  }
  root.innerHTML = incidents
    .map(
      (item) => `
      <article class="incident ${item.state}">
        <h3>${item.title}</h3>
        <p>${item.summary || ""}</p>
        <p><strong>${item.incidentType || item.recordKind}</strong> · ${item.layer} / ${item.component}</p>
        <p>${formatDate(item.timestamp)} · state: ${item.state}</p>
      </article>`,
    )
    .join("");
}

function renderByLayer(root, historyByLayer) {
  const layers = Object.keys(historyByLayer || {});
  if (!layers.length) {
    root.innerHTML = '<p class="muted">No layer history.</p>';
    return;
  }
  root.innerHTML = layers
    .map((layer) => {
      const items = historyByLayer[layer]
        .map(
          (item) =>
            `<li><strong>${item.incidentType || "snapshot"}</strong> — ${formatDate(item.timestamp)} — ${item.state}</li>`,
        )
        .join("");
      return `<article class="layer-card"><header><strong>${layer}</strong></header><ul>${items}</ul></article>`;
    })
    .join("");
}

async function init() {
  const overall = document.getElementById("overall-label");
  const generated = document.getElementById("generated-at");
  try {
    const manifest = await loadManifest();
    const state = healthClass(manifest.overallState);
    overall.textContent = `Overall: ${manifest.overallState}`;
    overall.className = `overall ${state}`;
    generated.textContent = `Updated ${formatDate(manifest.generatedAt)}`;
    renderCoverage(document.getElementById("coverage"), manifest.testCoverage);
    renderComponents(document.getElementById("components"), manifest.components);
    renderTimeline(document.getElementById("timeline"), manifest.incidents);
    renderByLayer(document.getElementById("by-layer"), manifest.historyByLayer);
  } catch (error) {
    overall.textContent = "Status unavailable";
    overall.className = "overall majorOutage";
    generated.textContent = String(error);
  }
}

init();
