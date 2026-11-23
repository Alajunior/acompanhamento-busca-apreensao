"""docs/ba.json: os dados da aba Busca e Apreensão, carregados só quando a aba é aberta.

Para cada "agora" simulado do dia, uma linha por pasta do universo (as regras de src/ba_regras.py aplicadas ao que o
sistema jurídico mostrava naquele horário) e as passagens das fichas de localizador. A primeira carga vai inteira; as
outras, só o que mudou. Às 11:05 a leitura do sistema jurídico vem incompleta (como a da agenda): a aba mantém a de 09:05.
"""
import json
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from dados.ba import FIM, fontes_ba
from dados.gerar import HOJE, Simulacao
from src.ba_regras import COLS_PASSAGEM, COLUNAS, ETAPAS, EVENTOS, SEM_LOCALIZADOR, linhas_pasta, localizadores_de, \
    marcos, marcos_linha_tempo, passagens
from src.publicacao import HORAS_HOJE, PARCIAL

COLS_PAS = ["LOCALIZADOR", "RECEBEU", "ATE", "DIAS", "RESULTADO", "FICHAS", "UF", "ADVOGADO", "APREENDEU",
            "VALOR_PERFORMANCE", "DIAS_ATE_LOCALIZAR"]
RESULTADOS = ["localizou", "encerrada", "substituido", "sem_localizacao"]
BASE_MIN = pd.Timestamp("2026-01-01")      # instantes das passagens em minutos desde esta data (payload menor)


def _v(x):
    if x is None or x is pd.NaT:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, pd.Timestamp):
        return None if pd.isna(x) else x.strftime("%Y-%m-%dT%H:%M")
    if isinstance(x, (datetime,)):
        return x.strftime("%Y-%m-%dT%H:%M")
    if isinstance(x, date):
        return x.isoformat()
    if hasattr(x, "item"):
        return x.item()
    return x


def _linhas(df: pd.DataFrame) -> dict[str, list]:
    return {r[0]: [_v(v) for v in r] for r in df[COLUNAS].itertuples(index=False, name=None)}


def _min(ts) -> int | None:
    return None if ts is None or pd.isna(ts) else int((ts - BASE_MIN) / pd.Timedelta(minutes=1))


def _passagens(df: pd.DataFrame, idx: dict[str, dict]) -> dict[str, list]:
    """Linha compacta: textos viram índices das listas de opções; instantes, minutos; DIAS de passagem aberta fica
    vazio (o navegador calcula com o agora, e a linha não muda a cada horário)."""
    out: dict[str, list] = {}
    for r in df.itertuples(index=False):
        aberta = r.ATE is None or pd.isna(r.ATE)
        out.setdefault(r.PASTA, []).append([
            idx["localizadores"][r.LOCALIZADOR], _min(r.RECEBEU), _min(r.ATE), None if aberta else _v(r.DIAS),
            RESULTADOS.index(r.RESULTADO), int(r.FICHAS), idx["ufs"].get(r.UF), idx["advogados"].get(r.ADVOGADO),
            int(bool(r.APREENDEU)), _v(r.VALOR_PERFORMANCE), _v(r.DIAS_ATE_LOCALIZAR)])
    return out


def _delta(antes: dict | None, agora: dict, lista: bool) -> dict:
    if antes is None:
        return {"base": list(agora.values()) if lista else agora}
    sai = sorted(set(antes) - set(agora))
    muda = {k: v for k, v in agora.items() if antes.get(k) != v}
    return {"sai": sai, "muda": list(muda.values()) if lista else muda}


def montar_ba(sim: Simulacao, saida: Path) -> dict:
    f = fontes_ba(sim)
    mapa, info = localizadores_de(f)
    cargas, pas_brutas = [], []
    ant_l = None
    ultimo_lin = None
    for hora in HORAS_HOJE:
        instante = HOJE + pd.Timedelta(hours=int(hora[:2]), minutes=int(hora[3:]))
        if hora in PARCIAL:          # leitura incompleta: mantém a carga anterior
            cargas.append({"agora": hora, "quando": cargas[-1]["quando"], "sai": [], "muda": [],
                           "aviso": f"Leitura de {hora} incompleta; mantida a de {cargas[-1]['agora']}."})
            pas_brutas.append(None)
            continue
        lin = linhas_pasta(f, instante, mapa)
        pas = passagens(f, lin, instante, mapa)
        lin_d = _linhas(lin)
        cargas.append({"agora": hora, "quando": instante.strftime("%Y-%m-%dT%H:%M"), "aviso": None, **_delta(ant_l, lin_d, True)})
        pas_brutas.append(pas)
        ant_l, ultimo_lin = lin_d, lin
    final = ultimo_lin
    todas = pd.concat([x for x in pas_brutas if x is not None])
    opc = {"advogados": sorted(set(final["ADVOGADO"].dropna()) | set(todas["ADVOGADO"].dropna())),
           "ufs": sorted(set(final["UF"].dropna()) | set(todas["UF"].dropna()))}
    locs = sorted((set(final["LOCALIZADOR"]) | set(todas["LOCALIZADOR"])) - {SEM_LOCALIZADOR}) + [SEM_LOCALIZADOR]
    idx = {"localizadores": {v: i for i, v in enumerate(locs)}, "ufs": {v: i for i, v in enumerate(opc["ufs"])},
           "advogados": {v: i for i, v in enumerate(opc["advogados"])}}
    pas_cargas, ant_p = [], None
    for pas in pas_brutas:
        if pas is None:
            pas_cargas.append({"sai": [], "muda": {}})
            continue
        pas_d = _passagens(pas, idx)
        pas_cargas.append(_delta(ant_p, pas_d, False))
        ant_p = pas_d
    meses = sorted({m for m in pd.concat([final["MES_EVENTO"], final["MES_APREENSAO"]]).dropna()} | {f"{HOJE.month}/{HOJE.year}"},
                   key=lambda m: (int(m.split("/")[1]), int(m.split("/")[0])), reverse=True)
    ba = {
        "hoje": HOJE.date().isoformat(), "agoras": list(HORAS_HOJE), "eventos": list(EVENTOS), "etapas": list(ETAPAS),
        "opcoes": {"advogados": opc["advogados"], "fases": sorted(final["FASE"].dropna().unique().tolist()), "ufs": opc["ufs"],
                   "localizadores": locs, "localizadores_info": {k: v for k, v in info.items() if k in set(locs)},
                   "meses": meses, "etapas": list(ETAPAS)},
        "colunas": COLUNAS, "colunas_passagem": COLS_PAS, "resultados": RESULTADOS,
        "base_minutos": BASE_MIN.strftime("%Y-%m-%dT%H:%M"), "cargas": cargas, "passagens": pas_cargas,
        "marcos": marcos_linha_tempo(marcos(f.tarefas[f.tarefas["DATA_INICIO"] <= FIM]), final, HOJE.date()),
        "metas": {"faixa": [[_norm_mes(m), c, _v(q), _v(v)] for m, c, q, v in f.metas_faixa.itertuples(index=False, name=None)],
                  "advogado": [[_norm_mes(m), c, _v(q), _v(v)] for m, c, q, v in f.metas_advogado.itertuples(index=False, name=None)]},
        "feriados": sorted(d.isoformat() for d in f.feriados),
    }
    Path(saida).write_text(json.dumps(ba, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return json.loads(json.dumps(ba, ensure_ascii=False))


def _norm_mes(m: str) -> str:
    mm, aa = str(m).split("/")
    return f"{int(mm)}/{aa}"
