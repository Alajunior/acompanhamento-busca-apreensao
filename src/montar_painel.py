"""Monta o painel: payload compacto embutido em docs/index.html e a base analítica (bd.json) para a exportação.

Payload:
- `pastas`: atributos de cada pasta que aparece em alguma foto, em colunas com códigos de dicionário
  (na simulação os atributos são estáveis dentro da janela);
- `fotos`: a 1ª foto cheia ([pasta, tipo, dias até hoje]) e as demais como delta sobre a anterior
  ({"sai": [...], "muda": [...]}). O navegador reconstrói cada dia aplicando os deltas em sequência;
- `publicacoes`: o que o painel mostra em cada horário do "agora (simulado)".
"""
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from dados.gerar import HOJE, NOME_UF, simular
from src.publicacao import LinhaDoTempo, linha_do_tempo
from src.regra import COLUNAS, EXTINTAS, ORDEM_ACAO, ORDEM_FOLLOW, ORDEM_PROCESSUAL, TIPOS, chave

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "src" / "painel.html"
SCRIPTS = {"/*__AGREGAR__*/": RAIZ / "src" / "agregar.js", "/*__EXPORTAR__*/": RAIZ / "src" / "exportar.js"}
DINAMICAS_BD = ("TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "FASE", "DATA_INSERT")
_ATRIBUTOS = {"uf": ("UF", None), "carteira": ("CARTEIRA_PRODUTO", "(vazio)"), "adv": ("ADVOGADO_OPERACIONAL", "(sem advogado)"),
              "produto": ("PRODUTO_VEICULO", "(sem produto)"), "comarca": ("COMARCA", "(sem comarca)"), "marca": ("MARCA", None)}


def _texto(s: pd.Series, vazio: str | None) -> pd.Series:
    t = s.astype("string").str.strip()
    t = t.mask(t == "")
    return t.fillna(vazio) if vazio else t


def _num(v):
    return None if v is None or pd.isna(v) else float(v)


def _atributos(linha: LinhaDoTempo) -> pd.DataFrame:
    """Uma linha por pasta (chave), com os atributos da foto mais recente em que ela aparece."""
    partes = [f.df.assign(_k=f.df["PASTA"].map(chave), _ordem=i) for i, f in enumerate(linha.fotos)]
    todas = pd.concat(partes, ignore_index=True).sort_values("_ordem").drop_duplicates("_k", keep="last")
    return todas.sort_values("_k").reset_index(drop=True)


def montar_payload(linha: LinhaDoTempo) -> dict:
    at = _atributos(linha)
    dic = {"tipo": list(TIPOS), "nome_uf": NOME_UF}
    pastas = {"pasta": at["_k"].tolist()}
    for nome, (col, vazio) in _ATRIBUTOS.items():
        valores = _texto(at[col], vazio)
        dic[nome] = sorted(valores.dropna().unique().tolist(), key=lambda x: (x.startswith("("), x))
        cod = {v: i for i, v in enumerate(dic[nome])}
        pastas[nome] = [None if pd.isna(v) else cod[v] for v in valores]
    pastas["risco"] = [_num(v) for v in at["VALOR_RISCO_CONTRATO"]]
    pastas["bem"] = [_num(v) for v in at["VALOR_DO_BEM"]]
    pastas["ano_modelo"] = [None if pd.isna(v) else int(v) for v in pd.to_numeric(at["ANO_MODELO"], errors="coerce")]

    idx = {k: i for i, k in enumerate(pastas["pasta"])}
    tipo_cod = {t: i for i, t in enumerate(TIPOS)}
    fotos, anterior = [], None
    for f in linha.fotos:
        datas = pd.to_datetime(f.df["DATA_AGENDAMENTO"])
        dias = ((datas - HOJE).dt.days).astype("Int64")
        atual = {idx[chave(p)]: (tipo_cod[t], None if pd.isna(d) else int(d))
                 for p, t, d in zip(f.df["PASTA"], f.df["TIPO_AGENDAMENTO"], dias)}
        if anterior is None:
            estado = [[i, t, d] for i, (t, d) in sorted(atual.items())]
        else:
            estado = {"sai": sorted(set(anterior) - set(atual)),
                      "muda": [[i, t, d] for i, (t, d) in sorted(atual.items()) if anterior.get(i) != (t, d)]}
        fotos.append({"dia": f.dia.isoformat(), "hora": f.hora, "origem": f.origem, "estado": estado})
        anterior = atual

    return {"hoje": HOJE.date().isoformat(), "dic": dic,
            "ordens": {"processual": list(ORDEM_PROCESSUAL), "follow": list(ORDEM_FOLLOW), "acao": list(ORDEM_ACAO),
                       "extintas": list(EXTINTAS)},
            "pastas": pastas, "fotos": fotos, "publicacoes": _limpo(linha.publicacoes), "fontes_bd": "bd.json"}


def _limpo(x):
    """Tipos do numpy/pandas → JSON puro."""
    if isinstance(x, dict):
        return {str(k): _limpo(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_limpo(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _json(x) -> str:
    return json.dumps(x, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("</", r"<\/")


def montar_html(payload: dict, saida: Path) -> None:
    html = MODELO.read_text(encoding="utf-8").replace("/*__DADOS__*/", "const DADOS = " + _json(payload) + ";")
    for marca, arq in SCRIPTS.items():
        html = html.replace(marca, arq.read_text(encoding="utf-8").replace("</", r"<\/") if arq.exists() else "")
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")


def _valor_bd(v):
    if v is None or (not isinstance(v, (str, date, time)) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (date, time)):
        return v.isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v)
    return v


def montar_bd(linha: LinhaDoTempo, payload: dict, saida: Path) -> None:
    """Base analítica (aba BD do .xlsx): uma linha por pasta das fotos de hoje, com as colunas estáveis.
    TIPO_AGENDAMENTO, DATA_AGENDAMENTO, FASE e DATA_INSERT vêm da foto da publicação (no navegador)."""
    hoje = HOJE.date()
    partes = [f.df.assign(_ordem=i) for i, f in enumerate(linha.fotos) if f.dia == hoje]
    df = pd.concat(partes, ignore_index=True).sort_values("_ordem").drop_duplicates("PASTA", keep="last")
    idx = {k: i for i, k in enumerate(payload["pastas"]["pasta"])}
    colunas = [c for c in COLUNAS if c not in DINAMICAS_BD]
    bd = {"colunas": colunas, "pastas": [idx[chave(p)] for p in df["PASTA"]],
          "valores": [[_valor_bd(v) for v in linha_] for linha_ in df[colunas].itertuples(index=False, name=None)]}
    saida.write_text(json.dumps(bd, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    linha = linha_do_tempo(simular(42))
    payload = montar_payload(linha)
    montar_html(payload, RAIZ / "docs" / "index.html")
    montar_bd(linha, payload, RAIZ / "docs" / "bd.json")
    print(f"docs/index.html: {(RAIZ / 'docs' / 'index.html').stat().st_size / 1024:.0f} KB · "
          f"docs/bd.json: {(RAIZ / 'docs' / 'bd.json').stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
