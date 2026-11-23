"""Regras da aba Busca e Apreensão (inventário do painel real §4): marcos, etapa, datas, valor e campos por pasta."""
from datetime import date

import pandas as pd

from src.ba_regras import fase_de_atraso, linhas_pasta, marcos, valor_performance
from tests.construtores_ba import campo, fontes, tarefa

AGORA = pd.Timestamp("2026-11-26 17:05")
LOC = "EM DILIGÊNCIA - VEÍCULO LOCALIZADO"


def linha(f, pasta="1", instante=AGORA):
    df = linhas_pasta(f, instante, {})
    return df.set_index("PASTA").loc[pasta]


def test_marcos_reconhece_eventos_e_anula_equivocado():
    f = fontes([tarefa("1", "1º MANDADO EXPEDIDO", "2026-10-01"), tarefa("1", "6º OU + MANDADO NEGATIVO", "2026-10-05"),
                tarefa("1", LOC, "2026-10-02", "2026-10-03", "AGENDADO EQUIVOCADAMENTE"),
                tarefa("1", "2º MANDADO REQUERIDO", "2026-10-06", "2026-10-07", "AGENDADO EQUIVOCADAMENTE"),
                tarefa("1", "PROTOCOLAR PETICAO", "2026-10-08")])
    m = marcos(f.tarefas)
    assert sorted(zip(m.EVENTO, m.N_MDD.fillna(0).astype(int))) == [("EXPEDIDO", 1), ("LOCALIZADO", 0), ("NEGATIVO", 6)]


def test_precedencia_da_etapa():
    f = fontes([tarefa("1", LOC, "2026-11-01"), tarefa("1", "1º MANDADO EXPEDIDO", "2026-11-05"),          # mandado
                tarefa("2", LOC, "2026-11-01"),                                                            # localizado
                tarefa("3", LOC, "2026-10-01", "2026-10-10", "NAO LOCALIZADO NO ENDERECO"),                # encerrada
                tarefa("4", LOC, "2026-10-01", "2026-10-20 10:00", "VEICULO APREENDIDO"),
                tarefa("4", "BEM APREENDIDO", "2026-10-20 10:00", "2026-10-21")])                         # apreendido
    df = linhas_pasta(f, AGORA, {}).set_index("PASTA")["ETAPA"].to_dict()
    assert df == {"1": "Mandado expedido", "2": "Localizado (diligência)", "3": "Localização encerrada sem apreensão",
                  "4": "Apreendido"}


def test_relocalizada_sai_de_apreendido_mas_mantem_mes_e_valor():
    f = fontes([tarefa("1", "BEM APREENDIDO", "2026-09-10 10:00", "2026-09-11"), tarefa("1", LOC, "2026-10-20")],
               [campo("1", "DATA DA APREENSÃO", "10/09/2026", "2026-09-10 10:00")])
    r = linha(f)
    assert r.ETAPA == "Localizado (diligência)" and r.MES_APREENSAO == "9/2026" and r.VALOR_PERFORMANCE == 22_000.0


def test_mandado_expedido_so_com_status_vazio_ou_ag_resultado():
    base = [tarefa("1", LOC, "2026-11-01")]
    for st, etapa in ((None, "Mandado expedido"), ("AG. RESULTADO", "Mandado expedido"), ("CONCLUIDO", "Localizado (diligência)")):
        f = fontes(base + [tarefa("1", "1º MANDADO EXPEDIDO", "2026-11-02", "2026-11-10" if st else None, st)])
        assert linha(f).ETAPA == etapa


def test_agendado_equivocadamente_encerra_localizacao():
    f = fontes([tarefa("1", LOC, "2026-10-01", "2026-10-05", "AGENDADO EQUIVOCADAMENTE"), tarefa("1", "1º MANDADO EXPEDIDO", "2026-10-02")])
    r = linha(f)
    assert r.ETAPA == "Localização encerrada sem apreensão" and r.STATUS_LOCALIZACAO == "AGENDADO EQUIVOCADAMENTE"


