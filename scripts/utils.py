"""
Utilitários de suporte para normalização de texto e parsing de valores monetários.
"""

import re
from unidecode import unidecode


def norm_text(s: str) -> str:
    """Normaliza uma string removendo acentos, espaços extras e convertendo para maiúsculas."""
    if not s:
        return ""
    s_norm = unidecode(str(s)).strip()
    s_norm = re.sub(r"\s+", " ", s_norm)
    return s_norm.upper()


def parse_money(x) -> float:
    """Converte representações de valores monetários em float.

    Preserva números que já chegam como int/float. Isso é importante para a API
    do PNCP, que frequentemente retorna valores numéricos reais; a versão antiga
    transformava 1637.00 em 163700.0 ao remover todos os pontos.
    """
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    try:
        s = str(x).strip()
        if not s:
            return 0.0
        # Formato brasileiro: 1.234.567,89
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        # Formato JSON/API: 1234567.89 fica intacto.
        return float(s)
    except Exception:
        return 0.0
