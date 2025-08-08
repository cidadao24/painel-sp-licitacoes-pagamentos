"""
Utilitários de suporte para normalização de texto e parsing de valores monetários.
"""

import re
from unidecode import unidecode

def norm_text(s: str) -> str:
    """Normaliza uma string removendo acentos, espaços extras e convertendo para maiúsculas.

    Args:
        s: texto de entrada ou `None`.

    Returns:
        String normalizada.
    """
    if not s:
        return ""
    s_norm = unidecode(str(s)).strip()
    s_norm = re.sub(r"\s+", " ", s_norm)
    return s_norm.upper()

def parse_money(x) -> float:
    """Converte representações de valores monetários em float.

    Args:
        x: string ou número representando um valor.

    Returns:
        Valor como float; 0.0 em caso de falha.
    """
    try:
        s = str(x).replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0
