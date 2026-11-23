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


# ---------- trajetos (capturas seguidas, células diferentes, até 3 h) ----------

A_ = {"LATITUDE": "-23.550000", "LONGITUDE": "-46.630000", "LOCALITY": "CENTRO"}
B_ = {"LATITUDE": "-23.560000", "LONGITUDE": "-46.640000", "LOCALITY": "VILA NOVA"}


def _traj(*rows):
    prep = P.preparar(cap_raw(*rows))
    cels = sorted(P.celulas(prep), key=P._chave_peso)
    return P.trajetos(prep, cels), cels


def test_trajeto_recorrente():
    t, cels = _traj(A_ | {"CAPTURED": "2026-11-20 08:00"}, B_ | {"CAPTURED": "2026-11-20 08:30"},
                    A_ | {"CAPTURED": "2026-11-21 08:10"}, B_ | {"CAPTURED": "2026-11-21 08:50"})
    assert len(t) == 1
    x = t[0]
    assert cels[x["de"]]["endereco"]["bairro"] == "CENTRO" and cels[x["para"]]["endereco"]["bairro"] == "VILA NOVA"
    assert (x["dias"], x["passagens"], x["minutos"], x["faixa"], x["recorrente"]) == (2, 2, 35, 8, True)
    assert x["km"] == round(P.haversine(-23.55, -46.63, -23.56, -46.64), 1)


def test_ida_e_volta_sao_trajetos_distintos():
    t, cels = _traj(A_ | {"CAPTURED": "2026-11-20 08:00"}, B_ | {"CAPTURED": "2026-11-20 08:30"},
                    A_ | {"CAPTURED": "2026-11-20 09:00"})
    assert sorted((cels[x["de"]]["endereco"]["bairro"], cels[x["para"]]["endereco"]["bairro"]) for x in t) == \
        [("CENTRO", "VILA NOVA"), ("VILA NOVA", "CENTRO")]
    assert not any(x["recorrente"] for x in t)


def test_intervalo_maior_que_3h_nao_e_trajeto():
    assert _traj(A_ | {"CAPTURED": "2026-11-20 08:00"}, B_ | {"CAPTURED": "2026-11-20 11:01"})[0] == []
    assert len(_traj(A_ | {"CAPTURED": "2026-11-20 08:00"}, B_ | {"CAPTURED": "2026-11-20 11:00"})[0]) == 1


def test_mesmo_ponto_nao_e_trajeto():
    assert _traj(A_ | {"CAPTURED": "2026-11-20 08:00"}, A_ | {"CAPTURED": "2026-11-20 08:20"})[0] == []
    t, _ = _traj(A_ | {"CAPTURED": "2026-11-20 08:00"}, A_ | {"CAPTURED": "2026-11-20 08:20"},
                 B_ | {"CAPTURED": "2026-11-20 08:50"})
    assert len(t) == 1 and t[0]["minutos"] == 30          # conta a partir da captura seguida, não da primeira


def test_recorrentes_primeiro_e_limite_de_12():
    rows = [{"CAPTURED": f"2026-11-20 {6 + k // 6:02d}:{(k % 6) * 10:02d}", "LATITUDE": f"{-23.5 - 0.01 * k:.6f}",
             "LOCALITY": f"B{k}"} for k in range(14)]
    rows += [A_ | {"CAPTURED": "2026-11-21 08:00"}, B_ | {"CAPTURED": "2026-11-21 08:30"},
             A_ | {"CAPTURED": "2026-11-22 08:00"}, B_ | {"CAPTURED": "2026-11-22 08:30"}]
    t, _ = _traj(*rows)
    assert len(t) == P.MAX_TRAJETOS == 12 and t[0]["recorrente"] and not any(x["recorrente"] for x in t[1:])


def test_principal_de_um_dia_sem_letra():
    cels = [{"id": (0, k), "dias": 1, "passagens": 1, "ultima": pd.Timestamp("2026-11-20"), "faixa": 8 + k,
             "hora_tipica": 8.0 + k, "endereco": {}} for k in range(3)]
    assert P.sequencia(cels) == []


def test_pasta_tem_trajetos_e_passagens_na_janela():
    prep = P.preparar(cap_raw(A_ | {"CAPTURED": "2026-08-01 08:00"}, A_ | {"CAPTURED": "2026-11-20 08:00"},
                              B_ | {"CAPTURED": "2026-11-20 08:30"}))
    r = P.carga(prep, info(), END, pd.Timestamp("2026-11-26 09:05"))["P1"]
    assert r["resumo"]["passagens_janela"] == 2 and r["resumo"]["n"] == 3
    assert len(r["detalhe"]["trajetos"]) == 1


PASTA_README = "7012366"          # a pasta do link direto do README (?aba=padroes&pasta=...)
COM_CAPTURA = {"PADRAO_OBSERVADO", "PADRAO_EM_FORMACAO", "APRENDENDO"}


