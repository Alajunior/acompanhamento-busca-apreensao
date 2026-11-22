import pandas as pd

from src.conciliacao import conciliar


def painel(pastas_tipos: dict[str, str], carteira="VAREJO 1 ") -> pd.DataFrame:
    return pd.DataFrame({"PASTA": list(pastas_tipos), "TIPO_AGENDAMENTO": list(pastas_tipos.values()),
                         "CARTEIRA_PRODUTO": carteira})


def test_conciliacao_ok_quando_iguais():
    a = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(300)})
    c = conciliar(a, a.copy(), set())
    assert c["ok"] and c["linhas_oficial"] == c["linhas_nosso"] == 300 and c["so_nosso"] == c["so_oficial"] == 0


def test_conciliacao_acusa_tipo_fora_da_tolerancia():
    oficial = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(300)})
    nosso = painel({f"{i}": ("AGUARDANDO LIMINAR" if i < 20 else "LIMINAR DEFERIDA") for i in range(300)})
    c = conciliar(nosso, oficial, set())
    assert not c["ok"] and c["tipos_divergentes"] == {"LIMINAR DEFERIDA": -20, "AGUARDANDO LIMINAR": 20}


def test_conciliacao_tolera_ate_max_5_ou_2pct():
    oficial = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(300)})
    nosso = painel({f"{i}": ("AGUARDANDO LIMINAR" if i < 5 else "LIMINAR DEFERIDA") for i in range(300)})
    assert conciliar(nosso, oficial, set())["ok"]


def test_conciliacao_ignora_tipo_das_pastas_com_empate():
    oficial = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(300)})
    nosso = painel({f"{i}": ("AGUARDANDO LIMINAR" if i < 20 else "LIMINAR DEFERIDA") for i in range(300)})
    c = conciliar(nosso, oficial, {f"{i}" for i in range(20)})
    assert c["ok"] and c["empates_fora"] == 20


def test_conciliacao_pastas_um_lado_ate_1pct():
    oficial = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(1000)})
    nosso = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(5, 1005)})
    c = conciliar(nosso, oficial, set())
    assert c["so_nosso"] == 5 and c["so_oficial"] == 5 and c["ok"]          # 10 de 1000 = 1%
    nosso = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(6, 1006)})
    assert not conciliar(nosso, oficial, set())["ok"]


def test_conciliacao_compara_carteira_normalizada():
    oficial = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(300)}, carteira="VAREJO 1   ")
    nosso = painel({f"{i}": "LIMINAR DEFERIDA" for i in range(300)}, carteira="VAREJO 1")
    assert conciliar(nosso, oficial, set())["ok"]
    nosso.loc[:40, "CARTEIRA_PRODUTO"] = None
    c = conciliar(nosso, oficial, set())
    assert not c["ok"] and c["carteiras_divergentes"]["(vazio)"] == 41
