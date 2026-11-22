import re

import pandas as pd
import pytest

from dados.gerar import DIA_EXTINCAO, HOJE, agenda_em, simular


def _chave(x: str) -> str:
    return re.sub(r"\s+", "", str(x)).upper()


@pytest.fixture(scope="session")
def sim():
    return simular(42)


def share_primeiro_mandado(sim) -> float:
    ap = sim.pastas.dropna(subset=["dia_apreensao"])
    return (ap["tentativa_apreensao"] == 1).mean()


def taxa_apreensao_14d(sim, dia: pd.Timestamp) -> float:
    q = dia + pd.Timedelta(hours=17, minutes=5)
    ag = agenda_em(sim, q)
    tipos = ag["TIPO_AGENDAMENTO"].str.upper().str.strip()
    baixadas = set(ag.loc[tipos == "BAIXADO", "PASTA"].map(_chave))
    ativas = set(ag["PASTA"].map(_chave)) - baixadas
    p = sim.pastas.assign(k=sim.pastas["PASTA"].map(_chave)).set_index("k")
    ap = p.loc[sorted(ativas), "dia_apreensao"]
    return ((ap > q) & (ap <= q + pd.Timedelta(days=14))).mean()


def test_funil_bate_as_medianas(sim):   # design §4, tolerância ±15%
    ap = sim.pastas.dropna(subset=["dia_apreensao"])
    for marco, alvo in [("dia_contencioso", 170), ("dia_ajuizamento", 71), ("dia_liminar", 34), ("dia_mandado1", 18)]:
        med = (ap["dia_apreensao"] - ap[marco]).dt.days.median()
        assert abs(med - alvo) <= 0.15 * alvo, (marco, med)


def test_74pct_apreendidos_no_primeiro_mandado(sim):
    assert 0.69 <= share_primeiro_mandado(sim) <= 0.79


def test_carteira_estavel_perto_de_4500(sim):
    for dia in pd.date_range("2026-10-12", "2026-11-26", freq="7D"):
        ag = agenda_em(sim, dia + pd.Timedelta(hours=17, minutes=5))
        assert 4000 <= ag["PASTA"].map(_chave).nunique() <= 5000, dia


def test_taxa_de_apreensao_14_dias_perto_de_1_3pct(sim):
    assert 0.008 <= taxa_apreensao_14d(sim, pd.Timestamp("2026-11-01")) <= 0.018


def test_emenda_realizada_some_depois_da_extincao(sim):
    tipos = agenda_em(sim, DIA_EXTINCAO + pd.Timedelta(hours=12))["TIPO_AGENDAMENTO"].str.upper().str.strip()
    assert not (tipos == "EMENDA REALIZADA").any()
    antes = agenda_em(sim, DIA_EXTINCAO - pd.Timedelta(days=2))["TIPO_AGENDAMENTO"].str.upper().str.strip()
    assert (antes == "EMENDA REALIZADA").sum() > 50


def test_defeitos_presentes(sim):
    ag = agenda_em(sim, HOJE + pd.Timedelta(hours=17, minutes=5))
    assert ag["PASTA"].str.contains("\xa0").any() and ag["PASTA"].str.endswith(" ").any()
    assert (ag["TIPO_AGENDAMENTO"] != ag["TIPO_AGENDAMENTO"].str.upper()).any()
    assert (ag["TIPO_AGENDAMENTO"].str.upper().str.strip() == "BAIXADO").any()


def test_agenda_parcial_e_estavel(sim):
    q = HOJE + pd.Timedelta(hours=11, minutes=5)
    a, b = agenda_em(sim, q, fracao=0.6), agenda_em(sim, q, fracao=0.6)
    assert a.equals(b) and 0.55 <= len(a) / len(agenda_em(sim, q)) <= 0.65


def test_prazos_vencidos_plausiveis(sim):
    ag = agenda_em(sim, HOJE + pd.Timedelta(hours=17, minutes=5))
    venc = (pd.to_datetime(ag["DATA_AGENDAMENTO"]).dt.normalize() < HOJE).mean()
    assert 0.15 <= venc <= 0.35


def test_fontes_tem_as_colunas_do_inventario(sim):
    assert {"CONTRATO", "VALOR_RISCO_CONTRATO", "VALOR_DO_BEM", "FASE", "PRODUTO_VEICULO", "CPF"} <= set(sim.estoque.columns)
    assert {"CARTEIRA_CONTRATO", "MARCA", "MODELO", "PLACA", "CHASSI", "ANO_FABRICACAO", "ANO_MODELO"} <= set(sim.garantia.columns)
    assert {"PASTA", "COR"} <= set(sim.veiculo.columns) and {"PASTA", "DATA_CONCLUSAO"} <= set(sim.distribuicao.columns)
    assert sim.garantia["PLACA"].dropna().str.match(r"^ZZ[A-Z]\d[A-Z]\d{2}$").all()