def test_proporcao_de_trajetos(sim):
    # calibrada pelo real: 38% das placas com captura na janela têm trajeto, 10% com trajeto repetido
    ult = [v for v in P.cargas(sim)[-1]["pastas"].values() if v["resumo"]["estado"] in COM_CAPTURA]
    com = [v for v in ult if v["detalhe"]["trajetos"]]
    rec = [v for v in com if any(t["recorrente"] for t in v["detalhe"]["trajetos"])]
    assert 0.33 <= len(com) / len(ult) <= 0.42 and 0.09 <= len(rec) / len(ult) <= 0.16


def test_pasta_do_readme_tem_trajetos(sim):
    from pathlib import Path
    p = P.cargas(sim)[-1]["pastas"][PASTA_README]
    assert p["resumo"]["estado"] == "PADRAO_OBSERVADO" and sum(t["recorrente"] for t in p["detalhe"]["trajetos"]) >= 2
    assert sum(1 for x in p["detalhe"]["pontos"] if x["letra"]) >= 2
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    assert f"?aba=padroes&pasta={PASTA_README}" in readme and "pasta=7007528" not in readme
    mapa = next(l for l in readme.splitlines() if "mapa de ruas (OpenStreetMap)" in l)
    assert f"pasta={PASTA_README}" in mapa                                  # o link fica no item do mapa e dos trajetos
    assert "placas com captura nos 60 dias" not in readme


# ---------- apreendidos com captura antes (estado do padrão na data real da apreensão) ----------

def _aps(*linhas):
    base = {"PASTA": "P1", "PLACA": "ZZA1B23", "DT_APREENSAO": pd.Timestamp("2026-11-20"), "UF": "SP", "ADVOGADO": "ADV-01",
            "LOCALIZADOR": "ARARA"}
    return pd.DataFrame([base | x for x in (linhas or [{}])])


def test_estado_na_data_da_apreensao():
    rows = [A_ | {"CAPTURED": f"2026-11-{d:02d} 08:00"} for d in (10, 12, 14, 16, 18, 20)]
    rows += [A_ | {"CAPTURED": "2026-11-20 21:00"}, A_ | {"CAPTURED": "2026-11-22 08:00"}]     # a do dia 22 é depois
    prep = P.preparar(cap_raw(*rows))
    a18 = P.apreendidos_com_captura(prep, _aps({"DT_APREENSAO": pd.Timestamp("2026-11-18")}))["itens"][0]
    assert (a18["estado"], a18["dias"], a18["passagens"]) == ("PADRAO_EM_FORMACAO", 5, 5)
    assert a18["ultima"] == pd.Timestamp("2026-11-18 08:00") and a18["dias_antes"] == 0
    a20 = P.apreendidos_com_captura(prep, _aps())["itens"][0]
    assert (a20["estado"], a20["passagens"], a20["ultima"]) == ("PADRAO_OBSERVADO", 7, pd.Timestamp("2026-11-20 21:00"))
    assert a20["local"] == "CENTRO, SAO PAULO/SP" and a20["principal"] == "CENTRO, SAO PAULO/SP"


def test_dias_antes_nunca_negativo():
    prep = P.preparar(cap_raw(A_ | {"CAPTURED": "2026-11-22 08:00"}, A_ | {"PLATE": "ZZB2C34", "CAPTURED": "2026-08-01 08:00"}))
    r = P.apreendidos_com_captura(prep, _aps({"DT_APREENSAO": pd.Timestamp("2026-11-25")},
                                             {"PASTA": "P2"},                                     # só captura depois
                                             {"PASTA": "P3", "PLACA": "ZZB2C34"},                 # só captura antiga
                                             {"PASTA": "P4", "PLACA": None}))
    it = {x["pasta"]: x for x in r["itens"]}
    assert it["P1"]["dias_antes"] == 3 and it["P1"]["estado"] == "APRENDENDO"
    assert it["P2"]["estado"] == "SEM_CAPTURA" and it["P2"]["dias_antes"] is None and it["P2"]["ultima"] is None
    assert it["P3"]["estado"] == "SEM_CAPTURA_RECENTE" and it["P3"]["dias_antes"] > 60
    assert it["P4"]["estado"] == "SEM_PLACA"
    assert all(x["dias_antes"] is None or x["dias_antes"] >= 0 for x in r["itens"])
    assert (r["total"], r["com_placa"], r["com_captura_antes"], r["na_janela"], r["mediana_dias"]) == (4, 3, 2, 1, 3)


def test_apreendidos_da_simulacao(sim):
    r = P.apreendidos_da_simulacao(sim)
    assert r["total"] > 1000 and r["com_placa"] <= r["total"] and 20 <= r["na_janela"] <= r["com_captura_antes"]
    na = [x for x in r["itens"] if x["estado"] in COM_CAPTURA]
    assert len(na) == r["na_janela"] and all(x["dias_antes"] >= 0 and x["ultima"].normalize() <= x["dt_apreensao"] for x in na)



def test_apreendido_sem_advogado_casa_com_o_filtro():
    prep = P.preparar(cap_raw(A_ | {"CAPTURED": "2026-11-19 08:00"}))
    it = P.apreendidos_com_captura(prep, _aps({"ADVOGADO": None}))["itens"][0]
    assert it["advogado"] == "(sem advogado)"
