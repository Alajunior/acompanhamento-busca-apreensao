"""Regras da aba Busca e Apreensão: das tarefas lidas do sistema jurídico a uma linha por pasta.

Reproduz as regras do painel real: marcos por tarefa, a etapa da pasta (Apreendido > Mandado expedido > Localizado >
Encerrada), as duas datas da apreensão (dia útil do registro e data do fato), a fase da carteira na data do evento, o
valor de performance estimado, o localizador padronizado e as passagens das fichas de localizador.
"""
import re
from datetime import date

import pandas as pd

from src.ba_calendario import dia_util_registro, du_indice, mes_txt, quebra

LOC = "EM DILIGÊNCIA - VEÍCULO LOCALIZADO"
EQUIVOCADO = "AGENDADO EQUIVOCADAMENTE"
VEIC_APREENDIDO = "VEICULO APREENDIDO"
ETAPAS = ("Apreendido", "Mandado expedido", "Localizado (diligência)", "Localização encerrada sem apreensão")
EVENTOS = ("LOCALIZADO", "LIMINAR", "REQUERIDO", "EXPEDIDO", "NEGATIVO", "APREENDIDO")
SEM_LOCALIZADOR = "(sem localizador)"
FATOR_VALOR, CORTE_AVALIACAO, TETO_AVALIACAO = 0.55, 0.85, 3.0
COLUNAS = ["PASTA", "ETAPA", "FINANCIADO", "UF", "COMARCA", "ADVOGADO", "LOGIN_OPERACIONAL", "DT_LOCALIZACAO",
           "STATUS_LOCALIZACAO", "DT_MANDADO", "DT_APREENSAO", "OBSERVACAO", "COMPLEMENTO", "LOCALIZADOR",
           "MEMO_LOCALIZADO", "VALOR_RISCO", "FASE", "VALOR_PERFORMANCE", "ORIGEM_VALOR", "MES_APREENSAO",
           "LOCALIZADOR_ORIGINAL", "DT_APREENSAO_REAL", "ULT_ACAO_RESP", "DIA_UTIL", "DIA_UTIL_OK", "DIA_UTIL_QUEBRA",
           "MES_EVENTO"]
_MDD = re.compile(r"^([1-6])º(?: OU \+)? MANDADO (EXPEDIDO|NEGATIVO|REQUERIDO)$")


def chave(s) -> str:
    return re.sub(r"\s", "", str(s)).upper()


def evento_de(nome: str) -> tuple[str | None, int | None]:
    n = str(nome).upper().strip()
    m = _MDD.match(n)
    if m:
        return m.group(2), int(m.group(1))
    if n == LOC:
        return "LOCALIZADO", None
    if n in ("BEM APREENDIDO", "APREENDIDO"):
        return "APREENDIDO", None
    if n == "LIMINAR DEFERIDA":
        return "LIMINAR", None
    return None, None


def marcos(tarefas: pd.DataFrame) -> pd.DataFrame:
    t = tarefas.copy()
    t["PASTA"] = t["PASTA"].map(chave)
    ev = t["TAREFA"].map(evento_de)
    t["EVENTO"] = [e for e, _ in ev]
    t["N_MDD"] = pd.array([n for _, n in ev], dtype="Int64")
    t["DATA"] = t["DATA_INICIO"]
    t = t[t["EVENTO"].notna() & ((t["STATUS_FINAL"] != EQUIVOCADO) | (t["EVENTO"] == "LOCALIZADO"))]
    return t[["PASTA", "ID_TAREFA", "EVENTO", "N_MDD", "DATA", "DATA_CONCLUSAO", "STATUS_FINAL", "RESPONSAVEL"]].reset_index(drop=True)


def fase_de_atraso(dias) -> str:
    if dias is None or pd.isna(dias):
        return "SEM FASE"
    dias = int(dias)
    return ("ATÉ 120" if dias <= 120 else "JUDICIAL 1" if dias <= 240 else "JUDICIAL 2" if dias <= 360
            else "JUDICIAL 3" if dias <= 720 else "PREJUÍZO")


def valor_performance(avaliacao, fipe, valor_bem) -> tuple[float | None, str | None]:
    ok = lambda v: v is not None and not pd.isna(v)
    ref = fipe if ok(fipe) and fipe > 0 else (valor_bem if ok(valor_bem) and valor_bem > 0 else None)
    if ok(avaliacao) and avaliacao > 1 and (ref is None or avaliacao <= TETO_AVALIACAO * ref):
        if ref is not None and avaliacao / ref > CORTE_AVALIACAO:
            return round(avaliacao * FATOR_VALOR, 2), "estimado 55% FIPE"
        return round(float(avaliacao), 2), "avaliação"
    if ok(fipe) and fipe > 0:
        return round(fipe * FATOR_VALOR, 2), "estimado 55% FIPE"
    if ok(valor_bem) and valor_bem > 0:
        return round(valor_bem * FATOR_VALOR, 2), "estimado 55% valor do bem"
    return None, None


