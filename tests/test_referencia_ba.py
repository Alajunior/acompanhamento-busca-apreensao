"""Referência Python das seções da Planilha (Busca e Apreensão): fórmulas fechadas à mão e regras de recorte."""
import copy

from src.referencia_ba import curva, estado, linha_meta, linha_tempo, recortes, secoes

SEM = {}


def test_linha_meta_formulas():
    l = linha_meta(50, 800_000.0, 30, 450_000.0, du_total=19, du_atual=17)
    assert l["pct_qtd"] == 0.6 and l["falta_qtd"] == -20 and l["tkt_meta"] == 16_000.0 and l["tkt_real"] == 15_000.0
    assert l["falta_dia_qtd"] == 10                      # ARRED.CIMA(20 / 2)
    assert l["falta_dia_valor"] == 175_000.0             # ARRED(350.000 / 2; 2)
    assert l["proj_qtd"] == 34                           # ARRED(30 / 17 × 2) + 30 = 4 + 30
    assert l["proj_valor"] == 510_000.0                  # 34 × 15.000
    assert l["proj_pct_qtd"] == 0.68 and l["tkt_falta"] == 17_500.0


def test_linha_meta_sem_meta_e_mes_futuro():
    l = linha_meta(None, None, 3, 40_000.0, du_total=20, du_atual=0)
    assert l["pct_qtd"] is None and l["falta_qtd"] is None and l["proj_qtd"] is None and l["tkt_real"] == 40_000.0 / 3


def test_curva_relogio():
    c = curva(220, 1.2, 19, [5, 11, None])
    assert c["total"] == 264 and c["necessidade_dia"] == 13.9 and c["acum"][:2] == [13.9, 27.8] and len(c["acum"]) == 19
    assert c["diferenca"][:3] == [-9, -17, None]


def test_estado_decodifica_passagens(ba_json):
    e = estado(ba_json, "17:05")
    assert len(e["linhas"]) > 1_000 and e["aviso"] is None
    abertas = [p for p in e["passagens"] if p["ATE"] is None]
    assert abertas and all(p["DIAS"] is not None for p in abertas)
    assert {p["RESULTADO"] for p in e["passagens"]} == {"localizou", "encerrada", "substituido", "sem_localizacao"}
    assert estado(ba_json, "11:05")["aviso"] == "Leitura de 11:05 incompleta; mantida a de 09:05."


def test_mes_sem_meta_ou_futuro(ba_json):                 # Review Focus 2
    s = secoes(ba_json, "17:05", {"mes": "12/2026"})
    mb = s["meta_banco"]
    assert mb["aviso"] == "meta não informada para 12/2026" and mb["du_atual"] == 0
    assert all(l["proj_qtd"] is None for l in mb["linhas"])
    assert s["meta_relogio"]["curvas"] == {} and s["nota_mes"] == "Mês 12/2026 · dia útil 0 de 22"


def test_localizados_ignora_mes_apreendidos_respeita(ba_json):
    a, b = secoes(ba_json, "17:05", SEM), secoes(ba_json, "17:05", {"mes": "10/2026"})
    assert a["localizados"] == b["localizados"] and a["mandados"] == b["mandados"]
    assert len(b["apreendidos"]) < len(a["apreendidos"]) and all(r["MES_APREENSAO"] == "10/2026" for r in b["apreendidos"])
    assert {r["ETAPA"] for r in a["localizados"]} <= {"Mandado expedido", "Localizado (diligência)"}


def test_etapa_nao_muda_metas_nem_visao_apreendidos(ba_json):
    a = secoes(ba_json, "17:05", {"mes": "10/2026"})
    b = secoes(ba_json, "17:05", {"mes": "10/2026", "etapa": ["Localizado (diligência)"]})
    for k in ("meta_banco", "meta_relogio", "visao_apreendidos", "comp_analista", "por_localizador"):
        assert a[k] == b[k], k
    assert b["apreendidos"] == []


