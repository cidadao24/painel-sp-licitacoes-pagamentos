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

from scripts.utils import parse_money, norm_text


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

    fatos_contratos = []
    fornecedores_agg = defaultdict(lambda: {"cnpj": "", "nome": "", "total_contratado": 0.0, "total_pago": 0.0})

    for c in contratos:
        orgao = ((c.get("orgaoEntidade") or {}).get("nomeOrgao")) or ""
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

    fornecedores = list(fornecedores_agg.values())
    # Flags simples: top N fornecedores por valor contratado
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
