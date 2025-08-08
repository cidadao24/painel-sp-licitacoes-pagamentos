"""
Script para coletar dados de pagamentos da Prefeitura de São Paulo.

Atualmente este script contém um *placeholder* até que a fonte seja
definida com clareza (CKAN ou exportação CSV/Excel). Ele cria um
arquivo `placeholder.json` para não quebrar o fluxo de atualização.

Futuramente, você poderá implementar a coleta real usando a API CKAN
(`package_search` e `datastore_search`) ou simulando o download de
relatórios via HTTP.
"""

import json
import pathlib

def main():
    outdir = pathlib.Path("data/raw/sp")
    outdir.mkdir(parents=True, exist_ok=True)
    placeholder_path = outdir / "placeholder.json"
    data = {
        "status": "ok",
        "nota": "Coleta de pagamentos da PMSP ainda não implementada"
    }
    with placeholder_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[01] Placeholder gerado em {placeholder_path}")

if __name__ == "__main__":
    main()
