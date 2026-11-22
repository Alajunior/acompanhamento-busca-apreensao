"""Conciliação: a nossa regra contra a "tabela oficial" (recarregada às 9h, 15h e 17h).

- por TIPO, fora as pastas com empate (nelas a procedure oficial escolhe ao acaso): divergente se
  |nosso − oficial| > max(5, 2% do oficial);
- por carteira normalizada (strip; nulo → "(vazio)"), com a mesma tolerância, em todas as pastas;
- pastas só de um lado: ok até 1% das pastas oficiais.
"""
from __future__ import annotations

import pandas as pd

from src.regra import chave


def _tolerancia(oficial: int) -> float:
    return max(5, 0.02 * oficial)


def _divergencias(nosso: pd.Series, oficial: pd.Series) -> dict[str, int]:
    a, b = nosso.value_counts(), oficial.value_counts()
    out = {}
    for k in sorted(set(a.index) | set(b.index)):
        d = int(a.get(k, 0)) - int(b.get(k, 0))
        if abs(d) > _tolerancia(int(b.get(k, 0))):
            out[str(k)] = d
    return out


def _carteira(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().fillna("(vazio)").replace("", "(vazio)")


def conciliar(nosso: pd.DataFrame, oficial: pd.DataFrame, empates: set[str]) -> dict:
    kn, ko = nosso["PASTA"].map(chave), oficial["PASTA"].map(chave)
    emp = {chave(p) for p in empates}
    so_nosso, so_oficial = len(set(kn) - set(ko)), len(set(ko) - set(kn))
    tipos = _divergencias(nosso.loc[~kn.isin(emp), "TIPO_AGENDAMENTO"], oficial.loc[~ko.isin(emp), "TIPO_AGENDAMENTO"])
    carteiras = _divergencias(_carteira(nosso["CARTEIRA_PRODUTO"]), _carteira(oficial["CARTEIRA_PRODUTO"]))
    pastas_ok = (so_nosso + so_oficial) <= 0.01 * len(oficial)
    return {"ok": bool(not tipos and not carteiras and pastas_ok), "linhas_oficial": int(len(oficial)),
            "linhas_nosso": int(len(nosso)), "so_nosso": so_nosso, "so_oficial": so_oficial,
            "tipos_divergentes": tipos, "carteiras_divergentes": carteiras, "empates_fora": len(emp & set(kn))}
