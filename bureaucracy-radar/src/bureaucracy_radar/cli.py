from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import yaml

from .diffing import compare_text
from .fetchers import fetch_url, save_raw_snapshot
from .storage import connect, get_latest_snapshot, init_db, insert_alert, insert_snapshot


def load_sources(config_path: str) -> list[dict]:
    data = yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
    return data.get('sources', [])


def cmd_init_db(args: argparse.Namespace) -> None:
    db_path = os.getenv('BUREAUCRACY_RADAR_DB', './data/bureaucracy_radar.db')
    conn = connect(db_path)
    init_db(conn)
    print(json.dumps({'status': 'ok', 'db_path': db_path}, ensure_ascii=False))


def _fetch_error_summary(source_id: str, exc: Exception) -> dict:
    return {
        'source_id': source_id,
        'status': 'fetch_error',
        'summary': f'{type(exc).__name__}: {exc}',
    }


def cmd_run(args: argparse.Namespace) -> None:
    db_path = os.getenv('BUREAUCRACY_RADAR_DB', './data/bureaucracy_radar.db')
    conn = connect(db_path)
    init_db(conn)

    sources = load_sources(args.config)
    output = []

    for source in sources:
        source_id = source['id']
        fetched_at = datetime.now(timezone.utc).isoformat()

        try:
            result = fetch_url(source['url'])
        except Exception as exc:  # Keep scheduled deploys alive when a public source blocks/limits bots.
            print(
                f'[bureaucracy-radar] fetch failed for {source_id}: {type(exc).__name__}: {exc}',
                file=sys.stderr,
            )
            output.append(_fetch_error_summary(source_id, exc))
            continue

        latest = get_latest_snapshot(conn, source_id)

        save_raw_snapshot(Path('./data/raw'), source_id, result.raw_bytes)

        if latest is None:
            insert_snapshot(conn, source_id, fetched_at, result.content_hash, result.text)
            output.append({'source_id': source_id, 'status': 'initial_snapshot', 'summary': 'Primeiro snapshot registrado.'})
            continue

        diff = compare_text(latest['text_content'], result.text)
        insert_snapshot(conn, source_id, fetched_at, result.content_hash, result.text)

        if diff.changed:
            insert_alert(conn, source_id, fetched_at, diff.summary, diff.diff_text)

        output.append({'source_id': source_id, 'status': 'changed' if diff.changed else 'unchanged', 'summary': diff.summary})

    print(json.dumps(output, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Bureaucracy Radar MVP')
    subparsers = parser.add_subparsers(dest='command', required=True)

    init_db_parser = subparsers.add_parser('init-db', help='Inicializa o banco SQLite')
    init_db_parser.set_defaults(func=cmd_init_db)

    run_parser = subparsers.add_parser('run', help='Executa a coleta e comparação')
    run_parser.add_argument('--config', required=True, help='Caminho do YAML de fontes')
    run_parser.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
