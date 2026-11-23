import pytest

from src import referencia as R
from tests.construtores import mini_payload, pasta, um_dia

LD, AG, EM = "LIMINAR DEFERIDA", "AGUARDANDO LIMINAR", "EMENDAR INICIAL"


def tudo(pl, filtros=None, agora="17:05"):
    return R.tudo(pl, agora, filtros or {})


def test_kpi_prox7_exclui_hoje_e_vencidos_ate_ontem():
    pl = um_dia([pasta("A", LD, -1), pasta("B", LD, 0), pasta("C", LD, 7), pasta("D", LD, 8), pasta("E", LD, None)])
    k = tudo(pl)["kpis"]["atual"]
    assert (k["processos"], k["vencidos"], k["hoje"], k["prox7"]) == (5, 1, 1, 1)


def test_atalho_proximos_7_inclui_hoje():   # o atalho é um filtro de datas hoje..hoje+7 (inclusivo)
    pl = um_dia([pasta("A", LD, -1), pasta("B", LD, 0), pasta("C", LD, 7), pasta("D", LD, 8)])
    assert tudo(pl, {"de": "2026-11-26", "ate": "2026-12-03"})["kpis"]["atual"]["processos"] == 2   # B (hoje) e C (+7)


def test_filtro_datas_bordas():
    pl = um_dia([pasta("A", LD, -3), pasta("B", LD, 0), pasta("C", LD, 5), pasta("D", LD, None)])
    assert tudo(pl, {"de": "2026-11-26"})["kpis"]["atual"]["processos"] == 2          # só "de"; sem data sai
    assert tudo(pl, {"ate": "2026-11-26"})["kpis"]["atual"]["processos"] == 2         # só "ate"
    assert tudo(pl, {"de": "2026-11-30", "ate": "2026-11-27"})["kpis"]["atual"]["processos"] == 0


def test_filtros_e_entre_grupos_ou_dentro():
    pl = um_dia([pasta("A", LD, uf="SP", adv="ADV-01"), pasta("B", LD, uf="RJ", adv="ADV-01"),
                 pasta("C", AG, uf="RJ", adv="ADV-02")])
    assert tudo(pl, {"uf": ["SP", "RJ"], "adv": ["ADV-01"]})["kpis"]["atual"]["processos"] == 2
    assert tudo(pl, {"etapa": ["AGUARDANDO LIMINAR"]})["kpis"]["atual"]["processos"] == 1


def test_escada_chegou_cumulativo():
    rows = ([pasta(f"a{i}", "1º MANDADO NEGATIVO") for i in range(10)] + [pasta(f"b{i}", "2º MANDADO EXPEDIDO") for i in range(5)]
            + [pasta(f"c{i}", "6º OU + MANDADO REQUERIDO") for i in range(5)])
    e = tudo(um_dia(rows))["escada"]
    assert e["em_mandado"] == 20
    assert [round(x["chegou"], 6) for x in e["linhas"]] == [100.0, 50.0, 25.0, 25.0, 25.0, 25.0]
    assert e["linhas"][5]["REQUERIDO"] == 5 and e["linhas"][0]["NEGATIVO"] == 10


def test_escada_vazia_sem_mandado():
    assert tudo(um_dia([pasta("A", LD)]))["escada"] is None


def test_sinais_advogado():
    rows = []
    for adv, n in (("ADV-01", 30), ("ADV-02", 32), ("ADV-03", 40), ("ADV-04", 50), ("ADV-05", 10)):
        rows += [pasta(f"{adv}-{i}", LD, 5, adv=adv) for i in range(n)]
    a = tudo(um_dia(rows))["advogados"]
    assert a["n_comparaveis"] == 4 and a["mediana"] == 36
    sinais = {x["adv"]: x["carga_alta"] for x in a["linhas"]}
    assert sinais == {"ADV-01": False, "ADV-02": False, "ADV-03": False, "ADV-04": True, "ADV-05": False}


def test_mediana_exige_3_comparaveis():
    rows = [pasta(f"{adv}-{i}", LD, adv=adv) for adv in ("ADV-01", "ADV-02") for i in range(40)]
    a = tudo(um_dia(rows))["advogados"]
    assert a["mediana"] is None and not any(x["carga_alta"] for x in a["linhas"])


