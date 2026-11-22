from datetime import date

import pandas as pd
import pytest

from dados.gerar import simular
from src.publicacao import Foto, anterior, avaliar_rodada, base_do_dia, linha_do_tempo

VAZIO = pd.DataFrame()


def test_guarda_rejeita_abaixo_de_85():
    ok, aviso = avaliar_rodada(80, 100, None, "11:05")
    assert not ok and aviso == "Rodada das 11:05 rejeitada: 80 linhas contra 100 da publicacao anterior (guarda de 85%)."


def test_guarda_aceita_acima_de_85_sem_aviso():
    assert avaliar_rodada(85, 100, None, "11:05") == (True, None)


def test_guarda_aceita_queda_confirmada_em_2pct():
    ok, aviso = avaliar_rodada(81, 100, 80, "11:35")
    assert ok and aviso == "Queda de volume confirmada em duas rodadas seguidas: 81 linhas (antes 100)."


def test_guarda_nao_confirma_fora_de_2pct():
    assert not avaliar_rodada(70, 100, 80, "11:35")[0]


def test_base_do_dia_prefere_ao_vivo_mais_cedo():
    d = date(2026, 11, 26)
    fotos = [Foto(d, "06:00", "reconstruido", VAZIO), Foto(d, "07:00", "oficial", VAZIO), Foto(d, "09:05", "ao_vivo", VAZIO),
             Foto(d, "07:05", "ao_vivo", VAZIO), Foto(date(2026, 11, 25), "17:05", "ao_vivo", VAZIO)]
    assert base_do_dia(fotos, d) is fotos[3]
    assert base_do_dia(fotos[:2], d) is fotos[1]
    assert base_do_dia(fotos[:1], d) is None


def test_anterior_e_ultima_foto_de_dia_menor():
    fotos = [Foto(date(2026, 11, 24), "17:05", "ao_vivo", VAZIO), Foto(date(2026, 11, 25), "09:05", "ao_vivo", VAZIO),
             Foto(date(2026, 11, 25), "17:05", "ao_vivo", VAZIO), Foto(date(2026, 11, 26), "07:05", "ao_vivo", VAZIO)]
    assert anterior(fotos, date(2026, 11, 26)) is fotos[2]
    assert anterior(fotos[:1], date(2026, 11, 24)) is None


def test_roteiro_de_hoje(linha):
    p = {x["agora"]: x for x in linha.publicacoes}
    assert list(p) == ["07:05", "09:05", "11:05", "13:05", "15:05", "17:05"]
    assert p["11:05"]["foto"] == p["09:05"]["foto"] and "guarda de 85%" in p["11:05"]["avisos"][0]
    assert p["13:05"]["origem"] == "oficial" and p["13:05"]["quando"] == "09:04" and p["13:05"]["avisos"]
    assert p["07:05"]["base"] == p["07:05"]["foto"] and p["17:05"]["base"] == p["07:05"]["foto"]
    assert p["07:05"]["conciliacao"] is None and not p["15:05"]["avisos"]
    ant = linha.fotos[p["17:05"]["anterior"]]
    assert (ant.dia, ant.hora, ant.origem) == (date(2026, 11, 25), "17:05", "ao_vivo")


def test_evolucao_tem_lacunas_aos_domingos_e_10_reconstruidos(linha):
    hist = [f for f in linha.fotos if f.dia < date(2026, 11, 26)]
    dias = sorted({f.dia for f in hist})
    assert dias[0] == date(2026, 10, 12) and dias[-1] == date(2026, 11, 25)
    assert all(d.weekday() != 6 for d in dias) and len(dias) == 39
    assert [f.origem for f in sorted(hist, key=lambda f: f.dia)][:11] == ["reconstruido"] * 10 + ["ao_vivo"]


def test_conciliacao_ok_ignora_empates(linha):
    c = [x for x in linha.publicacoes if x["agora"] == "17:05"][0]["conciliacao"]
    assert c["ok"] and c["empates_fora"] > 0 and not c["tipos_divergentes"] and c["recarga"] == "17:04"
