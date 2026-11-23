"""Calendário de dias úteis e arredondamentos do Excel usados pela aba Busca e Apreensão."""
from datetime import date, datetime

from src.ba_calendario import (arred, arred_cima, dia_util_registro, dias_uteis, du_indice, eh_util, mes_txt,
                               quebra)


def test_registro_depois_das_19h_vai_para_o_dia_seguinte():
    assert dia_util_registro(datetime(2026, 11, 25, 19, 0)) == date(2026, 11, 26)
    assert dia_util_registro(datetime(2026, 11, 25, 18, 59)) == date(2026, 11, 25)


def test_registro_no_fim_de_semana_e_na_virada_do_mes():
    assert dia_util_registro(datetime(2026, 11, 28, 10, 0)) == date(2026, 11, 30)   # sábado → segunda
    assert dia_util_registro(datetime(2026, 10, 30, 20, 0)) == date(2026, 11, 3)    # sex 20h → sáb → seg 02/11 feriado → ter


def test_du_indice_e_dias_uteis():
    assert len(dias_uteis("11/2026")) == 19          # 02/11 e 20/11 feriados nacionais em 2026
    assert du_indice(date(2026, 11, 26)) == 17
    assert du_indice(date(2026, 11, 1)) == 0          # domingo antes do 1º útil
    assert du_indice(date(2026, 11, 21)) == du_indice(date(2026, 11, 19)) == 13   # sábado herda; 20/11 feriado herda
    assert not eh_util(date(2026, 8, 14))             # feriado local fictício


def test_arredondamentos_do_excel():
    assert arred(2.5) == 3 and arred(-2.5) == -3 and arred(1.005, 2) == 1.01
    assert arred_cima(2.01) == 3 and arred_cima(-2.01) == -3 and arred_cima(11.58, 1) == 11.6
    assert arred_cima(13.894736842105264, 1) == 13.9 and arred(-16.8) == -17


def test_quebra_e_mes():
    assert [quebra(date(2026, 11, d)) for d in (10, 11, 20, 21, 30)] == [
        "ATÉ DIA 10", "DO DIA 11 AO DIA 20", "DO DIA 11 AO DIA 20", "DO DIA 21 AO DIA 31", "DO DIA 21 AO DIA 31"]
    assert mes_txt(date(2026, 6, 3)) == "6/2026"