def test_vencidos_alto_usa_carteira_com_sem_advogado():
    rows = [pasta(f"x{i}", LD, -1 if i < 12 else 5, adv="ADV-01") for i in range(30)]          # 40% vencidos
    rows += [pasta(f"s{i}", LD, 5, adv=None) for i in range(30)]                                # sem advogado, 0%
    a = tudo(um_dia(rows))["advogados"]
    assert a["pct_carteira"] == pytest.approx(20.0)
    linha = {x["adv"]: x for x in a["linhas"]}
    assert linha["ADV-01"]["venc_alto"] and not linha["(sem advogado)"]["venc_alto"]
    assert [x["adv"] for x in a["linhas"]][-1] == "(sem advogado)"


def test_cobertura_faixas_fechadas_a_esquerda():
    rows = [pasta("A", LD, risco=100.0, bem=50.0), pasta("B", LD, risco=100.0, bem=100.0), pasta("C", LD, risco=100.0, bem=None),
            pasta("D", LD, risco=None, bem=10.0), pasta("E", LD, risco=100.0, bem=79.9)]
    f = dict(tudo(um_dia(rows))["risco_uf"]["faixas"])
    assert f == {"< 50%": 0, "50-80%": 2, "80-100%": 0, ">= 100%": 1, "sem bem ou risco <= 0": 1}
    assert tudo(um_dia(rows))["risco_etapa"]["sem_estoque"] == 1


def test_perfil_idade_faixas():
    rows = [pasta("A", LD, ano=2027), pasta("B", LD, ano=1960), pasta("C", LD, ano=2016), pasta("D", LD, ano=None),
            pasta("E", LD, ano=2009)]
    assert dict(tudo(um_dia(rows))["perfil"]["idade"]) == {"ate 5 anos": 1, "6-10 anos": 1, "16+ anos": 1, "sem ano": 2}


def test_perfil_marcas_top10_e_demais():
    rows = [pasta(f"m{i}", LD, marca=f"M{i:02d}") for i in range(12)] + [pasta("x", LD, marca="M00")]
    m = tudo(um_dia(rows))["perfil"]["marcas"]
    assert m[0] == ["M00", 2] and len(m) == 11 and m[-1] == ["(demais marcas)", 2]


def test_destaques_textos_exatos():
    rows = [pasta(f"l{i}", LD, -1 if i < 2 else 3, risco=1_500_000.0) for i in range(3)]
    rows += [pasta(f"v{i}", AG, -2) for i in range(7)]
    d = {x["chave"]: x["achado"] for x in tudo(um_dia(rows))["destaques"]}
    assert d["liminar_deferida"] == ("3 processos com liminar deferida aguardando requerimento de mandado (R$ 4,5 mi em risco). "
                                     "2 deles com data de agendamento já vencida.")
    assert d["vencidos"] == "9 agendamentos vencidos (90% da carteira filtrada)."
    assert "escada" not in d and "uf_negativo" not in d


def test_destaque_singular():
    d = tudo(um_dia([pasta("A", LD, -1, risco=999.0)]))["destaques"]
    assert d[0]["achado"].startswith("1 processo com liminar deferida") and "(R$ 999 em risco)" in d[0]["achado"]
    assert d[1]["achado"] == "1 agendamento vencido (100% da carteira filtrada)."


def test_destaque_escada_e_uf_negativo():
    rows = [pasta(f"n{i}", "3º MANDADO NEGATIVO", uf="BA") for i in range(30)]
    rows += [pasta(f"e{i}", "1º MANDADO EXPEDIDO", uf="SP") for i in range(30)]
    d = {x["chave"]: x["achado"] for x in tudo(um_dia(rows))["destaques"]}
    assert d["escada"] == "30 processos (50% dos que estão em mandado) já passaram da 2ª tentativa."
    assert d["uf_negativo"] == "BA: 100% dos processos da UF estão em mandado negativo, contra 50% no total."


def test_destaque_uf_negativo_usa_mapa_com_filtro_uf():
    rows = [pasta(f"n{i}", "3º MANDADO NEGATIVO", uf="BA") for i in range(30)]
    rows += [pasta(f"e{i}", "1º MANDADO EXPEDIDO", uf="SP") for i in range(30)]
    d = {x["chave"] for x in tudo(um_dia(rows), {"uf": ["BA"]})["destaques"]}
    assert "uf_negativo" not in d                       # só BA no recorte: 100% contra 100%


