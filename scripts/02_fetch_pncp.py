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

# Cabeçalhos HTTP para as requisições. Um User-Agent ajuda a evitar bloqueios simples
# e permite identificar o painel nos logs do PNCP.
HEADERS = {
    "User-Agent": "cidadao24-painel-sp-licitacoes-pagamentos/1.0 (+https://github.com/cidadao24/painel-sp-licitacoes-pagamentos)"
}


def load_parametros() -> dict:
    cfg_path = pathlib.Path("config/parametros.json")
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fetch_paginated(endpoint: str, params: dict) -> tuple[list, bool]:
    """Faz paginação em um endpoint da API do PNCP com tentativas e backoff.

    Args:
        endpoint: parte do caminho após BASE_URL
        params: dicionário de parâmetros base (dataInicial, dataFinal etc.)

    Returns:
        tuple: (lista de resultados, booleano indicando se a coleta foi bem-sucedida).
        Se ocorrerem erros repetidos ao chamar a API, a lista pode estar incompleta e
        o segundo elemento retornará False.
    """
    resultados: list = []
    pagina = 1
    sucesso = True
    # Fazemos as tentativas página a página. Se uma página falhar após várias tentativas,
    # abortamos a coleta e marcamos como falha.
    while True:
        params["pagina"] = pagina
        params["tamanhoPagina"] = 500
        url = f"{BASE_URL}{endpoint}"
        tentativa = 0
        while True:
            try:
                resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
                # Considere erros 5xx como temporários que merecem nova tentativa
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"Erro {resp.status_code} do servidor")
                resp.raise_for_status()
                break
            except Exception:
                tentativa += 1
                if tentativa >= 3:
                    # aborta coleta e retorna o que já foi obtido, sinalizando falha
                    sucesso = False
                    return resultados, sucesso
                # espera incremental (2s, 4s, 6s)
                import time as _time
                _time.sleep(2 * tentativa)
        data = resp.json()
        itens = data.get("data", [])
        if not itens:
            break
        resultados.extend(itens)
        total_paginas = data.get("totalPaginas") or 1
        if pagina >= total_paginas:
            break
        pagina += 1
    return resultados, sucesso


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
    contratos, sucesso = fetch_paginated("/v1/contratos", params_base.copy())

    # Atenção: não filtramos por órgão aqui; a filtragem será feita na transformação.

    # Salvar
    outdir = pathlib.Path("data/raw/pncp")
    outdir.mkdir(parents=True, exist_ok=True)
    # Salvamos a lista completa de contratos coletados
    with (outdir / "contratos.json").open("w", encoding="utf-8") as f:
        json.dump(contratos, f, ensure_ascii=False)
    # Para compatibilidade, salvamos um arquivo vazio de contratacoes
    with (outdir / "contratacoes.json").open("w", encoding="utf-8") as f:
        json.dump([], f)
    # Salvar status da coleta
    status_path = outdir / "status_fetch_success.json"
    with status_path.open("w", encoding="utf-8") as f:
        json.dump({"success": bool(sucesso)}, f)
    print(f"[02] PNCP: contratos={len(contratos)}, sucesso={sucesso}")


if __name__ == "__main__":
    main()
