"""Padrões de circulação e resumo do localizado (inv. §7), com capturas construídas à mão."""
import pandas as pd
import pytest

from src import padroes as P

COLS = ["IDPLACAS", "PLATE", "BRAND", "MODEL", "COLOR", "YEAR_VEHICLE", "COMPANY_NAME", "CAPTURED", "LATITUDE",
        "LONGITUDE", "STREET", "STREET_NUMBER", "POSTAL_CODE", "LOCALITY", "CITY", "STATE", "DEVICE_NAME",
        "CAMERA_TYPE", "STORAGE_PATH"]
BASE = {"PLATE": "ZZA1B23", "LATITUDE": "-23.550000", "LONGITUDE": "-46.630000", "STREET": "RUA A", "STREET_NUMBER": "10",
        "POSTAL_CODE": "01234000", "LOCALITY": "CENTRO", "CITY": "SAO PAULO", "STATE": "SP", "DEVICE_NAME": "CAM-1",
        "COMPANY_NAME": "CAMERAS 01", "CAMERA_TYPE": "FIXA"}


def cap_raw(*rows):
    out = []
    for k, r in enumerate(rows):
        d = {c: None for c in COLS} | BASE | {"IDPLACAS": k + 1, "STORAGE_PATH": f"s/{k}.jpg"} | r
        d["CAPTURED"] = pd.Timestamp(d["CAPTURED"])
        out.append(d)
    return pd.DataFrame(out, columns=COLS)


def info(placa="ZZA1B23", uf="SP", cpf="C1"):
    return pd.DataFrame({"PASTA": ["P1"], "PLACA": [placa], "UF": [uf], "CPF": [cpf]})


END = pd.DataFrame(columns=["CPF", "ENDERECO", "NUMERO", "COMPLEMENTO", "BAIRRO", "CIDADE", "UF", "CEP", "TIPO", "DATA_CADASTRO"])


def test_preparar_normaliza_e_descarta():
    raw = cap_raw({"PLATE": "zza-1b23", "CAPTURED": "2026-11-20 08:00", "LOCALITY": "undefined", "CITY": "SÃO  PAULO"},
                  {"PLATE": "ZZA1B2", "CAPTURED": "2026-11-20 09:00"},
                  {"CAPTURED": "2026-11-20 10:00", "LATITUDE": "0", "LONGITUDE": "0"},
                  {"CAPTURED": "2026-11-20 11:00", "LATITUDE": None},
                  {"CAPTURED": None},
                  {"CAPTURED": "2026-11-20 12:00", "STORAGE_PATH": "x"},
                  {"CAPTURED": "2026-11-20 12:00", "STORAGE_PATH": "x"})
    raw.loc[6, "IDPLACAS"] = raw.loc[5, "IDPLACAS"]          # duplicata exata
    p = P.preparar(raw)
    assert list(p["placa_n"]) == ["ZZA1B23", "ZZA1B23"]
    assert p.iloc[0]["LOCALITY"] is None and p.iloc[0]["cidade_n"] == "SAO PAULO"
    assert P.normalizar_placa(" zza-1b23 ") == "ZZA1B23" and P.normalizar_placa("ZZA1B2") is None


def test_faixa_circular_e_desempates():
    assert P.faixa_2h([23, 0]) == 23 and P.rotulo_faixa(23) == "23h–1h"
    assert P.faixa_2h([7, 8, 8, 9]) == 7
    assert P.faixa_2h([5, 6]) == 5
    assert P.faixa_2h([3, 5]) == 3          # janela 2–4 empata, mas começa em hora sem passagem


def test_celula_330m():
    assert P.celula(-23.5500, -46.6300) == P.celula(-23.5509, -46.6300)       # ~100 m
    assert P.celula(-23.5500, -46.6300) != P.celula(-23.5554, -46.6300)       # ~600 m


def _cel(id_, dias, passagens, ultima):
    return {"id": id_, "dias": dias, "passagens": passagens, "ultima": pd.Timestamp(ultima)}


def test_principal_desempates():
    assert P.principal([_cel((0, 0), 3, 9, "2026-11-01"), _cel((0, 1), 4, 4, "2026-10-01")])["id"] == (0, 1)
    assert P.principal([_cel((0, 0), 4, 5, "2026-11-01"), _cel((0, 1), 4, 6, "2026-10-01")])["id"] == (0, 1)
    assert P.principal([_cel((0, 0), 4, 6, "2026-11-01"), _cel((0, 1), 4, 6, "2026-10-01")])["id"] == (0, 0)
    assert P.principal([]) is None


def test_estados_limiares():
    e = P.estado_de
    assert e(6, True, True) == "PADRAO_OBSERVADO"
    assert e(5, True, True) == e(4, True, True) == "PADRAO_EM_FORMACAO"
    assert e(3, True, True) == e(1, True, True) == "APRENDENDO"
    assert e(None, True, True) == "SEM_CAPTURA_RECENTE"
    assert e(None, True, False) == "SEM_CAPTURA"
    assert e(None, False, False) == "SEM_PLACA"