def test_mapa_ignora_filtro_uf():
    rows = [pasta("A", LD, uf="SP"), pasta("B", "2º MANDADO NEGATIVO", uf="RJ", risco=5.0)]
    t = tudo(um_dia(rows), {"uf": ["SP"]})
    assert t["mapa_uf"] == {"RJ": [1, 5.0, 1], "SP": [1, 1000.0, 0]} and t["kpis"]["atual"]["processos"] == 1


def test_comarcas_top15_moda_uf_e_sem_comarca():
    rows = [pasta(f"c{i}", "1º MANDADO NEGATIVO" if i < 2 else LD, comarca="RECIFE", uf="PE" if i else None) for i in range(4)]
    rows += [pasta("x", LD, comarca=None)]
    c = tudo(um_dia(rows))["comarcas"]
    assert c[0][:3] == ["RECIFE", "PE", 4] and c[0][3] == pytest.approx(50.0) and c[1][0] == "(sem comarca)"


def test_follow_ordem_excel_e_so_qtd_maior_que_zero():
    rows = [pasta("A", EM), pasta("B", AG), pasta("C", "1º MANDADO EXPEDIDO")]
    assert [x[0] for x in tudo(um_dia(rows))["tabelas"]["follow"]] == ["AGUARDANDO LIMINAR", "MANDADO EXPEDIDO", "EMENDAR INICIAL"]


def test_produtivos_ordem_texto_pura():
    rows = [pasta("A", AG), pasta("B", "6º OU + MANDADO EXPEDIDO"), pasta("C", "1º MANDADO EXPEDIDO")]
    t = tudo(um_dia(rows))["tabelas"]
    assert [x[0] for x in t["produtivos"]] == ["1º MANDADO EXPEDIDO", "6º OU + MANDADO EXPEDIDO", "AGUARDANDO LIMINAR"]
    assert t["diligencia"] == [["1º MANDADO EXPEDIDO", 1]]


def _tres_fotos():
    f0 = ("2026-11-23", "18:00", "reconstruido", [pasta("A", "EMENDA REALIZADA"), pasta("B", AG)])
    f1 = ("2026-11-25", "17:05", "ao_vivo", [pasta("A", AG), pasta("B", AG)])
    f2 = ("2026-11-26", "07:05", "ao_vivo", [pasta("A", AG), pasta("B", LD)])
    f3 = ("2026-11-26", "09:05", "ao_vivo", [pasta("A", LD), pasta("C", EM)])
    pubs = [{"agora": "07:05", "foto": 2, "origem": "ao_vivo", "quando": "07:05", "avisos": [], "base": 2, "anterior": 1,
             "conciliacao": None},
            {"agora": "09:05", "foto": 3, "origem": "ao_vivo", "quando": "09:05", "avisos": [], "base": 2, "anterior": 1,
             "conciliacao": None},
            {"agora": "13:05", "foto": 2, "origem": "oficial", "quando": "09:04", "avisos": [], "base": 2, "anterior": 1,
             "conciliacao": None}]
    return mini_payload([f0, f1, f2, f3], pubs)


def test_evolucao_lacuna_reconstruido_extintas():
    e = tudo(_tres_fotos(), agora="09:05")["evolucao"]
    assert e["dias"] == ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"]
    assert e["lacuna"] == [False, True, False, False] and e["reconstruido"] == [True, False, False, False]
    assert e["total"] == [2, None, 2, 2] and e["extintas"] == [1, None, 0, 0]
    assert e["por_etapa"]["LIMINAR DEFERIDA"] == [0, None, 0, 1]


def test_movimentacao_entre_base_e_atual():
    m = tudo(_tres_fotos(), agora="09:05")["movimentacao"]
    assert (m["entradas"], m["saidas"], m["mud_agendamento"], m["mud_etapa"]) == (1, 1, 1, 1)
    assert m["transicoes"] == [["AGUARDANDO LIMINAR", "LIMINAR DEFERIDA", 1]]
    assert ["entrada", "C"] in m["movimentos"] and ["saida", "B"] in m["movimentos"]


