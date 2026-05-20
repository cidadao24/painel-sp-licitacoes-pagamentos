"""
Coleta dados de contratações e contratos do PNCP para a Prefeitura de São Paulo.

O PNCP disponibiliza endpoints públicos de consulta. Este script coleta
contratos dentro de uma janela de tempo definida (`config/parametros.json`),
com paginação em blocos menores de datas para reduzir timeouts/erros
intermitentes da API, e salva os resultados em `data/raw/pncp/`.
"""

import json
import pathlib
import time
from datetime import datetime, timedelta
from typing import Any

import requests


BASE_URL = "https://pncp.gov.br/api/consulta"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "cidadao24-painel-sp-licitacoes-pagamentos/1.1 (+https://github.com/cidadao24/painel-sp-licitacoes-pagamentos)",
}


class FetchDiagnostics(list):
    """Lista simples de eventos diagnósticos serializáveis."""

    def add(self, **kwargs: Any) -> None:
        kwargs.setdefault("ts_utc", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        self.append(kwargs)


def load_parametros() -> dict:
    cfg_path = pathlib.Path("config/parametros.json")
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fetch_paginated(endpoint: str, params: dict, diagnostics: FetchDiagnostics) -> tuple[list, bool]:
    """Faz paginação em um endpoint da API do PNCP com tentativas e backoff.

    Retorna (resultados, sucesso). Se uma página falhar após tentativas, retorna
    os dados já coletados naquele bloco e sucesso=False, sem explodir o workflow.
    """
    resultados: list = []
    pagina = 1
    url = f"{BASE_URL}{endpoint}"

    while True:
        page_params = dict(params)
        page_params["pagina"] = pagina
        page_params["tamanhoPagina"] = 100
        last_error = ""

        for tentativa in range(1, 4):
            try:
                resp = requests.get(url, params=page_params, headers=HEADERS, timeout=45)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                diagnostics.add(
                    level="warning",
                    endpoint=endpoint,
                    pagina=pagina,
                    tentativa=tentativa,
                    params=page_params,
                    error=last_error,
                )
                if tentativa < 3:
                    time.sleep(2 * tentativa)
        else:
            return resultados, False

        itens = data.get("data", [])
        if not itens:
            return resultados, True

        resultados.extend(itens)
        total_paginas = data.get("totalPaginas") or 1
        diagnostics.add(
            level="info",
            endpoint=endpoint,
            pagina=pagina,
            total_paginas=total_paginas,
            itens=len(itens),
            params=page_params,
        )

        if pagina >= total_paginas:
            return resultados, True
        pagina += 1


def date_chunks(start_date, end_date, chunk_days: int = 7):
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_date)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def dedupe_contracts(contratos: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in contratos:
        key = (
            item.get("numeroControlePNCP"),
            item.get("numeroContratoEmpenho"),
            item.get("anoContrato"),
            json.dumps(item.get("orgaoEntidade", {}), sort_keys=True, ensure_ascii=False),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def main():
    parametros = load_parametros()
    janela_dias = parametros.get("janela_pncp_dias", 90)
    hoje = datetime.utcnow().date()
    data_fim = hoje
    data_ini = hoje - timedelta(days=janela_dias)

    diagnostics = FetchDiagnostics()
    contratos: list[dict] = []
    falhas = 0
    blocos = 0

    for inicio, fim in date_chunks(data_ini, data_fim, chunk_days=7):
        blocos += 1
        params_base = {
            "dataInicial": inicio.strftime("%Y%m%d"),
            "dataFinal": fim.strftime("%Y%m%d"),
        }
        lote, sucesso_lote = fetch_paginated("/v1/contratos", params_base, diagnostics)
        contratos.extend(lote)
        if not sucesso_lote:
            falhas += 1
            diagnostics.add(
                level="error",
                endpoint="/v1/contratos",
                dataInicial=params_base["dataInicial"],
                dataFinal=params_base["dataFinal"],
                message="Bloco encerrado com falha após tentativas; seguindo para o próximo bloco.",
                itens_parciais=len(lote),
            )

    contratos = dedupe_contracts(contratos)
    sucesso = falhas == 0 or len(contratos) > 0

    outdir = pathlib.Path("data/raw/pncp")
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "contratos.json").open("w", encoding="utf-8") as f:
        json.dump(contratos, f, ensure_ascii=False)
    with (outdir / "contratacoes.json").open("w", encoding="utf-8") as f:
        json.dump([], f)
    with (outdir / "status_fetch_success.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "success": bool(sucesso),
                "partial": bool(falhas and contratos),
                "failed_chunks": falhas,
                "total_chunks": blocos,
                "contracts_collected": len(contratos),
            },
            f,
            ensure_ascii=False,
        )
    with (outdir / "diagnostics.json").open("w", encoding="utf-8") as f:
        json.dump(list(diagnostics), f, ensure_ascii=False, indent=2)

    print(f"[02] PNCP: contratos={len(contratos)}, blocos={blocos}, falhas={falhas}, sucesso={sucesso}")


if __name__ == "__main__":
    main()