def _num_br(s) -> float | None:
    if s is None or pd.isna(s):
        return None
    txt = re.sub(r"[^\d,.-]", "", str(s)).replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


def _data_br(s) -> date | None:
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})", str(s or ""))
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _ultimo(df: pd.DataFrame, col: str):
    s = df[col].dropna()
    return s.iloc[-1] if len(s) else None


def _pasta(g: pd.DataFrame, campos: dict, instante: pd.Timestamp, hoje: date, atraso, bem, risco, acoes,
           localizadores: dict) -> dict | None:
    g = g.sort_values(["DATA_INICIO", "ID_TAREFA"])
    concl = g["DATA_CONCLUSAO"].where(g["DATA_CONCLUSAO"] <= instante)
    status = g["STATUS_FINAL"].where(concl.notna())
    g = g.assign(CONC=concl, ST=status)
    ev = g["TAREFA"].map(evento_de)
    g = g.assign(EVENTO=[e for e, _ in ev], N=[n for _, n in ev])
    valida = g["EVENTO"].notna() & ((g["ST"] != EQUIVOCADO) | (g["EVENTO"] == "LOCALIZADO"))
    mk = g[valida]
    if not (mk["EVENTO"].isin(["LOCALIZADO", "APREENDIDO"])).any():
        return None
    locs = g[g["EVENTO"] == "LOCALIZADO"]
    loc = locs.iloc[-1] if len(locs) else None
    loc_aberta = loc is not None and pd.isna(loc["CONC"])

    bens = mk[(mk["EVENTO"] == "APREENDIDO") & (mk["TAREFA"].str.upper().str.strip() == "BEM APREENDIDO")]
    aps = mk[mk["EVENTO"] == "APREENDIDO"]
    loc_ap = locs[(locs["ST"] == VEIC_APREENDIDO)]
    if len(bens):
        momento = bens.iloc[0]["DATA_INICIO"]
    elif len(loc_ap):
        momento = loc_ap.iloc[-1]["CONC"]
    elif len(aps):
        momento = aps.iloc[0]["DATA_INICIO"]
    else:
        momento = None
    dt_ap = dia_util_registro(momento.to_pydatetime()) if momento is not None else None
    dt_real = None
    if momento is not None:
        digitada = _data_br(campos.get("DATA DA APREENSÃO"))
        if len(bens):
            ab = bens.iloc[0]["DATA_INICIO"].date()
            if digitada and (ab - pd.Timedelta(days=30).to_pytimedelta()) <= digitada <= (ab + pd.Timedelta(days=1).to_pytimedelta()):
                dt_real = digitada
            elif len(loc_ap):
                dt_real = loc_ap.iloc[-1]["CONC"].date()
            else:
                dt_real = ab
        else:
            dt_real = momento.date()

    mand = mk[mk["EVENTO"].isin(["EXPEDIDO", "NEGATIVO", "REQUERIDO"])]
    ordem = {"REQUERIDO": 0, "EXPEDIDO": 1, "NEGATIVO": 2}
    ult_mand = (mand.assign(_o=mand["EVENTO"].map(ordem)).sort_values(["DATA_INICIO", "N", "_o"]).iloc[-1]
                if len(mand) else None)
    aguardando = ult_mand is not None and ult_mand["EVENTO"] == "EXPEDIDO" and (pd.isna(ult_mand["ST"]) or ult_mand["ST"] == "AG. RESULTADO")
    if dt_real is not None and not (loc_aberta and loc["DATA_INICIO"].date() > dt_real):
        etapa = ETAPAS[0]
    elif loc_aberta and aguardando:
        etapa = ETAPAS[1]
    elif loc_aberta:
        etapa = ETAPAS[2]
    else:
        etapa = ETAPAS[3]

    exp = mand[mand["EVENTO"] == "EXPEDIDO"]
    dt_mandado = exp[exp["N"] == exp["N"].max()]["DATA_INICIO"].min().date() if len(exp) else None
    abertas = g[g["CONC"].isna()]
    concluidas = g[g["CONC"].notna()].sort_values("CONC")
    complemento = None
    if len(concluidas):
        c = concluidas.iloc[-1]
        complemento = f"{c['ST'] or 'CONCLUIDO'} em {c['CONC'].day:02d}/{c['CONC'].month:02d}"
    dt_loc = loc["DATA_INICIO"].date() if loc is not None else None
    evento = dt_ap if etapa == ETAPAS[0] else dt_loc
    fase = fase_de_atraso(None if atraso is None or evento is None else atraso - (hoje - evento).days)
    vp, origem = (valor_performance(_num_br(campos.get("AVALIAÇÃO DO BEM")), _num_br(campos.get("TABELA FIPE")), bem)
                  if dt_ap is not None else (None, None))
    original = campos.get("NOME DO LOCALIZADOR")
    login = _ultimo(g, "LOGIN_OPERACIONAL")
    ult = None
    if login is not None and acoes is not None and len(acoes):
        a = acoes[(acoes["LOGIN"] == login) & (acoes["ALTERACOES"] > 0)]["DIA"]
        ult = a.max().date() if len(a) else None
    du = du_indice(dt_ap) if dt_ap else None
    mes_ap = mes_txt(dt_ap) if dt_ap else None
    return {
        "PASTA": g["PASTA"].iloc[0], "ETAPA": etapa, "FINANCIADO": _ultimo(g, "PARTE_CONTRARIA"), "UF": _ultimo(g, "UF"),
        "COMARCA": _ultimo(g, "COMARCA"), "ADVOGADO": _ultimo(g, "ADV_OPERACIONAL"), "LOGIN_OPERACIONAL": login,
        "DT_LOCALIZACAO": dt_loc, "STATUS_LOCALIZACAO": None if loc is None or loc_aberta else loc["ST"],
        "DT_MANDADO": dt_mandado, "DT_APREENSAO": dt_ap,
        "OBSERVACAO": abertas.iloc[-1]["TAREFA"] if len(abertas) else None, "COMPLEMENTO": complemento,
        "LOCALIZADOR": localizadores.get(original, SEM_LOCALIZADOR) if original else SEM_LOCALIZADOR,
        "MEMO_LOCALIZADO": loc["MEMO"] if loc is not None else None, "VALOR_RISCO": risco, "FASE": fase,
        "VALOR_PERFORMANCE": vp, "ORIGEM_VALOR": origem, "MES_APREENSAO": mes_ap, "LOCALIZADOR_ORIGINAL": original,
        "DT_APREENSAO_REAL": dt_real, "ULT_ACAO_RESP": ult, "DIA_UTIL": du,
        "DIA_UTIL_OK": None if du is None else ("SIM" if du <= du_indice(hoje) else "NÃO"),
        "DIA_UTIL_QUEBRA": quebra(dt_ap) if dt_ap else None,
        "MES_EVENTO": mes_ap if etapa == ETAPAS[0] else (mes_txt(dt_loc) if dt_loc else None),
    }