def test_sequencia_letras():
    cels = [{"id": (0, k), "dias": 2 + k, "passagens": 2 + k, "ultima": pd.Timestamp("2026-11-20"), "faixa": 20 - k,
             "hora_tipica": 20.5 - k, "endereco": {"bairro": f"B{k}", "cidade": "SAO PAULO", "uf": "SP"}} for k in range(10)]
    cels.append({"id": (1, 0), "dias": 1, "passagens": 1, "ultima": pd.Timestamp("2026-11-21"), "faixa": 3,
                 "hora_tipica": 3.0, "endereco": {"bairro": None, "cidade": "SAO PAULO", "uf": "SP"}})
    seq = P.sequencia(cels)
    assert [s["letra"] for s in seq] == list("ABCDEFGH")
    assert (1, 0) not in [s["id"] for s in seq] and (0, 0) not in [s["id"] for s in seq]   # 1 dia; e o mais leve fica fora
    assert [s["faixa"] for s in seq] == sorted(s["faixa"] for s in seq)
    txt = P.texto_sequencia(seq[:2])
    assert txt == "Costuma aparecer em A (B9, 11h–13h), depois em B (B8, 12h–14h)."
    assert P.texto_sequencia(seq[:1]) is None


def test_area():
    assert P.area_km([(-23.55, -46.63)]) == ([(-23.55, -46.63)], 0.3)
    pts = [(-23.55, -46.63), (-23.55, -46.61), (-23.53, -46.63), (-23.54, -46.62)]
    vert, km = P.area_km(pts)
    assert len(vert) == 3 and (-23.54, -46.62) not in vert
    assert km == pytest.approx(P.haversine(-23.55, -46.61, -23.53, -46.63), abs=0.01)
    assert km == pytest.approx(3.03, abs=0.02)


def test_endereco_banco_e_perto_de_casa():
    end = pd.DataFrame({"CPF": ["C1", "C1", "C1"], "TIPO": ["RESIDENCIAL", "RESIDENCIAL", "COMERCIAL"],
                        "DATA_CADASTRO": pd.to_datetime(["2020-01-01", "2022-01-01", "2025-01-01"]),
                        "CEP": ["11111000", "22222000", "33333000"]})
    assert P.endereco_banco(end)["CEP"] == "22222000"
    assert P.endereco_banco(end[end["TIPO"] == "COMERCIAL"])["CEP"] == "33333000"
    assert P.endereco_banco(end.iloc[0:0]) is None
    assert P.perto_de_casa("22222999", "22222000") is True
    assert P.perto_de_casa("2222299", "22222000") is False and P.perto_de_casa(None, "22222000") is False


def test_carga_ignora_capturas_futuras():
    prep = P.preparar(cap_raw({"CAPTURED": "2026-11-25 10:00"}, {"CAPTURED": "2026-11-26 08:00"},
                              {"CAPTURED": "2026-11-10 10:00"}))
    c7 = P.carga(prep, info(), END, pd.Timestamp("2026-11-26 07:05"))["P1"]["resumo"]
    c9 = P.carga(prep, info(), END, pd.Timestamp("2026-11-26 09:05"))["P1"]["resumo"]
    assert (c7["n"], c7["n7"], c7["n30"], c7["ult"]) == (2, 1, 2, pd.Timestamp("2026-11-25 10:00"))
    assert (c9["n"], c9["n7"], c9["ult"]) == (3, 2, pd.Timestamp("2026-11-26 08:00"))
    assert c9["estado"] == "APRENDENDO" and c9["dias"] == 3 and c9["principal"] == "CENTRO, SAO PAULO/SP"
    assert P.carga(prep, info(placa="ZZB9C99"), END, pd.Timestamp("2026-11-26 09:05")) == {}


def test_carga_estado_sem_captura_recente():
    prep = P.preparar(cap_raw({"CAPTURED": "2026-08-01 10:00"}))
    r = P.carga(prep, info(), END, pd.Timestamp("2026-11-26 09:05"))["P1"]["resumo"]
    assert r["estado"] == "SEM_CAPTURA_RECENTE" and r["dias"] is None and r["n30"] == 0


def test_cargas_falha_1505(sim):
    cs = P.cargas(sim)
    assert [c["agora"] for c in cs] == ["07:05", "09:05", "11:05", "13:05", "15:05", "17:05"]
    assert cs[4]["falhou"] and not any(c["falhou"] for i, c in enumerate(cs) if i != 4)
    assert cs[4]["pastas"] is cs[3]["pastas"] and cs[4]["ate"] == cs[3]["ate"]
    assert cs[0]["ate"] <= pd.Timestamp("2026-11-26 07:05") < cs[5]["ate"]