def test_movimentacao_vazia_na_base_e_oficial():
    pl = _tres_fotos()
    assert tudo(pl, agora="07:05")["movimentacao"] == {"vazia": "base"}
    assert tudo(pl, agora="13:05")["movimentacao"] == {"vazia": "oficial"}


def test_kpi_da_referencia_usa_a_data_da_propria_foto():
    k = tudo(_tres_fotos(), agora="09:05")["kpis"]
    assert k["anterior"]["dia"] == "2026-11-25" and k["inicio"]["hora"] == "07:05"
    # na foto de 25/11 as datas 0 (= 26/11) ficam no futuro: nenhum vencido, nenhum "hoje"
    assert k["anterior"]["kpis"]["hoje"] == 0 and k["anterior"]["kpis"]["prox7"] == 2


def test_regioes_modos_e_brasil():
    rows = [pasta(f"{u}{i}", LD, uf=u) for u in ("SP", "RJ", "MG", "BA", "PR", "RS") for i in range(3)]
    pl = um_dia(rows)
    assert tudo(pl)["regioes"] is None
    r1 = tudo(pl, {"uf": ["SP"]})["regioes"]
    assert r1["modo"] == 1 and r1["brasil"]["kpis"]["processos"] == 18 and r1["ufs"][0]["part_processos"] == pytest.approx(100 / 6)
    assert tudo(pl, {"uf": ["SP", "RJ", "MG"]})["regioes"]["modo"] == 2
    assert tudo(pl, {"uf": ["SP", "RJ", "MG", "BA", "PR"]})["regioes"]["modo"] == 5


def test_recorte_vazio_sem_quebrar():
    t = tudo(um_dia([pasta("A", LD, uf="SP")]), {"uf": ["AC"]})
    assert t["kpis"]["atual"]["processos"] == 0 and t["escada"] is None and t["destaques"] == []
    assert t["regioes"]["ufs"][0]["pct"]["vencidos"] is None and t["advogados"]["linhas"] == []
    assert t["risco_etapa"]["cobertura_mediana"] is None


def test_movimentacao_com_recorte_vazio_mostra_vazio():
    assert tudo(_tres_fotos(), {"uf": ["AC"]}, agora="09:05")["movimentacao"] == {"vazia": "recorte"}


# ---------- placas ----------
from tests.construtores import placas_min  # noqa: E402

SP = ("SAO PAULO", "SP", "CENTRO")
RJ = ("RIO DE JANEIRO", "RJ", "CENTRO")
AGORA_MIN = 17 * 60 + 5


def _cap(ult, loc=SP, est="APRENDENDO", dias=2):
    return [ult, loc, 3, 1, 2, est, dias, "CENTRO, SAO PAULO/SP"]


def test_janelas_bordas():
    pl = placas_min(um_dia([pasta("a", "1º MANDADO EXPEDIDO"), pasta("b", "1º MANDADO EXPEDIDO"),
                            pasta("c", "1º MANDADO EXPEDIDO")]),
                    {"a": _cap(AGORA_MIN - 1440), "b": _cap(AGORA_MIN - 1441), "c": _cap(AGORA_MIN - 43201)}, {})
    L = R.tudo(pl, "17:05", {})["localizado"]
    assert (L["j24"], L["j7"], L["j30"], L["total"], L["base"], L["com_placa"]) == (1, 2, 2, 3, 3, 3)
    assert L["por_etapa"][0] == ["MANDADO EXPEDIDO", 1, 2, 2, "Informar o local ao oficial de justiça"]
    assert L["total_etapas"] == [1, 2, 2]


def test_fora_da_uf():
    pl = placas_min(um_dia([pasta("a", "LIMINAR DEFERIDA"), pasta("b", "LIMINAR DEFERIDA"), pasta("c", "LIMINAR DEFERIDA")]),
                    {"a": _cap(0, RJ), "b": _cap(0, (None, None, None)), "c": _cap(0)}, {})
    L = R.tudo(pl, "17:05", {})["localizado"]
    assert L["fora_uf"] == 1 and L["pct_fora"] == pytest.approx(100 / 3)


