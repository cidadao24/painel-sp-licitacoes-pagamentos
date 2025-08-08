"""
Transforma dados brutos do PNCP e gera arquivos JSON processados para o painel.

Este script carrega os dados brutos de `data/raw/pncp/contratacoes.json` e
`data/raw/pncp/contratos.json`, cria listas de fatos e fornecedores, e
gera um conjunto inicial de `flags` com alertas simples.  
Também lê (placeholder) de pagamentos da PMSP caso exista.
"""

import json
import os
import pathlib
from collections import defaultdict

# Ajustar sys.path para permitir import do módulo utils quando executado como script
import sys
current_dir = pathlib.Path(__file__).resolve()
repo_root = current_dir.parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.utils import parse_money, norm_text
from typing import List, Dict

def load_parametros() -> Dict:
    """Carrega parâmetros do arquivo config/parametros.json."""
    cfg_path = pathlib.Path("config/parametros.json")
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def is_orgao_sp(nome: str, filtros: List[str]) -> bool:
    """Retorna True se o nome do órgão corresponder a algum filtro.

    A comparação é feita de forma robusta:
    - remove acentos e normaliza espaços via ``norm_text``;
    - converte tudo para maiúsculas;
    - verifica se qualquer filtro (também normalizado) está contido no nome.

    Isso permite que filtros como "PREFEITURA" ou "SAO PAULO" casem com
    "Prefeitura do Município de São Paulo" ou "PREFEITURA MUNICÍPIO SAO PAULO",
    mesmo com acentos diferentes.
    """
    if not nome:
        return False
    up = norm_text(nome).upper()
    for f in filtros:
        if norm_text(f).upper() in up:
            return True
    return False


def load_json(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    data_processed_dir = pathlib.Path("data/processed")
    data_processed_dir.mkdir(parents=True, exist_ok=True)

    contratacoes = load_json("data/raw/pncp/contratacoes.json")
    contratos = load_json("data/raw/pncp/contratos.json")

    # Carregar status de coleta para detectar falhas no fetch
    status_path = pathlib.Path("data/raw/pncp/status_fetch_success.json")
    fetch_failed = False
    if status_path.exists():
        try:
            with status_path.open("r", encoding="utf-8") as f:
                status_data = json.load(f)
                fetch_failed = not bool(status_data.get("success", True))
        except Exception:
            fetch_failed = True
    # Carregar filtros de órgão a partir dos parâmetros
    parametros = load_parametros()
    filtros = [f.upper() for f in parametros.get("orgaos_nome_filtro", [])]

    fatos_contratos: list = []
    fornecedores_agg: Dict[str, Dict] = defaultdict(lambda: {"cnpj": "", "nome": "", "total_contratado": 0.0, "total_pago": 0.0})

    for c in contratos:
        # Se a coleta falhou, não processamos os contratos
        if fetch_failed:
            continue
        orgao = ((c.get("orgaoEntidade") or {}).get("nomeOrgao")) or ""
        # Se houver filtros definidos, filtrar pelos nomes dos órgãos
        if filtros and not is_orgao_sp(orgao, filtros):
            continue
        fornecedor = ((c.get("fornecedor") or {}).get("razaoSocial")) or ""
        cnpj = ((c.get("fornecedor") or {}).get("cpfCnpj")) or ""
        objeto = c.get("objeto") or ""
        valor_estimado = parse_money(c.get("valorEstimado"))
        valor_contratado = parse_money(c.get("valorFinal"))
        pub = c.get("dataPublicacao") or c.get("dataInclusao")
        vig_fim = c.get("dataVigenciaFim") or ""

        fatos_contratos.append({
            "data_publicacao": pub,
            "orgao": orgao,
            "fornecedor_nome": fornecedor,
            "fornecedor_cnpj": cnpj,
            "objeto": objeto,
            "valor_estimado": valor_estimado,
            "valor_contratado": valor_contratado,
            "vigencia_fim": vig_fim
        })

        key = cnpj or norm_text(fornecedor)
        f = fornecedores_agg[key]
        f["cnpj"] = cnpj
        f["nome"] = fornecedor
        f["total_contratado"] += valor_contratado

    # Pagamentos (placeholder): carregar arquivo se existir
    fatos_pagamentos = []
    pag_path = "data/raw/sp/placeholder.json"
    if os.path.exists(pag_path):
        # Nenhum pagamento real carregado ainda
        fatos_pagamentos = []

    # Agregar lista de fornecedores somente se a coleta não falhou
    fornecedores = list(fornecedores_agg.values()) if not fetch_failed else []
    # Construir flags
    if fetch_failed:
        flags = {"fetch_failed": True}
    else:
        topN = sorted(fornecedores, key=lambda x: x["total_contratado"], reverse=True)[:5]
        flags = {
            "top_fornecedores_contratados": topN,
            "msg": "Alertas completos só serão gerados após integração dos pagamentos PMSP."
        }

    # Salvar
    with open(data_processed_dir / "fatos_contratos.json", "w", encoding="utf-8") as f:
        json.dump(fatos_contratos, f, ensure_ascii=False)
    with open(data_processed_dir / "fatos_pagamentos.json", "w", encoding="utf-8") as f:
        json.dump(fatos_pagamentos, f, ensure_ascii=False)
    with open(data_processed_dir / "fornecedores.json", "w", encoding="utf-8") as f:
        json.dump(fornecedores, f, ensure_ascii=False)
    with open(data_processed_dir / "flags.json", "w", encoding="utf-8") as f:
        json.dump(flags, f, ensure_ascii=False)
    print(f"[03] Processamento concluído: contratos={len(fatos_contratos)} fornecedores={len(fornecedores)}")


if __name__ == "__main__":
    main()
