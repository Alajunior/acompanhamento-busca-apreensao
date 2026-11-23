"""Fontes sintéticas da aba Busca e Apreensão: calibragem pelo real e defeitos da fonte presentes."""
import pandas as pd

from dados.ba import APREENSAO, FIM, LOC, fontes_ba


def universo(f) -> set[str]:
    t = f.tarefas
    return set(t.loc[t["TAREFA"].isin([LOC, APREENSAO]), "PASTA"].str.strip())


def test_universo_e_ritmo(ba_fontes, sim):
    u = universo(ba_fontes)
    assert 1_300 <= len(u) <= 1_900
    ap = sim.pastas.dropna(subset=["dia_apreensao"])
    ap26 = ap[(ap.dia_apreensao >= "2026-01-01") & (ap.dia_apreensao <= FIM - pd.Timedelta(days=3))]
    assert set(ap26.PASTA) <= u                       # toda apreensão de 2026 está no universo
    reg = ba_fontes.tarefas[ba_fontes.tarefas.TAREFA == APREENSAO]
    assert set(reg.PASTA.str.strip()) <= set(ap.PASTA)  # nenhuma apreensão nova
    por_mes = reg.DATA_INICIO.dt.month.value_counts()
    assert por_mes.drop(11).min() >= 80 and por_mes.max() <= 145


def test_em_aberto(ba_fontes):
    t = ba_fontes.tarefas
    abertas = t[(t.TAREFA == LOC) & t.DATA_CONCLUSAO.isna()].PASTA.str.strip().nunique()
    assert 180 <= abertas <= 340


def test_defeitos_presentes(ba_fontes):
    t = ba_fontes.tarefas
    ab = t[t.TAREFA == APREENSAO]
    assert (ab.DATA_INICIO.dt.hour >= 19).mean() > 0.10
    assert (ab.DATA_INICIO.dt.dayofweek == 5).any()
    assert (t.STATUS_FINAL == "AGENDADO EQUIVOCADAMENTE").any()
    assert t.PASTA.str.endswith("\xa0").any()
    nomes = ba_fontes.campos.query("CAMPO == 'NOME DO LOCALIZADOR'").VALOR
    assert nomes.str.contains(r"\(00\) 9|00 9").any() and (nomes == ".").any()
    assert not nomes.str.contains(r"\b(?!00)\d{2} 9\d{4}-\d{4}").any()      # nenhum DDD que exista


def test_metas(ba_fontes):
    assert "12/2026" not in set(ba_fontes.metas_faixa.MES)
    assert set(ba_fontes.metas_faixa.CHAVE) == {"JUDICIAL 1", "JUDICIAL 2", "JUDICIAL 3", "PREJUÍZO", "121 A 360"}
    assert ba_fontes.metas_advogado.CHAVE.nunique() == 12


def test_fichas_dentro_e_fora_do_universo(ba_fontes):
    pastas = set(ba_fontes.fichas.PASTA)
    assert len(pastas - universo(ba_fontes)) > 2 * len(pastas & universo(ba_fontes))


def test_determinismo(sim, ba_fontes):
    pd.testing.assert_frame_equal(fontes_ba(sim).tarefas, ba_fontes.tarefas)