def linhas_pasta(f, instante: pd.Timestamp, localizadores: dict[str, str]) -> pd.DataFrame:
    """Uma linha por pasta do universo, só com o que o sistema jurídico mostrava em `instante`."""
    hoje = instante.date()
    t = f.tarefas[f.tarefas["DATA_INICIO"] <= instante].copy()
    t["PASTA"] = t["PASTA"].map(chave)
    universo = set(t.loc[t["TAREFA"].map(lambda n: evento_de(n)[0] in ("LOCALIZADO", "APREENDIDO")), "PASTA"])
    t = t[t["PASTA"].isin(universo)]
    c = f.campos[f.campos["DATA_CADASTRO"] <= instante].assign(PASTA=lambda x: x["PASTA"].map(chave))
    c = c.sort_values("DATA_CADASTRO").groupby(["PASTA", "CAMPO"])["VALOR"].last()
    campos = {p: grp.droplevel(0).to_dict() for p, grp in c.groupby(level=0)}

    def por_contrato(df, col):
        return df.assign(_k=df["CONTRATO"].map(chave)).drop_duplicates("_k").set_index("_k")[col]
    atraso = por_contrato(f.fase_base, "DIAS_ATRASO_REF")
    ref = f.fase_base["DIA_REF"].iloc[0].date() if len(f.fase_base) else hoje
    bem, risco = por_contrato(f.estoque, "VALOR_DO_BEM"), por_contrato(f.estoque, "VALOR_RISCO_CONTRATO")
    ac = f.acoes[f.acoes["DIA"] <= instante.normalize()].assign(PASTA=lambda x: x["PASTA"].map(chave))
    ac_por = dict(tuple(ac.groupby("PASTA")))
    out = []
    for pasta, g in t.groupby("PASTA", sort=True):
        a = atraso.get(pasta)
        a = None if a is None or pd.isna(a) else int(a) - (ref - hoje).days
        r = _pasta(g, campos.get(pasta, {}), instante, hoje, a, _f(bem.get(pasta)), _f(risco.get(pasta)),
                   ac_por.get(pasta), localizadores)
        if r:
            out.append(r)
    return pd.DataFrame(out, columns=COLUNAS)


def _f(v):
    return None if v is None or pd.isna(v) else float(v)
