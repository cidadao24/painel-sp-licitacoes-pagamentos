from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path('config/sources.example.yml')
LATEST_RUN_PATH = Path('data/latest-run.json')
LIVE_ALERTS_PATH = Path('data/live-alerts.json')

SOURCE_URLS = {
    'diario_oficial_sp_home': 'https://diariooficial.prefeitura.sp.gov.br/',
    'metro_sp_noticias': 'https://www.metro.sp.gov.br/pt_BR/imprensa/noticias/',
}

SOURCE_CATEGORIES = {
    'diario_oficial_sp_home': 'diario_oficial',
    'metro_sp_noticias': 'transporte',
}

SOURCE_TITLES = {
    'diario_oficial_sp_home': 'Diário Oficial da Cidade de São Paulo',
    'metro_sp_noticias': 'Metrô de São Paulo — Notícias',
}


def build_live_alerts() -> list[dict]:
    if not LATEST_RUN_PATH.exists():
        return []

    latest_run = json.loads(LATEST_RUN_PATH.read_text(encoding='utf-8'))
    created_at = datetime.now(timezone.utc).isoformat()
    alerts = []

    for item in latest_run:
        source_id = item.get('source_id', 'unknown_source')
        status = item.get('status', 'unknown')
        summary = item.get('summary', 'No summary available.')
        alerts.append(
            {
                'created_at': created_at,
                'category': SOURCE_CATEGORIES.get(source_id, 'general'),
                'title': SOURCE_TITLES.get(source_id, source_id),
                'summary': status + ': ' + summary,
                'evidence': 'Generated automatically from the latest scheduled run output.',
                'source_url': SOURCE_URLS.get(source_id, ''),
                'source_id': source_id,
            }
        )

    return alerts


def main() -> None:
    LIVE_ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    alerts = build_live_alerts()
    LIVE_ALERTS_PATH.write_text(json.dumps(alerts, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
