"""
Transforma dados brutos do PNCP e gera arquivos JSON processados para o painel.

Este script carrega os dados brutos de `data/raw/pncp/contratos.json`, filtra
contratos do Município de São Paulo, extrai fornecedor/valor de forma tolerante
a variações do schema do PNCP e gera JSONs consumidos pelo site.
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
from typing import Dict, Any


MUNICIPIO_SP_ORG_TOKENS = [
    "MUNICIPIO DE SAO PAULO",
    "MUNICIPIO SAO PAULO",
    "PREFEITURA DO MUNICIPIO DE SAO PAULO",
    "PREFEITURA MUNICIPAL DE SAO PAULO",
    "PREFEITURA DE SAO PAULO",
    "SECRETARIA MUNICIPAL",
    "FUNDO MUNICIPAL DE SAUDE",
    "FUNDO MUNICIPAL DE ASSISTENCIA SOCIAL",
    "FUNDO MUNICIPAL DOS DIREITOS",
    "CAMARA MUNICIPAL DE SAO PAULO",
]

EXCLUDED_ORG_TOKENS = [
    "ESTADO DE SAO PAULO",
    "SECRETARIA DE ESTADO",
    "UNIVERSIDADE DE SAO PAULO",
    "UNIVERSIDADE FEDERAL",
    "INSTITUTO FEDERAL",
    "COMANDO DA AERONAUTICA",
    "MINISTERIO ",
    "FUNDACAO PARA O DESENVOLVIMENTO DA EDUCACAO",
    "CONSELHO REGIONAL",
    "DEPARTAMENTO DE ESTRADAS DE RODAGEM",
    "CENTRO ESTADUAL",
]

SUPPLIER_NAME_KEYS = [
    "razaoSocial", "nomeRazaoSocialFornecedor", "nomeFornecedor", "fornecedorNome",
    "fornecedor", "nome", "razaoSocialFornecedor", "nomeEmpresarial",
]

SUPPLIER_CNPJ_KEYS = [
    "cpfCnpj", "niFornecedor", "cpfCnpjFornecedor", "fornecedorCnpj", "cnpjFornecedor",
    "cnpj", "numeroDocumento", "identificadorFornecedor",
]

VALUE_KEYS = [
    "valorFinal", "valorContrato", "valorGlobal", "valorTotal", "valorTotalContrato",
    "valorInicial", "valorParcela", "valor", "valorContratado",
]


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
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(deep_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(deep_text(v) for v in value.values())
    return ""


def get_nested(data: dict, *path: str) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
    return cur


def first_value_from_keys(*containers: dict, keys: list[str]) -> str:
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in keys:
            value = container.get(key)
            if value not in (None, ""):
                return str(value)
    return ""


def first_money_from_keys(c: dict, keys: list[str]) -> float:
    for key in keys:
        value = c.get(key)
        parsed = parse_money(value)
        if parsed:
            return parsed
    return 0.0


def contract_org_text(c: dict) -> str:
    orgao = as_dict(c.get("orgaoEntidade"))
    unidade = as_dict(c.get("unidadeOrgao"))
    compra = as_dict(c.get("compra"))
    parts = [
        orgao.get("cnpj"),
        orgao.get("nomeOrgao"),
        orgao.get("razaoSocial"),
        orgao.get("nomeRazaoSocial"),
        orgao.get("poderId"),
        orgao.get("esferaId"),
        unidade.get("codigoUnidade"),
        unidade.get("nomeUnidade"),
        unidade.get("nome"),
        unidade.get("municipioNome"),
        unidade.get("ufSigla"),
        c.get("nomeOrgao"),
        c.get("razaoSocialOrgao"),
        c.get("municipioNome"),
        c.get("ufSigla"),
        deep_text(compra.get("orgaoEntidade")),
        deep_text(compra.get("unidadeOrgao")),
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


def normalized_org_text(c: dict) -> str:
    return norm_text(contract_org_text(c))


def is_municipio_sao_paulo_contract(c: dict) -> bool:
    unidade = as_dict(c.get("unidadeOrgao"))
    municipio = norm_text(
        unidade.get("municipioNome")
        or c.get("municipioNome")
        or get_nested(c, "compra", "unidadeOrgao", "municipioNome")
    )
    uf = norm_text(
        unidade.get("ufSigla")
        or c.get("ufSigla")
        or get_nested(c, "compra", "unidadeOrgao", "ufSigla")
    )
    text = normalized_org_text(c)

    if any(token in text for token in EXCLUDED_ORG_TOKENS):
        return False

    has_municipal_sp_token = any(token in text for token in MUNICIPIO_SP_ORG_TOKENS)

    # Estruturado: município = São Paulo/SP + órgão municipal explícito.
    if municipio == "SAO PAULO" and (not uf or uf == "SP"):
        return has_municipal_sp_token or "MUNICIPAL" in text

    # Não estruturado: exige token forte; não basta conter "São Paulo".
    return has_municipal_sp_token


def extract_supplier(c: dict) -> tuple[str, str]:
    fornecedor_obj = as_dict(c.get("fornecedor"))
    fornecedor_pessoa = as_dict(c.get("pessoa"))
    name = first_value_from_keys(c, fornecedor_obj, fornecedor_pessoa, keys=SUPPLIER_NAME_KEYS)
    cnpj = first_value_from_keys(c, fornecedor_obj, fornecedor_pessoa, keys=SUPPLIER_CNPJ_KEYS)

    # Alguns retornos do PNCP usam campos paralelos com nomes diferentes.
    if not name:
        for key, value in c.items():
            lk = key.lower()
            if "fornecedor" in lk and any(word in lk for word in ["nome", "razao", "social"]):
                if value not in (None, ""):
                    name = str(value)
                    break
    if not cnpj:
        for key, value in c.items():
            lk = key.lower()
            if ("fornecedor" in lk or "contratad" in lk) and any(word in lk for word in ["cnpj", "cpf", "ni"]):
                if value not in (None, ""):
                    cnpj = str(value)
                    break
    return name, cnpj


def extract_object(c: dict) -> str:
    return c.get("objeto") or c.get("objetoContrato") or c.get("descricaoObjeto") or c.get("objetoCompra") or ""


def main():
    data_processed_dir = pathlib.Path("data/processed")
    data_processed_dir.mkdir(parents=True, exist_ok=True)

    contratos = load_json("data/raw/pncp/contratos.json")
    fetch_status = load_fetch_status()
    fetch_failed = not bool(fetch_status.get("success", True))
    fetch_partial = bool(fetch_status.get("partial", False))

    fatos_contratos: list = []
    fornecedores_agg: Dict[str, Dict] = defaultdict(lambda: {"cnpj": "", "nome": "", "total_contratado": 0.0, "total_pago": 0.0, "qtd_contratos": 0})
    orgao_sample: list[str] = []
    accepted_org_sample: list[str] = []
    supplier_empty_count = 0

    for c in contratos:
        orgao = orgao_display_name(c)
        if len(orgao_sample) < 20:
            sample_text = contract_org_text(c)
            if sample_text:
                orgao_sample.append(sample_text[:300])

        if not is_municipio_sao_paulo_contract(c):
            continue

        if len(accepted_org_sample) < 20:
            accepted_org_sample.append(contract_org_text(c)[:300])

        fornecedor, cnpj = extract_supplier(c)
        if not fornecedor and not cnpj:
            supplier_empty_count += 1
        objeto = extract_object(c)
        valor_estimado = parse_money(c.get("valorEstimado") or c.get("valorEstimadoTotal"))
        valor_contratado = first_money_from_keys(c, VALUE_KEYS)
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

        key = cnpj or norm_text(fornecedor) or "(fornecedor não informado)"
        f = fornecedores_agg[key]
        f["cnpj"] = cnpj
        f["nome"] = fornecedor or "(fornecedor não informado)"
        f["total_contratado"] += valor_contratado
        f["qtd_contratos"] += 1

    fatos_pagamentos = []
    fornecedores = list(fornecedores_agg.values())
    topN = sorted(fornecedores, key=lambda x: x["total_contratado"], reverse=True)[:10]

    flags = {
        "top_fornecedores_contratados": topN,
        "msg": "Alertas completos só serão gerados após integração dos pagamentos PMSP.",
        "fetch_status": fetch_status,
        "fetch_failed": bool(fetch_failed and not contratos),
        "fetch_partial": bool(fetch_partial),
        "raw_contracts_loaded": len(contratos),
        "contracts_after_filter": len(fatos_contratos),
        "suppliers_after_filter": len(fornecedores),
        "supplier_empty_count": supplier_empty_count,
        "orgao_sample": orgao_sample,
        "accepted_org_sample": accepted_org_sample,
    }
    if fetch_failed and contratos:
        flags["warning"] = "Coleta PNCP parcial: alguns blocos falharam, mas os dados obtidos foram preservados no painel."
    elif fetch_failed:
        flags["warning"] = "Coleta PNCP falhou sem dados aproveitáveis."
    if contratos and not fatos_contratos:
        flags["warning"] = "Coleta PNCP retornou dados, mas nenhum registro passou pelo filtro do Município de São Paulo. Verifique orgao_sample."
    if supplier_empty_count:
        flags["supplier_warning"] = f"{supplier_empty_count} contratos filtrados ainda vieram sem fornecedor identificável no endpoint consultado."

    with open(data_processed_dir / "fatos_contratos.json", "w", encoding="utf-8") as f:
        json.dump(fatos_contratos, f, ensure_ascii=False)
    with open(data_processed_dir / "fatos_pagamentos.json", "w", encoding="utf-8") as f:
        json.dump(fatos_pagamentos, f, ensure_ascii=False)
    with open(data_processed_dir / "fornecedores.json", "w", encoding="utf-8") as f:
        json.dump(fornecedores, f, ensure_ascii=False)
    with open(data_processed_dir / "flags.json", "w", encoding="utf-8") as f:
        json.dump(flags, f, ensure_ascii=False)
    print(f"[03] Processamento concluído: raw={len(contratos)} contratos={len(fatos_contratos)} fornecedores={len(fornecedores)} sem_fornecedor={supplier_empty_count}")


if __name__ == "__main__":
    main()
