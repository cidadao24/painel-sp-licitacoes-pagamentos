"""
Coleta dados de contratos do PNCP com foco no Município de São Paulo.

A coleta direcionada é usada com parcimônia: se a API começar a responder com
timeouts/503, o script interrompe essa etapa e volta para a coleta nacional em
blocos, deixando o filtro posterior separar São Paulo. Isso evita que uma rodada
ruim da API apague o painel inteiro.
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
    "User-Agent": "cidadao24-painel-sp-licitacoes-pagamentos/1.3 (+https://github.com/cidadao24/painel-sp-licitacoes-pagamentos)",
}

SAO_PAULO_IBGE = "3550308"
PREFEITURA_SP_CNPJ_BASE = "46395000"
TARGETED_FAILURE_LIMIT = 3


class FetchDiagnostics(list):
    """Lista simples de eventos diagnósticos serializáveis."""

    def add(self, **kwargs: Any) -> None:
        kwargs.setdefault("ts_utc", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        self.append(kwargs)


def load_parametros() -> dict:
    cfg_path = pathlib.Path("config/parametros.json")
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_contracts() -> list[dict]:
    path = pathlib.Path("data/raw/pncp/contratos.json")
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_paginated(endpoint: str, params: dict, diagnostics: FetchDiagnostics, strategy: str, timeout: int = 30) -> tuple[list, bool, str]:
    """Faz paginação em um endpoint PNCP com tentativas e backoff curto."""
    resultados: list = []
    pagina = 1
    url = f"{BASE_URL}{endpoint}"

    while True:
        page_params = dict(params)
        page_params["pagina"] = pagina
        page_params["tamanhoPagina"] = 100
        last_error = ""

        for tentativa in range(1, 3):
            try:
                resp = requests.get(url, params=page_params, headers=HEADERS, timeout=timeout)
                if resp.status_code in (400, 404, 422):
                    msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
                    diagnostics.add(level="warning", strategy=strategy, endpoint=endpoint, pagina=pagina, params=page_params, error=msg)
                    return resultados, False, msg
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                diagnostics.add(level="warning", strategy=strategy, endpoint=endpoint, pagina=pagina, tentativa=tentativa, params=page_params, error=last_error)
                if tentativa < 2:
                    time.sleep(2)
        else:
            return resultados, False, last_error

        itens = data.get("data", [])
        if not itens:
            diagnostics.add(level="info", strategy=strategy, endpoint=endpoint, pagina=pagina, itens=0, params=page_params)
            return resultados, True, ""

        resultados.extend(itens)
        total_paginas = data.get("totalPaginas") or 1
        diagnostics.add(level="info", strategy=strategy, endpoint=endpoint, pagina=pagina, total_paginas=total_paginas, itens=len(itens), params=page_params)

        if pagina >= total_paginas:
            return resultados, True, ""
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


def strategy_params(base: dict) -> list[tuple[str, dict]]:
    # Só duas tentativas direcionadas para evitar bombardear uma API instável.
    return [
        ("municipio_ibge", {**base, "codigoMunicipioIbge": SAO_PAULO_IBGE}),
        ("cnpj_orgao_base", {**base, "cnpjOrgao": PREFEITURA_SP_CNPJ_BASE}),
    ]


def fetch_targeted_contracts(data_ini, data_fim, diagnostics: FetchDiagnostics) -> tuple[list[dict], int, int, list[dict]]:
    contratos: list[dict] = []
    blocos = 0
    falhas = 0
    consecutive_failures = 0
    strategy_summary: list[dict] = []

    # Testa primeiro os blocos mais recentes; são mais úteis ao painel.
    chunks = list(date_chunks(data_ini, data_fim, chunk_days=7))
    chunks.reverse()

    for inicio, fim in chunks:
        if consecutive_failures >= TARGETED_FAILURE_LIMIT:
            diagnostics.add(level="warning", message="Circuit breaker: coleta direcionada interrompida após falhas consecutivas.", consecutive_failures=consecutive_failures)
            break

        base = {
            "dataInicial": inicio.strftime("%Y%m%d"),
            "dataFinal": fim.strftime("%Y%m%d"),
        }
        bloco_resultados: list[dict] = []
        bloco_ok = False

        for strategy, params in strategy_params(base):
            blocos += 1
            lote, sucesso, erro = fetch_paginated("/v1/contratos", params, diagnostics, strategy, timeout=25)
            strategy_summary.append({
                "strategy": strategy,
                "dataInicial": base["dataInicial"],
                "dataFinal": base["dataFinal"],
                "success": bool(sucesso),
                "items": len(lote),
                "error": erro,
            })
            bloco_resultados.extend(lote)
            if sucesso and lote:
                bloco_ok = True
                consecutive_failures = 0
                break

        contratos.extend(bloco_resultados)
        if not bloco_ok and not bloco_resultados:
            falhas += 1
            consecutive_failures += 1
            diagnostics.add(level="warning", endpoint="/v1/contratos", dataInicial=base["dataInicial"], dataFinal=base["dataFinal"], message="Nenhuma estratégia direcionada retornou contratos para este bloco.")

    return contratos, blocos, falhas, strategy_summary


def fetch_national_fallback(data_ini, data_fim, diagnostics: FetchDiagnostics) -> tuple[list[dict], int, int]:
    contratos: list[dict] = []
    blocos = 0
    falhas = 0

    for inicio, fim in date_chunks(data_ini, data_fim, chunk_days=7):
        blocos += 1
        params = {
            "dataInicial": inicio.strftime("%Y%m%d"),
            "dataFinal": fim.strftime("%Y%m%d"),
        }
        lote, sucesso, erro = fetch_paginated("/v1/contratos", params, diagnostics, "national_fallback", timeout=45)
        contratos.extend(lote)
        if not sucesso:
            falhas += 1
            diagnostics.add(level="error", endpoint="/v1/contratos", dataInicial=params["dataInicial"], dataFinal=params["dataFinal"], message="Fallback nacional falhou ou retornou parcial.", error=erro, itens_parciais=len(lote))

    return contratos, blocos, falhas


def main():
    parametros = load_parametros()
    janela_dias = parametros.get("janela_pncp_dias", 90)
    hoje = datetime.utcnow().date()
    data_fim = hoje
    data_ini = hoje - timedelta(days=janela_dias)

    diagnostics = FetchDiagnostics()
    targeted, targeted_blocos, targeted_falhas, strategy_summary = fetch_targeted_contracts(data_ini, data_fim, diagnostics)
    targeted = dedupe_contracts(targeted)

    fallback: list[dict] = []
    fallback_blocos = 0
    fallback_falhas = 0
    if not targeted:
        diagnostics.add(level="warning", message="Coleta direcionada sem dados aproveitáveis; usando fallback nacional em blocos semanais.")
        fallback, fallback_blocos, fallback_falhas = fetch_national_fallback(data_ini, data_fim, diagnostics)
        fallback = dedupe_contracts(fallback)

    contratos = dedupe_contracts(targeted + fallback)
    existing_contracts = load_existing_contracts()
    preserved_previous = False
    if not contratos and existing_contracts:
        diagnostics.add(level="warning", message="Coleta PNCP não retornou dados novos; preservando contratos brutos anteriores para evitar apagar o painel.", existing_contracts=len(existing_contracts))
        contratos = existing_contracts
        preserved_previous = True

    falhas = targeted_falhas + fallback_falhas
    blocos = targeted_blocos + fallback_blocos
    sucesso = bool(contratos)

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
                "partial": bool(falhas),
                "failed_chunks": falhas,
                "total_chunks": blocos,
                "contracts_collected": len(contratos),
                "targeted_contracts_collected": len(targeted),
                "fallback_contracts_collected": len(fallback),
                "preserved_previous_contracts": preserved_previous,
                "target_strategy_summary": strategy_summary[:80],
            },
            f,
            ensure_ascii=False,
        )
    with (outdir / "diagnostics.json").open("w", encoding="utf-8") as f:
        json.dump(list(diagnostics), f, ensure_ascii=False, indent=2)

    print(f"[02] PNCP: contratos={len(contratos)}, targeted={len(targeted)}, fallback={len(fallback)}, preserved_previous={preserved_previous}, blocos={blocos}, falhas={falhas}, sucesso={sucesso}")


if __name__ == "__main__":
    main()