def test_comp_analista_corta_pelo_du_de_hoje(ba_json):
    e = estado(ba_json, "17:05")
    du_hoje = 17
    s = secoes(ba_json, "17:05", SEM)["comp_analista"]
    total = next(r for r in s["por_adv"] if r["tipo"] == "total")
    for mes in s["meses"]:
        esperado = sum(1 for r in e["linhas"] if r["MES_APREENSAO"] == mes and r["DIA_UTIL"] <= du_hoje)
        assert total["valores"][mes] == esperado


def test_pivo_subtotal_e_total_no_fim(ba_json):
    v = secoes(ba_json, "17:05", SEM)["visao_apreendidos"]["adv_fase"]
    assert v[-1]["tipo"] == "total" and v[-2]["tipo"] == "sub"
    total = v[-1]["qtd"]
    assert total == sum(r["qtd"] for r in v if r["tipo"] == "sub") == sum(r["qtd"] for r in v if r["tipo"] == "")
    fases = [r["fase"] for r in v if r["tipo"] == "" and r["advogado"] == v[0]["advogado"]]
    ordem = ["JUDICIAL 1", "JUDICIAL 2", "JUDICIAL 3", "PREJUÍZO"]
    assert [f for f in fases if f in ordem] == [f for f in ordem if f in fases]


def test_metas_somam_e_tem_faixas(ba_json):
    mb = secoes(ba_json, "17:05", {"mes": "10/2026"})["meta_banco"]
    chaves = [l["chave"] for l in mb["linhas"]]
    assert chaves[:7] == ["JUDICIAL 1", "JUDICIAL 2", "121 A 360", "JUDICIAL 3", "360 A 720", "PREJUÍZO", "> 720"]
    assert chaves[-1] == "TOTAL"
    l = {x["chave"]: x for x in mb["linhas"]}
    assert l["121 A 360"]["real_qtd"] == l["JUDICIAL 1"]["real_qtd"] + l["JUDICIAL 2"]["real_qtd"]
    assert l["TOTAL"]["meta_qtd"] == l["121 A 360"]["meta_qtd"] + l["360 A 720"]["meta_qtd"] + l["> 720"]["meta_qtd"]
    assert mb["du_atual"] == mb["du_total"] == 21


def test_linha_tempo_dias_parado_nunca_negativo_e_janela_tudo(ba_json):   # Review Focus 5
    ba = copy.deepcopy(ba_json)
    e = estado(ba, "17:05")
    aberta = next(r for r in e["linhas"] if r["ETAPA"] == "Mandado expedido")
    ba["marcos"][aberta["PASTA"]] = ba["marcos"].get(aberta["PASTA"], []) + [[3, 9, "2026-11-30", None, "ADV-01"]]
    lt = linha_tempo(ba, "17:05", SEM, "tudo")
    p = next(x for x in lt["pastas"] if x["pasta"] == aberta["PASTA"])
    assert p["dias_parado"] == 0 and lt["de"] < "2026-03-01"
    assert all(x["dias_parado"] is None or x["dias_parado"] >= 0 for x in lt["pastas"])
    curta = linha_tempo(ba_json, "17:05", SEM, "30")
    assert curta["de"] == "2026-10-27" and {x["etapa"] for x in curta["pastas"]} <= {"Mandado expedido", "Localizado (diligência)"}


def test_filtro_que_zera_tudo(ba_json):                # Review Focus 1
    f = {"adv": ["ADV-01"], "uf": ["AC"], "localizador": ["(sem localizador)"], "fase": ["PREJUÍZO"]}
    s = secoes(ba_json, "17:05", f)
    for k in ("localizados", "mandados", "apreendidos"):
        assert s[k] == [], k
    assert s["visao_localizados"]["adv_fase"] == [] and s["comparativo"] == [] and s["por_localizador"] == []
    assert linha_tempo(ba_json, "17:05", f, "90")["pastas"] == []


def test_recortes_ordem_da_lista(ba_json):
    r = recortes(estado(ba_json, "17:05"), SEM)
    etapas = [x["ETAPA"] for x in r["lista"]]
    ordem = ["Apreendido", "Mandado expedido", "Localizado (diligência)", "Localização encerrada sem apreensão"]
    assert etapas == sorted(etapas, key=ordem.index)
