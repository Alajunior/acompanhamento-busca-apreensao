import pandas as pd
import pytest

from dados.gerar import HOJE, agenda_em, simular
from src.regra import COLUNAS, TIPOS, chave, fase_de, montar_painel, pastas_com_empate

Q = pd.Timestamp("2026-11-26 17:05")
_id = iter(range(1, 10 ** 6))


def tarefa(pasta, tipo, data, id_agenda=None, **extra):
    base = {"ID_AGENDA": id_agenda or next(_id), "PASTA": pasta, "TIPO_AGENDAMENTO": tipo,
            "DATA_AGENDAMENTO": pd.Timestamp(data), "PROCESSO_UNICO": "0000001-00.2026.8.00.0001",
            "NUMERO_PROCESSO": "P1", "PARTE_CONTRARIA": "CLIENTE 000001", "COMARCA": "RECIFE", "UF": "PE",
            "ADVOGADO_OPERACIONAL": "ADV-01", "VARA": "1ª VARA CIVEL", "FORO": "FORO DE RECIFE", "STATUS": "Ativo",
            "DIVISAO_FILIAL": "DIVISAO 1", "ACAO": "BUSCA E APREENSAO", "CONTROLE_CLIENTE": "C1", "VALOR_CAUSA": 1000.0,
            "STATUS_FINAL": None, "ESTADO": "PERNAMBUCO"}
    base.update(extra)
    return base


def fontes(*pastas, cores=None):
    est = pd.DataFrame({"CONTRATO": list(pastas), "VALOR_RISCO_CONTRATO": 50000.0, "DIAS_ATRASO": 200, "CPF": "***.1.2-**",
                        "DATA_ATUALIZACAO": HOJE, "DATA_ENTRADA": HOJE, "DATA_IMPORTACAO": HOJE, "VALOR_CONTRATO": 70000.0,
                        "VALOR_RISCO_CLIENTE": 50000.0, "VALOR_DO_BEM": 35000.0, "VALOR_ORIGINAL": 40000.0,
                        "FASE": "VAREJO 1  ", "SITUACAO": "JURIDICO", "PRODUTO_VEICULO": "LEVES",
                        "FASE_ESTOQUE": "FX 181-360", "IDCOB_CLIENTE": 1, "IDCOB_CONTRATO": 2})
    gar = pd.DataFrame({"CARTEIRA_CONTRATO": list(pastas), "MARCA": "FIAT", "MODELO": "UNO", "PLACA": "ZZA1B23",
                        "CHASSI": "9X", "ANO_FABRICACAO": "2018", "ANO_MODELO": "2019"})
    vei = pd.DataFrame(cores if cores is not None else {"PASTA": list(pastas), "COR": "PRATA"})
    dist = pd.DataFrame({"PASTA": list(pastas), "DATA_CONCLUSAO": pd.Timestamp("2026-05-04")})
    return est, gar, vei, dist


def rodar(linhas, *pastas, **kw):
    return montar_painel(pd.DataFrame(linhas), *fontes(*pastas, **{k: v for k, v in kw.items() if k == "cores"}), quando=Q,
                         **{k: v for k, v in kw.items() if k != "cores"})


def tipo_de(df, pasta):
    return df.set_index("PASTA").loc[pasta, "TIPO_AGENDAMENTO"]


def test_pasta_com_baixado_sai_inteira():
    df = rodar([tarefa("A", "AGUARDANDO LIMINAR", "2026-11-20"), tarefa("A", "BAIXADO", "2026-11-25"),
                tarefa("B", "LIMINAR DEFERIDA", "2026-11-20")], "A", "B")
    assert list(df["PASTA"]) == ["B"]


def test_so_os_21_tipos():
    df = rodar([tarefa("A", "PROTOCOLAR PETICAO", "2026-11-20"), tarefa("B", "LIMINAR DEFERIDA", "2026-11-20")], "A", "B")
    assert list(df["PASTA"]) == ["B"]
    assert len(TIPOS) == 21 and "1º MANDADO REQUERIDO" not in TIPOS


def test_dia_mais_recente_vence():
    df = rodar([tarefa("A", "LIMINAR DEFERIDA", "2026-11-10 09:00"), tarefa("A", "AGUARDANDO LIMINAR", "2026-11-12 08:00")], "A")
    assert tipo_de(df, "A") == "AGUARDANDO LIMINAR"


def test_precedencia_so_dentro_do_trio():
    df = rodar([tarefa("A", "AGUARDANDO LIMINAR", "2026-11-20 23:59"), tarefa("A", "EMENDAR INICIAL", "2026-11-20 08:00")], "A")
    assert tipo_de(df, "A") == "EMENDAR INICIAL"
    df = rodar([tarefa("A", "AGUARDANDO LIMINAR", "2026-11-20 23:59"), tarefa("A", "EMENDAR INICIAL", "2026-11-20 08:00"),
                tarefa("A", "LIMINAR DEFERIDA", "2026-11-20 07:00")], "A")
    assert tipo_de(df, "A") == "LIMINAR DEFERIDA"
    df = rodar([tarefa("A", "AGUARDANDO LIMINAR", "2026-11-20 23:59"), tarefa("A", "EMENDAR INICIAL", "2026-11-20 08:00"),
                tarefa("A", "1º MANDADO EXPEDIDO", "2026-11-20 10:00")], "A")
    assert tipo_de(df, "A") == "AGUARDANDO LIMINAR"           # fora do trio: a hora decide


