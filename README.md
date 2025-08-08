# Painel — Pagamentos & Licitações/Contratos (Município de São Paulo)

Este repositório contém um painel interativo que consolida informações públicas sobre licitações e contratos firmados pela Prefeitura do Município de São Paulo.  
As fontes de dados incluem o Portal Nacional de Contratações Públicas (PNCP) e, em versão futura, as exportações de pagamentos da Prefeitura de São Paulo via CKAN/CSV.  

O painel é atualizado automaticamente de forma diária por meio de GitHub Actions. Os dados são coletados, transformados e sinalizados com simples heurísticas de concentração e séries de pagamentos. O front‑end é um site estático construído com HTML, CSS e Plotly.js que é publicado no GitHub Pages.

## Estrutura

- `scripts/`: scripts Python para coleta de dados (`01_fetch_sp_payments.py`, `02_fetch_pncp.py`) e transformação/geração de alertas (`03_transform_and_flags.py`).
- `data/processed/`: contém arquivos JSON processados consumidos pelo site.
- `site/`: arquivos HTML/CSS/JS do painel.
- `.github/workflows/`: workflows de GitHub Actions para coletar dados diariamente e fazer o deploy do site.
- `config/parametros.json`: parâmetros de ajuste das heurísticas e janelas de tempo.

## Uso

1. Os workflows de GitHub Actions estão configurados para rodar automaticamente.  
2. Você pode acionar manualmente a coleta de dados acessando a aba *Actions* no repositório e executando o workflow **Data refresh (SP + PNCP)**.  
3. O site está publicado via GitHub Pages em `https://cidadao24.github.io/painel-sp-licitacoes-pagamentos/`.

## Fontes

* [PNCP — API de consultas públicas](https://www.gov.br/compras/pt-br/pncp), utilizada para obter contratações, contratos e atas do município.  
* Portal de dados abertos da Prefeitura de São Paulo (CKAN), que fornece exportações de despesas/pagamentos (a ser integrado).
