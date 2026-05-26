"""
Coleta dados de contratos do PNCP com foco no Município de São Paulo.

Antes, o coletor buscava contratos nacionais por data e filtrava depois. Isso
produzia amostras aleatórias e, em caso de falha parcial da API, podia não trazer
nenhum contrato de São Paulo. Agora tentamos estratégias direcionadas primeiro
(município/UF e CNPJ-base da Prefeitura), mantendo a coleta nacional apenas como
fallback diagnóstico.
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
    "User-Agent": "cidadao24-painel-sp-licitacoes-pagamentos/1.2 (+https://github.com/cidadao24/painel-sp-licitacoes-pagamentos)",
}

# Identificadores úteis para tentar reduzir a busca na própria fonte.
SAO_PAULO_IBGE = "3550308"
SAO_PAULO_UF = "SP"
PREFEITURA_SP_CNPJ_BASE = "46395000"
PREFEITURA_SP_CNPJ = "46395000000139"


class FetchDiagnostics(list):
    """Lista simples de eventos diagnósticos serializáveis."""

    def add(self, **kwargs: Any) -> None:
        kwargs.setdefault("ts_utc", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        self.append(kwargs)


def load_parametros() -> dict:
    cfg_path = pathlib.Path("config/parametros.json")
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fetch_paginated(endpoint: str, params: dict, diagnostics: FetchDiagnostics, strategy: str) -> tuple[list, bool, str]:
    """Faz paginação em um endpoint PNCP com tentativas e backoff.

    Retorna (resultados, sucesso, erro_final). Erros 400/404 em parâmetros de
    filtro são tratados como estratégia incompatível, sem derrubar o workflow.
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
                if tentativa < 3:
                    time.sleep(2 * tentativa)
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
    """Estratégias em ordem de preferência.

    A API PNCP pode variar/ignorar parâmetros conforme versão. Mantemos várias
    formas comuns de filtro e registramos no diagnostics quais funcionaram.
    """
    return [
        ("municipio_ibge", {**base, "codigoMunicipioIbge": SAO_PAULO_IBGE}),
        ("municipio_uf_nome", {**base, "uf": SAO_PAULO_UF, "municipio": "São Paulo"}),
        ("municipio_uf_nome_ascii", {**base, "uf": SAO_PAULO_UF, "municipio": "Sao Paulo"}),
        ("cnpj_orgao_base", {**base, "cnpjOrgao": PREFEITURA_SP_CNPJ_BASE}),
        ("cnpj_orgao_completo", {**base, "cnpjOrgao": PREFEITURA_SP_CNPJ}),
        ("cnpj_entidade_base", {**base, "cnpjEntidade": PREFEITURA_SP_CNPJ_BASE}),
        ("cnpj_entidade_completo", {**base, "cnpjEntidade": PREFEITURA_SP_CNPJ}),
    ]


def fetch_targeted_contracts(data_ini, data_fim, diagnostics: FetchDiagnostics) -> tuple[list[dict], int, int, list[dict]]:
    contratos: list[dict] = []
    blocos = 0
    falhas = 0
    strategy_summary: list[dict] = []

    for inicio, fim in date_chunks(data_ini, data_fim, chunk_days=7):
        base = {
            "dataInicial": inicio.strftime("%Y%m%d"),
            "dataFinal": fim.strftime("%Y%m%d"),
        }
        bloco_resultados: list[dict] = []
        bloco_ok = False

        for strategy, params in strategy_params(base):
            blocos += 1
            lote, sucesso, erro = fetch_paginated("/v1/contratos", params, diagnostics, strategy)
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
                # Se uma estratégia direcionada achou dados, não precisamos repetir
                # o mesmo bloco com outras variações de parâmetro.
                break

        contratos.extend(bloco_resultados)
        if not bloco_ok and not bloco_resultados:
            falhas += 1
            diagnostics.add(level="warning", endpoint="/v1/contratos", dataInicial=base["dataInicial"], dataFinal=base["dataFinal"], message="Nenhuma estratégia direcionada retornou contratos para este bloco.")

    return contratos, blocos, falhas, strategy_summary


def fetch_national_fallback(data_ini, data_fim, diagnostics: FetchDiagnostics) -> tuple[list[dict], int, int]:
    contratos: list[dict] = []
    blocos = 0
    falhas = 0

    for inicio, fim in date_chunks(data_ini, data_fim, chunk_days=3):
        blocos += 1
        params = {
            "dataInicial": inicio.strftime("%Y%m%d"),
            "dataFinal": fim.strftime("%Y%m%d"),
        }
        lote, sucesso, erro = fetch_paginated("/v1/contratos", params, diagnostics, "national_fallback")
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

    # O fallback nacional só entra quando a coleta direcionada não encontrou nada.
    # Ele mantém o painel diagnosticável, mas o filtro posterior continua impedindo
    # outros municípios de aparecerem no dashboard.
    fallback: list[dict] = []
    fallback_blocos = 0
    fallback_falhas = 0
    if not targeted:
        diagnostics.add(level="warning", message="Coleta direcionada não retornou contratos; acionando fallback nacional diagnóstico.")
        fallback, fallback_blocos, fallback_falhas = fetch_national_fallback(data_ini, data_fim, diagnostics)
        fallback = dedupe_contracts(fallback)

    contratos = dedupe_contracts(targeted + fallback)
    falhas = targeted_falhas + fallback_falhas
    blocos = targeted_blocos + fallback_blocos
    sucesso = bool(targeted) or bool(fallback)

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
                "target_strategy_summary": strategy_summary[:200],
            },
            f,
            ensure_ascii=False,
        )
    with (outdir / "diagnostics.json").open("w", encoding="utf-8") as f:
        json.dump(list(diagnostics), f, ensure_ascii=False, indent=2)

    print(f"[02] PNCP: contratos={len(contratos)}, targeted={len(targeted)}, fallback={len(fallback)}, blocos={blocos}, falhas={falhas}, sucesso={sucesso}")


if __name__ == "__main__":
    main()
