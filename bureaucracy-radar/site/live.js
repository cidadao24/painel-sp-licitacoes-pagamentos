async function loadAlerts() {
  const container = document.getElementById('alerts');
  try {
    const response = await fetch('../data/live-alerts.json', { cache: 'no-store' });
    const alerts = await response.json();

    if (!Array.isArray(alerts) || alerts.length === 0) {
      container.innerHTML = '<div class="card">No live alerts yet.</div>';
      return;
    }

    container.innerHTML = alerts.map(function(alert) {
      const meta = (alert.created_at || 'unknown time') + ' · ' + (alert.category || 'general');
      const title = alert.title || alert.source_id || 'Untitled alert';
      const summary = alert.summary || 'No summary available.';
      const evidence = alert.evidence ? '<details><summary>Evidence</summary><pre>' + alert.evidence + '</pre></details>' : '';
      const source = alert.source_url ? '<p><a href="' + alert.source_url + '" target="_blank" rel="noopener noreferrer">Open source</a></p>' : '';
      return '<div class="card"><div class="meta">' + meta + '</div><h2>' + title + '</h2><p>' + summary + '</p>' + evidence + source + '</div>';
    }).join('');
  } catch (error) {
    container.innerHTML = '<div class="card">Failed to load live alerts: ' + error.message + '</div>';
  }
}

loadAlerts();
