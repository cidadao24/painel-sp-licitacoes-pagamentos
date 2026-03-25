async function loadAlerts() {
  const container = document.getElementById('alerts');
  try {
    const response = await fetch('../data/alerts.example.json');
    const alerts = await response.json();

    if (!Array.isArray(alerts) || alerts.length === 0) {
      container.innerHTML = '<div class="card">No alerts yet.</div>';
      return;
    }

    container.innerHTML = alerts.map(alert => `
      <div class="card">
        <div class="meta">${alert.created_at} · <span class="pill">${alert.category}</span></div>
        <h2>${alert.title}</h2>
        <p>${alert.summary}</p>
        <details>
          <summary>Evidence</summary>
          <pre>${alert.evidence}</pre>
        </details>
        <p><a href="${alert.source_url}" target="_blank" rel="noopener noreferrer">Open source</a></p>
      </div>
    `).join('');
  } catch (error) {
    container.innerHTML = `<div class="card">Failed to load alerts: ${error.message}</div>`;
  }
}

loadAlerts();
