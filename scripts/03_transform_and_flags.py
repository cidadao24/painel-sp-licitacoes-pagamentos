"""
Transforma dados brutos do PNCP e gera arquivos JSON processados para o painel.

Este script carrega os dados brutos de `data/raw/pncp/contratacoes.json` e
`data/raw/pncp/contratos.json`, cria listas de fatos e fornecedores, e
gera um conjunto inicial de `flags` com alertas simples.
"""

import json
import os
import pathlib
from collections import defaultdict

import sys
current_dir = pathlib.Path(__file__).resolve()
repo_root = current_dir.parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.utils import parse_money, norm_text
from typing import Dict, List, Any


def load_parametros() -> Dict:
    cfg_path = pathlib.Path("config/parametros.json")
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_fetch_status() -> dict:
    status_path = pathlib.Path("data/raw/pncp/status_fetch_success.json")
    if not status_path.exists():
        return {"success": False, "partial": False, "missing_status_file": True}
    try:
        with status_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        return {"success": False, "partial": False, "status_read_error": f"{type(exc).__name__}: {exc}"}


def as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def deep_text(value: Any) -> str:
    """Extrai texto de dict/list sem depender de nomes exatos de campos do PNCP."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(deep_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(deep_text(v) for v in value.values())
    return ""


def get_nested(data: dict, *path: str) -> str:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
    return "" if cur is None else str(cur)


def contract_org_text(c: dict) -> str:
    orgao = as_dict(c.get("orgaoEntidade"))
    unidade = as_dict(c.get("unidadeOrgao"))
    compra = as_dict(c.get("compra"))
    parts = [
        orgao.get("nomeOrgao"),
        orgao.get("razaoSocial"),
        orgao.get("nomeRazaoSocial"),
        orgao.get("poderId"),
        orgao.get("esferaId"),
        unidade.get("nomeUnidade"),
        unidade.get("nome"),
        unidade.get("municipioNome"),
        unidade.get("ufSigla"),
        c.get("nomeOrgao"),
        c.get("razaoSocialOrgao"),
        c.get("municipioNome"),
        c.get("ufSigla"),
        compra.get("orgaoEntidade"),
        compra.get("unidadeOrgao"),
    ]
    return " ".join(str(p) for p in parts if p)


def orgao_display_name(c: dict) -> str:
    orgao = as_dict(c.get("orgaoEntidade"))
    unidade = as_dict(c.get("unidadeOrgao"))
    return (
        orgao.get("nomeOrgao")
        or orgao.get("razaoSocial")
        or orgao.get("nomeRazaoSocial")
        or unidade.get("nomeUnidade")
        or c.get("nomeOrgao")
        or contract_org_text(c)
        or ""
    )


def is_municipio_sao_paulo_contract(c: dict) -> bool:
    """Identifica registros ligados ao Município de São Paulo no PNCP.

    O schema do PNCP varia entre endpoints/versões; por isso usamos sinais em
    vários campos, e não apenas `orgaoEntidade.nomeOrgao`.
    """
    unidade = as_dict(c.get("unidadeOrgao"))
    orgao = as_dict(c.get("orgaoEntidade"))

    municipio = norm_text(
        unidade.get("municipioNome")
        or c.get("municipioNome")
        or get_nested(c, "compra", "unidadeOrgao", "municipioNome")
    ).upper()
    uf = (
        unidade.get("ufSigla")
        or c.get("ufSigla")
        or get_nested(c, "compra", "unidadeOrgao", "ufSigla")
        or ""
    ).upper()

    text = norm_text(contract_org_text(c)).upper()
    municipal_signal = any(token in text for token in ["PREFEITURA", "MUNICIP", "SECRETARIA MUNICIPAL", "SAO PAULO"])

    if municipio == "SAO PAULO" and (not uf or uf == "SP") and municipal_signal:
        return True

    # Fallback para registros em que município/UF não vêm estruturados.
    # Evita depender de um único campo e cobre `razaoSocial`/`nomeUnidade`.
    return ("SAO PAULO" in text) and any(token in text for token in ["PREFEITURA", "MUNICIP", "SECRETARIA MUNICIPAL"])


def main():
    data_processed_dir = pathlib.Path("data/processed")
    data_processed_dir.mkdir(parents=True, exist_ok=True)

    contratos = load_json("data/raw/pncp/contratos.json")
    fetch_status = load_fetch_status()
    fetch_failed = not bool(fetch_status.get("success", True))
    fetch_partial = bool(fetch_status.get("partial", False))

    fatos_contratos: list = []
    fornecedores_agg: Dict[str, Dict] = defaultdict(lambda: {"cnpj": "", "nome": "", "total_contratado": 0.0, "total_pago": 0.0})
    orgao_sample: list[str] = []

    for c in contratos:
        orgao = orgao_display_name(c)
        if len(orgao_sample) < 20:
            sample_text = contract_org_text(c)
            if sample_text:
                orgao_sample.append(sample_text[:300])

        if not is_municipio_sao_paulo_contract(c):
            continue

        fornecedor_data = as_dict(c.get("fornecedor"))
        fornecedor = fornecedor_data.get("razaoSocial") or c.get("fornecedorNome") or c.get("nomeFornecedor") or ""
        cnpj = fornecedor_data.get("cpfCnpj") or c.get("fornecedorCnpj") or c.get("cpfCnpjFornecedor") or ""
        objeto = c.get("objeto") or c.get("objetoContrato") or c.get("descricaoObjeto") or ""
        valor_estimado = parse_money(c.get("valorEstimado"))
        valor_contratado = parse_money(c.get("valorFinal") or c.get("valorContrato") or c.get("valorGlobal"))
        pub = c.get("dataPublicacao") or c.get("dataInclusao") or c.get("dataAssinatura")
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

    fatos_pagamentos = []
    fornecedores = list(fornecedores_agg.values())
    topN = sorted(fornecedores, key=lambda x: x["total_contratado"], reverse=True)[:5]

    flags = {
        "top_fornecedores_contratados": topN,
        "msg": "Alertas completos só serão gerados após integração dos pagamentos PMSP.",
        "fetch_status": fetch_status,
        "fetch_failed": bool(fetch_failed and not contratos),
        "fetch_partial": bool(fetch_partial),
        "raw_contracts_loaded": len(contratos),
        "contracts_after_filter": len(fatos_contratos),
        "orgao_sample": orgao_sample,
    }
    if fetch_failed and contratos:
        flags["warning"] = "Coleta PNCP parcial: alguns blocos falharam, mas os dados obtidos foram preservados no painel."
    elif fetch_failed:
        flags["warning"] = "Coleta PNCP falhou sem dados aproveitáveis."
    if contratos and not fatos_contratos:
        flags["warning"] = "Coleta PNCP retornou dados, mas nenhum registro passou pelo filtro do Município de São Paulo. Verifique orgao_sample."

    with open(data_processed_dir / "fatos_contratos.json", "w", encoding="utf-8") as f:
        json.dump(fatos_contratos, f, ensure_ascii=False)
    with open(data_processed_dir / "fatos_pagamentos.json", "w", encoding="utf-8") as f:
        json.dump(fatos_pagamentos, f, ensure_ascii=False)
    with open(data_processed_dir / "fornecedores.json", "w", encoding="utf-8") as f:
        json.dump(fornecedores, f, ensure_ascii=False)
    with open(data_processed_dir / "flags.json", "w", encoding="utf-8") as f:
        json.dump(flags, f, ensure_ascii=False)
    print(f"[03] Processamento concluído: raw={len(contratos)} contratos={len(fatos_contratos)} fornecedores={len(fornecedores)}")


if __name__ == "__main__":
    main()