def test_duas_datas_de_apreensao():
    f = fontes([tarefa("1", "BEM APREENDIDO", "2026-10-30 20:00", "2026-10-31"),                       # sex 20h → ter 03/11
                tarefa("2", "BEM APREENDIDO", "2026-10-15 10:00", "2026-10-16"),
                tarefa("2", LOC, "2026-10-01", "2026-10-14 09:00", "VEICULO APREENDIDO")],
               [campo("1", "DATA DA APREENSÃO", "29/10/2026", "2026-10-30 20:00"),
                campo("2", "DATA DA APREENSÃO", "14/10/2025", "2026-10-15 10:00")])                   # ano errado → fora
    a, b = linha(f, "1"), linha(f, "2")
    assert a.DT_APREENSAO == date(2026, 11, 3) and a.DT_APREENSAO_REAL == date(2026, 10, 29) and a.MES_APREENSAO == "11/2026"
    assert b.DT_APREENSAO_REAL == date(2026, 10, 14)


def test_valor_performance_quatro_ramos():
    assert valor_performance(30_000, 40_000, None) == (30_000, "avaliação")
    assert valor_performance(38_000, 40_000, None) == (20_900, "estimado 55% FIPE")
    assert valor_performance(200_000, 40_000, None) == (22_000, "estimado 55% FIPE")
    assert valor_performance(None, None, 50_000) == (27_500, "estimado 55% valor do bem")
    assert valor_performance(None, None, None) == (None, None)


def test_fase_na_data_do_evento():
    assert [fase_de_atraso(d) for d in (100, 121, 241, 361, 721, None)] == [
        "ATÉ 120", "JUDICIAL 1", "JUDICIAL 2", "JUDICIAL 3", "PREJUÍZO", "SEM FASE"]
    f = fontes([tarefa("1", LOC, "2026-08-18")], atraso={"1": 300})      # 100 dias antes de hoje → 200 → JUDICIAL 1
    assert linha(f).FASE == "JUDICIAL 1"


def test_instante_corta_tarefas_futuras():
    f = fontes([tarefa("1", LOC, "2026-11-01"), tarefa("1", "1º MANDADO EXPEDIDO", "2026-11-26 15:00")])
    assert linha(f, instante=pd.Timestamp("2026-11-26 13:05")).ETAPA == "Localizado (diligência)"
    assert linha(f).ETAPA == "Mandado expedido"


def test_dia_util_ok_compara_numero_do_du():
    f = fontes([tarefa("1", "BEM APREENDIDO", "2026-10-26 10:00", "2026-10-27"),     # DU 17 de outubro
                tarefa("2", "BEM APREENDIDO", "2026-10-27 10:00", "2026-10-28")])    # DU 18 de outubro
    df = linhas_pasta(f, AGORA, {}).set_index("PASTA")
    assert df.loc["1", "DIA_UTIL"] == 17 and df.loc["1", "DIA_UTIL_OK"] == "SIM" and df.loc["2", "DIA_UTIL_OK"] == "NÃO"
    assert df.loc["1", "DIA_UTIL_QUEBRA"] == "DO DIA 21 AO DIA 31"


def test_campos_texto_da_pasta():
    f = fontes([tarefa("1", LOC, "2026-11-01", memo="visto no centro"), tarefa("1", "1º MANDADO EXPEDIDO", "2026-11-03"),
                tarefa("1", "LIMINAR DEFERIDA", "2026-10-01", "2026-10-20", "CONCLUIDO")],
               acoes=[("1", "adv01", pd.Timestamp("2026-11-20"), 3), ("1", "integracao", pd.Timestamp("2026-11-25"), 1)])
    r = linha(f)
    assert r.OBSERVACAO == "1º MANDADO EXPEDIDO" and r.COMPLEMENTO == "CONCLUIDO em 20/10"
    assert r.DT_LOCALIZACAO == date(2026, 11, 1) and r.DT_MANDADO == date(2026, 11, 3) and r.MEMO_LOCALIZADO == "visto no centro"
    assert r.ULT_ACAO_RESP == date(2026, 11, 20) and r.FINANCIADO == "CLIENTE 000001" and r.LOCALIZADOR == "(sem localizador)"


def test_chave_com_nbsp_vira_a_mesma_pasta():
    f = fontes([tarefa("1\xa0", LOC, "2026-11-01"), tarefa("1", "1º MANDADO EXPEDIDO", "2026-11-03")])
    assert list(linhas_pasta(f, AGORA, {})["PASTA"]) == ["1"]