def test_empate_total_decide_por_id_agenda():
    df = rodar([tarefa("A", "1º MANDADO EXPEDIDO", "2026-11-20 10:00", id_agenda=900_001),
                tarefa("A", "2º MANDADO REQUERIDO", "2026-11-20 10:00", id_agenda=900_002)], "A")
    assert tipo_de(df, "A") == "2º MANDADO REQUERIDO"


def test_chave_ignora_nbsp_espaco_e_caixa():
    assert chave(" 12345\xa0") == chave("12345") == "12345"
    assert chave(12345.0) == "12345"
    df = rodar([tarefa("ABC1 ", "LIMINAR DEFERIDA", "2026-11-20"), tarefa("XY9\xa0", "LIMINAR DEFERIDA", "2026-11-20")],
               "abc1", "XY9")
    assert df["VALOR_RISCO_CONTRATO"].notna().all() and df["PLACA"].notna().all()


def test_tipo_canonico_sem_caixa():
    df = rodar([tarefa("A", "liminar deferida ", "2026-11-20")], "A")
    assert tipo_de(df, "A") == "LIMINAR DEFERIDA" and df["FASE"].iloc[0] == "LIMINAR DEFERIDA"


def test_cor_nula_vence():
    df = rodar([tarefa("A", "LIMINAR DEFERIDA", "2026-11-20")], "A",
               cores={"PASTA": ["A", "A"], "COR": [None, "PRATA"]})
    assert pd.isna(df["COR"].iloc[0])


def test_62_colunas_na_ordem_e_pasta_unica():
    df = rodar([tarefa("A", "LIMINAR DEFERIDA", "2026-11-20"), tarefa("A", "EMENDAR INICIAL", "2026-11-19"),
                tarefa("B", "1º MANDADO NEGATIVO", "2026-11-20")], "A", "B")
    assert len(COLUNAS) == 62 and tuple(df.columns) == COLUNAS and df["PASTA"].is_unique
    assert df["DATA_DISTRIBUICAO"].iloc[0] == "04/05/2026" and (df["RKG"] == 1).all()
    assert (df["BASE_PRODUCAO"] == "PRODUTIVO").all() and (df["DATA_INSERT"] == Q).all()


def test_colunas_de_entrada_obrigatorias():
    with pytest.raises(ValueError):
        montar_painel(pd.DataFrame([tarefa("A", "LIMINAR DEFERIDA", "2026-11-20")]).drop(columns="UF"), *fontes("A"), quando=Q)


def test_fase_de():
    assert fase_de("3º MANDADO NEGATIVO") == "MANDADO NEGATIVO" and fase_de("XYZ") == "SEM INFO"
    assert fase_de("6º OU + MANDADO REQUERIDO") == "MANDADO REQUERIDO" and fase_de("EMENDA REALIZADA") == "EMENDA REALIZADA"


def test_pastas_com_empate():
    ag = pd.DataFrame([tarefa("A", "AGUARDANDO LIMINAR", "2026-11-20 23:59"), tarefa("A", "EMENDAR INICIAL", "2026-11-20 08:00"),
                       tarefa("B", "LIMINAR DEFERIDA", "2026-11-20"), tarefa("B", "EMENDAR INICIAL", "2026-11-19")])
    assert pastas_com_empate(ag) == {"A"}


def test_acaso_diverge_so_nos_empates(sim):
    q = HOJE + pd.Timedelta(hours=9, minutes=4)
    ag = agenda_em(sim, q)
    f = (sim.estoque, sim.garantia, sim.veiculo, sim.distribuicao)
    a = montar_painel(ag, *f, quando=q).set_index("PASTA")
    b = montar_painel(ag, *f, quando=q, desempate="acaso", seed=7).set_index("PASTA")
    dif = set(a.index[a["TIPO_AGENDAMENTO"] != b.loc[a.index, "TIPO_AGENDAMENTO"]])
    assert dif and dif <= {chave(p) for p in pastas_com_empate(ag)} | pastas_com_empate(ag)


def test_regra_na_simulacao_inteira(sim):
    df = montar_painel(agenda_em(sim, Q), sim.estoque, sim.garantia, sim.veiculo, sim.distribuicao, quando=Q)
    assert 4000 <= len(df) <= 5000
    assert df["TIPO_AGENDAMENTO"].isin(TIPOS).all()


def test_carteira_produto_vem_da_fase_do_estoque():
    df = rodar([tarefa("A", "LIMINAR DEFERIDA", "2026-11-20")], "A")
    assert df["CARTEIRA_PRODUTO"].iloc[0] == "VAREJO 1  " and df["FASE"].iloc[0] == "LIMINAR DEFERIDA"