def test_cidades_desempate():
    rows = [pasta(x, "LIMINAR DEFERIDA") for x in "abcd"]
    pl = placas_min(um_dia(rows), {"a": _cap(0, RJ), "b": _cap(0), "c": _cap(0, ("CAMPINAS", "SP", None)),
                                   "d": _cap(0, ("CAMPINAS", "SP", "X"))}, {})
    L = R.tudo(pl, "17:05", {})["localizado"]
    assert [c[:3] for c in L["cidades"]] == [["CAMPINAS", "SP", 2], ["RIO DE JANEIRO", "RJ", 1], ["SAO PAULO", "SP", 1]]
    assert L["cidades"][0][3] == pytest.approx(50.0)


def test_recentes_ordem():
    rows = [pasta("a", "AGUARDANDO LIMINAR"), pasta("b", "1º MANDADO EXPEDIDO"), pasta("c", "1º MANDADO EXPEDIDO"),
            pasta("d", "1º MANDADO EXPEDIDO")]
    pl = placas_min(um_dia(rows), {"a": _cap(AGORA_MIN - 5), "b": _cap(AGORA_MIN - 60), "c": _cap(AGORA_MIN - 30),
                                   "d": _cap(AGORA_MIN - 2000)}, {})
    rec = R.tudo(pl, "17:05", {})["localizado"]["recentes"]
    assert [r["pasta"] for r in rec] == ["c", "b", "a"] and rec[0]["min"] == 30 and rec[0]["local"] == "SAO PAULO/SP, CENTRO"


def test_estados_soma_base():
    rows = [pasta(x, "LIMINAR DEFERIDA") for x in "abcd"]
    pl = placas_min(um_dia(rows), {"a": _cap(0, est="PADRAO_OBSERVADO", dias=7),
                                   "b": _cap(-90000, est="SEM_CAPTURA_RECENTE", dias=None)}, {"d": None})
    E = R.tudo(pl, "17:05", {})["localizado"]["estados"]
    assert E == {"PADRAO_OBSERVADO": 1, "PADRAO_EM_FORMACAO": 0, "APRENDENDO": 0, "SEM_CAPTURA_RECENTE": 1,
                 "SEM_CAPTURA": 1, "SEM_PLACA": 1}
    assert sum(E.values()) == 4


def test_lista_padroes_ordem_e_busca():
    rows = [pasta("p1", "AGUARDANDO LIMINAR"), pasta("p2", "1º MANDADO EXPEDIDO"), pasta("p3", "1º MANDADO EXPEDIDO")]
    pl = placas_min(um_dia(rows), {"p1": _cap(0, est="PADRAO_OBSERVADO", dias=8), "p2": _cap(-10),
                                   "p3": _cap(-5)}, {"p2": "ZZA1B23"})
    L = R.lista_padroes(pl, "17:05", {}, list(R.ESTADOS_PADRAO), "")
    assert [x["pasta"] for x in L] == ["p3", "p2", "p1"]
    assert [x["pasta"] for x in R.lista_padroes(pl, "17:05", {}, list(R.ESTADOS_PADRAO), "zza-1b2")] == ["p2"]


def test_lista_padroes_com_passagens():
    rows = [pasta("p1", "AGUARDANDO LIMINAR"), pasta("p2", "AGUARDANDO LIMINAR")]
    pl = placas_min(um_dia(rows), {"p1": _cap(0, est="PADRAO_OBSERVADO", dias=8) + [41, 17]}, {"p2": None})
    L = {x["pasta"]: x for x in R.lista_padroes(pl, "17:05", {}, list(pl["placas"]["estados"]), "")}
    assert (L["p1"]["passagens"], L["p1"]["passagens_pp"]) == (41, 17)
    assert (L["p2"]["passagens"], L["p2"]["passagens_pp"]) == (None, None)


def test_regiao_e_mapa_localizados():
    rows = [pasta("a", "LIMINAR DEFERIDA"), pasta("b", "LIMINAR DEFERIDA", uf="RJ")]
    pl = placas_min(um_dia(rows), {"a": _cap(0, RJ), "b": _cap(-50000)}, {})
    res = R.tudo(pl, "17:05", {"uf": ["SP"]})
    assert res["mapa_localizados"] == {"RJ": 1}
    assert res["regioes"]["ufs"][0]["localizados"] == {"d30": 1, "pct": 100.0}
    assert res["regioes"]["brasil"]["localizados"] == {"d30": 1, "pct": 50.0}
