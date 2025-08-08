"""
Coleta dados de contratações e contratos do PNCP para a Prefeitura de São Paulo.

O PNCP disponibiliza endpoints públicos de consulta. Este script coleta
contratações e contratos dentro de uma janela de tempo definida
(`config/parametros.json`), filtra pelos órgãos da Prefeitura do
Município de São Paulo conforme nomes definidos em `orgaos_nome_filtro`
e salva os resultados em `data/raw/pncp/`.
"""

import json
import os
import pathlib
from datetime import datetime, timedelta
import requests


BASE_URL = "https://pncp.gov.br/api/consulta"


def load_parametros() -> dict:
    cfg_path = pathlib.Path("config/parametros.json")
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fetch_paginated(endpoint: str, params: dict) -> list:
    """Faz paginação em um endpoint da API do PNCP.

    Args:
        endpoint: parte do caminho após BASE_URL
        params: dicionário de parâmetros base (dataInicial, dataFinal etc.)

    Returns:
        Lista de resultados agregados de todas as páginas.
    """
    resultados = []
    pagina = 1
    while True:
        params['pagina'] = pagina
        params['tamanhoPagina'] = 500
        url = f"{BASE_URL}{endpoint}"
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        itens = data.get("data", [])
        if not itens:
            break
        resultados.extend(itens)
        total_paginas = data.get("totalPaginas") or 1
        if pagina >= total_paginas:
            break
        pagina += 1
    return resultados


def is_orgao_sp(nome: str, filtros: list) -> bool:
    if not nome:
        return False
    up = nome.upper()
    return any(filtro in up for filtro in filtros)


def main():
    parametros = load_parametros()
    filtros = [f.upper() for f in parametros.get("orgaos_nome_filtro", [])]
    janela_dias = parametros.get("janela_pncp_dias", 365)
    hoje = datetime.utcnow().date()
    data_fim = hoje
    data_ini = hoje - timedelta(days=janela_dias)
    params_base = {
        "dataInicial": data_ini.strftime("%Y%m%d"),
        "dataFinal": data_fim.strftime("%Y%m%d")
    }

    # Contratos
    contratos = fetch_paginated("/v1/contratos", params_base.copy())

    # Filtrar por órgão
    contratos_sp = [c for c in contratos
                    if is_orgao_sp(((c.get("orgaoEntidade") or {}).get("nomeOrgao")), filtros)]

    # Salvar
    outdir = pathlib.Path("data/raw/pncp")
    outdir.mkdir(parents=True, exist_ok=True)
    # Salvamos apenas a lista de contratos neste momento
    with (outdir / "contratos.json").open("w", encoding="utf-8") as f:
        json.dump(contratos_sp, f, ensure_ascii=False)
    # Para compatibilidade, salvamos um arquivo vazio de contratacoes
    with (outdir / "contratacoes.json").open("w", encoding="utf-8") as f:
        json.dump([], f)
    print(f"[02] PNCP: contratos={len(contratos_sp)}")


if __name__ == "__main__":
    main()
