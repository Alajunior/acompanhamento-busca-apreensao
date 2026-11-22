"""Capturas de placa e endereços do banco (sintéticos): metas da simulação e defeitos de propósito."""
import pandas as pd
import pytest

from dados.capturas import capturas, enderecos
from dados.gerar import HOJE, simular

AGORA_FIM = HOJE + pd.Timedelta(hours=17, minutes=5)


@pytest.fixture(scope="module")
def cap(sim):
    return capturas(sim)


@pytest.fixture(scope="module")
def end(sim):
    return enderecos(sim)


def _ativas_com_placa(sim):
    p = sim.pastas
    ativas = p[(p["dia_ajuizamento"] <= HOJE) & (p["dia_saida"].isna() | (p["dia_saida"] > AGORA_FIM))]
    placas = sim.garantia.set_index("CARTEIRA_CONTRATO")["PLACA"]
    return ativas.assign(PLACA=ativas["PASTA"].map(placas)).dropna(subset=["PLACA"])


def test_reprodutivel_e_fase1_intacta(sim, cap):
    outra = simular(42)
    pd.testing.assert_frame_equal(sim.estoque, outra.estoque)     # as capturas não mexem no gerador da fase 1
    pd.testing.assert_frame_equal(cap, capturas(outra))


def test_proporcao_vistos_60d(sim, cap):
    at = _ativas_com_placa(sim)
    c = cap.assign(_p=cap["PLATE"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True),
                   _q=pd.to_datetime(cap["CAPTURED"]))
    vistos = set(c.loc[c["_q"] >= AGORA_FIM - pd.Timedelta(days=60), "_p"])
    frac = at["PLACA"].isin(vistos).mean()
    assert 0.30 <= frac <= 0.40, frac


def test_estados_presentes(sim):
    from src.padroes import cargas
    ult = cargas(sim)[-1]["pastas"]
    est = pd.Series([v["resumo"]["estado"] for v in ult.values()])
    recentes = est[est.isin(["PADRAO_OBSERVADO", "PADRAO_EM_FORMACAO", "APRENDENDO"])]
    for e in ("PADRAO_OBSERVADO", "PADRAO_EM_FORMACAO", "APRENDENDO"):
        assert (recentes == e).mean() >= 0.10, e
    assert (est == "SEM_CAPTURA_RECENTE").sum() > 0


def test_fora_da_uf_existe(sim, cap):
    uf_da_placa = sim.garantia.drop_duplicates("PLACA", keep=False).set_index("PLACA")["CARTEIRA_CONTRATO"].map(sim.pastas.set_index("PASTA")["UF"])
    c = cap[cap["PLATE"].isin(uf_da_placa.index)]
    assert (c["STATE"] != c["PLATE"].map(uf_da_placa)).sum() > 0


def test_defeitos_presentes(sim, cap):
    assert cap["PLATE"].str.contains("-").any() and cap["PLATE"].str.contains("[a-z]").any()
    assert (cap["LATITUDE"].isna() | (cap["LATITUDE"] == "")).any()
    assert ((cap["LATITUDE"] == "0") & (cap["LONGITUDE"] == "0")).any()
    assert cap["LOCALITY"].isin(["undefined", "null", "nan"]).any()
    assert cap.duplicated().any()
    assert cap["CITY"].str.contains("Ã").any()
    normal = cap["PLATE"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    assert (~normal.isin(set(sim.garantia["PLACA"]))).any()


def test_capturas_de_hoje(cap):
    q = pd.to_datetime(cap["CAPTURED"])
    hoje = q[q.dt.normalize() == HOJE]
    assert (hoje < HOJE + pd.Timedelta(hours=7, minutes=5)).any()
    assert ((hoje > HOJE + pd.Timedelta(hours=7, minutes=5)) & (hoje <= AGORA_FIM)).any()
    assert (q <= AGORA_FIM).all()


def test_enderecos_por_cpf(sim, end):
    cpfs = set(sim.estoque["CPF"])
    assert cpfs <= set(end["CPF"])
    res = end.groupby("CPF")["TIPO"].apply(lambda s: s.str.startswith("RESIDENC").any())
    assert 0.85 <= res.mean() <= 0.95


def test_rotina_sem_madrugada(sim, cap):
    # a 2ª passagem do dia é ida e volta de dia: nada entre 0h e 4h nos veículos da carteira (o ruído de ±40 min da rotina das 6h chega às 4h)
    da_carteira = cap["PLATE"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True).isin(set(sim.garantia["PLACA"]))
    h = pd.to_datetime(cap.loc[da_carteira, "CAPTURED"]).dt.hour
    assert (h < 4).mean() < 0.001, (h < 4).mean()
