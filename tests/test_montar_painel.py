import json
from pathlib import Path

import pandas as pd
import pytest

from dados.gerar import HOJE, simular
from src.montar_painel import DINAMICAS_BD, montar_bd, montar_html, montar_payload, montar_placas
from src.padroes import ESTADOS
from src.publicacao import linha_do_tempo
from src.regra import COLUNAS, TIPOS, chave


def decodificar_foto(pl: dict, k: int) -> set[tuple]:
    estado: dict[int, tuple] = {}
    for j in range(k + 1):
        e = pl["fotos"][j]["estado"]
        if isinstance(e, list):
            estado = {i: (i, t, d) for i, t, d in e}
        else:
            for i in e["sai"]:
                estado.pop(i)
            for i, t, d in e["muda"]:
                estado[i] = (i, t, d)
    return set(estado.values())


def esperado(pl: dict, foto) -> set[tuple]:
    idx = {p: i for i, p in enumerate(pl["pastas"]["pasta"])}
    tipos = {t: i for i, t in enumerate(pl["dic"]["tipo"])}
    out = set()
    for p, t, d in zip(foto.df["PASTA"], foto.df["TIPO_AGENDAMENTO"], foto.df["DATA_AGENDAMENTO"]):
        dias = None if pd.isna(d) else int((pd.Timestamp(d) - HOJE).days)
        out.add((idx[chave(p)], tipos[t], dias))
    return out


def test_delta_reconstroi_cada_foto(linha, payload):
    assert len(payload["fotos"]) == len(linha.fotos)
    for k in (0, 1, len(linha.fotos) // 2, len(linha.fotos) - 1):
        assert decodificar_foto(payload, k) == esperado(payload, linha.fotos[k])
    assert isinstance(payload["fotos"][0]["estado"], list) and isinstance(payload["fotos"][1]["estado"], dict)


def test_dicionarios_e_atributos(payload):
    assert payload["dic"]["tipo"] == list(TIPOS) and payload["hoje"] == "2026-11-26"
    assert "(vazio)" in payload["dic"]["carteira"] and "(sem advogado)" in payload["dic"]["adv"]
    assert all(c == c.strip() for c in payload["dic"]["carteira"])
    n = len(payload["pastas"]["pasta"])
    assert all(len(v) == n for v in payload["pastas"].values())


def test_publicacoes_apontam_para_fotos(payload):
    p = {x["agora"]: x for x in payload["publicacoes"]}
    assert payload["fotos"][p["13:05"]["foto"]]["origem"] == "oficial"
    assert p["07:05"]["base"] == p["07:05"]["foto"]


def test_payload_sem_nan_e_json_estrito(payload):
    json.dumps(payload, allow_nan=False)


def test_html_escapa_fechamento_de_script(tmp_path, payload):
    pl = json.loads(json.dumps(payload))
    pl["dic"]["comarca"][0] = "</script>x"
    montar_html(pl, tmp_path / "i.html")
    html = (tmp_path / "i.html").read_text("utf-8")
    assert "</script>x" not in html and "<\\/script>x" in html


def test_tamanho_do_html_abaixo_de_3mb(tmp_path, payload):
    montar_html(payload, tmp_path / "i.html")
    assert (tmp_path / "i.html").stat().st_size < 3 * 1024 * 1024


def test_bd_recompoe_as_62_colunas(tmp_path, linha, payload):
    montar_bd(linha, payload, tmp_path / "bd.json")
    bd = json.loads((tmp_path / "bd.json").read_text("utf-8"))
    assert set(bd["colunas"]) | set(DINAMICAS_BD) == set(COLUNAS) and len(bd["colunas"]) + len(DINAMICAS_BD) == 62
    assert len(bd["valores"]) == len(bd["pastas"]) > 4000
    assert bd["todas"] == list(COLUNAS)


def test_html_tem_abas_filtros_e_agora(tmp_path, payload):
    montar_html(payload, tmp_path / "i.html")
    html = (tmp_path / "i.html").read_text("utf-8")
    for aba in ("oper", "gest", "padroes", "planilha"):
        assert f'data-aba="{aba}"' in html
    for h in ("07:05", "09:05", "11:05", "13:05", "15:05", "17:05"):
        assert f'data-agora="{h}"' in html
    for f in ("fUF", "fCarteira", "fDe", "fAte", "fAdv", "fEtapa", "fProduto"):
        assert f'id="{f}"' in html
    for t in ("midnight", "dark", "light"):
        assert f'data-tema="{t}"' in html
    assert 'src="vendor/chart.umd.min.js"' in html and "Agregar" in html
    assert 'src="vendor/leaflet.js"' in html and 'href="vendor/leaflet.css"' in html and 'id="pd-mapa"' in html


def test_chip_ligado_visivel_no_tema_claro(tmp_path, payload):
    # no tema claro a regra do chip (fundo branco) é mais específica que .chip.on: precisa da sua própria regra
    montar_html(payload, tmp_path / "i.html")
    assert 'body[data-theme="light"] .chip.on{' in (tmp_path / "i.html").read_text("utf-8")


def decodificar_placas(pl: dict, k: int) -> dict[int, list]:
    estado: dict[int, list] = {}
    for j in range(k + 1):
        e = pl["placas"]["cargas"][j]["estado"]
        if isinstance(e, list):
            estado = {r[0]: r for r in e}
        else:
            for i in e["sai"]:
                estado.pop(i)
            for r in e["muda"]:
                estado[r[0]] = r
    return estado


def test_placas_delta_reconstroi(payload, cargas):
    pl = payload["placas"]
    idx = {p: i for i, p in enumerate(payload["pastas"]["pasta"])}
    loc, pp = pl["dic"]["local"], pl["dic"]["principal"]
    assert [c["agora"] for c in pl["cargas"]] == ["07:05", "09:05", "11:05", "13:05", "15:05", "17:05"]
    assert pl["cargas"][4]["falhou"] and pl["cargas"][4]["estado"] == {"sai": [], "muda": []}
    for k, c in enumerate(cargas):
        dec = decodificar_placas(payload, k)
        esp = {idx[p]: v["resumo"] for p, v in c["pastas"].items() if p in idx}
        assert set(dec) == set(esp) and len(dec) > 1000
        for i, r in esp.items():
            _, ult, l, n, n7, n30, est, dias, p, pj, ppp = dec[i]
            assert (pj, ppp) == (r["passagens_janela"], r["passagens_principal"])
            assert ult == int((r["ult"] - HOJE).total_seconds() // 60)
            assert tuple(loc[l]) == r["loc"] and (n, n7, n30, dias) == (r["n"], r["n7"], r["n30"], r["dias"])
            assert ESTADOS[est] == r["estado"] and (pp[p] if p is not None else None) == r["principal"]


def test_placas_json_sem_nan(tmp_path, payload, cargas, sim):
    from src.padroes import bancos_por_pasta
    montar_placas(cargas, bancos_por_pasta(sim), payload, tmp_path / "placas.json")
    d = json.loads((tmp_path / "placas.json").read_text("utf-8"), parse_constant=lambda c: 1 / 0)
    n = len(payload["pastas"]["pasta"])
    assert len(d["cargas"]) == 6 and all(0 <= int(i) < n for i in d["cargas"][0])
    assert all(0 <= int(i) < n for i in d["banco"]) and len(d["banco"]) > 4000
    um = next(iter(d["cargas"][0].values()))
    assert {"ultima", "pontos", "sequencia", "area", "semana", "horas", "ultimas", "perto_de_casa"} <= set(um)
    assert (tmp_path / "placas.json").stat().st_size < 2.5 * 1024 * 1024


def test_placas_json_tem_trajetos(tmp_path, payload, cargas, sim):
    from src.padroes import bancos_por_pasta
    montar_placas(cargas, bancos_por_pasta(sim), payload, tmp_path / "placas.json")
    d = json.loads((tmp_path / "placas.json").read_text("utf-8"))
    ult = cargas[-1]["pastas"]
    idx = {p: i for i, p in enumerate(payload["pastas"]["pasta"])}
    com = [v for v in d["cargas"][0].values() if v["trajetos"]]
    assert len(com) > 100
    for v in com:
        assert all(len(t) == 8 and 0 <= t[0] < len(v["pontos"]) and 0 <= t[1] < len(v["pontos"]) and t[0] != t[1]
                   for t in v["trajetos"])
    esp = ult["7012366"]["detalhe"]["trajetos"]
    pasta = _detalhe_em(d, idx["7012366"])
    assert pasta["trajetos"] == [[t["de"], t["para"], t["dias"], t["passagens"], t["minutos"], t["faixa"], t["km"],
                                  int(t["recorrente"])] for t in esp]
    assert (tmp_path / "placas.json").stat().st_size < 2.8 * 1024 * 1024


def _detalhe_em(d: dict, i: int) -> dict:
    """Detalhe da pasta i na última carga do placas.json (aplica os deltas)."""
    det = {}
    for c in d["cargas"]:
        if "sai" in c:
            for k in c["sai"]:
                det.pop(str(k), None)
            det.update(c["muda"])
        else:
            det = dict(c)
    return det[str(i)]


def test_payload_sem_placas_igual_fase1(linha, payload):
    base = montar_payload(linha)
    assert "placas" not in base and "placa" not in base["pastas"]
    com = json.loads(json.dumps({k: v for k, v in payload.items() if not k.startswith("_")}))   # caches da referência
    com.pop("placas"), com["pastas"].pop("placa")
    assert com == json.loads(json.dumps(base))


def test_placa_das_pastas(payload):
    pl = payload["pastas"]["placa"]
    assert len(pl) == len(payload["pastas"]["pasta"]) and any(p is None for p in pl)
    assert all(p is None or (len(p) == 7 and p.startswith("ZZ")) for p in pl)


def test_html_abaixo_de_1mb(tmp_path, payload):
    montar_html(payload, tmp_path / "i.html")
    assert (tmp_path / "i.html").stat().st_size < 1.0 * 1024 * 1024


@pytest.fixture(scope="module")
def html_gerado(tmp_path_factory, payload):
    saida = tmp_path_factory.mktemp("html") / "i.html"
    montar_html(payload, saida)
    return saida.read_text(encoding="utf-8")


def test_tres_tabelas_na_operacao(html_gerado):
    oper = html_gerado.split('<section id="v-oper"')[1].split("</section>")[0]
    for card in ("produtivos", "follow", "diligencia"):
        assert f'data-card="{card}"' in oper
    plan = html_gerado.split('<section id="v-planilha"')[1].split("</section>")[0]
    assert 'id="ba-raiz"' in plan and "c-produtivos" not in plan


def test_index_html_nao_inclui_ba(html_gerado):
    assert "base_minutos\":" not in html_gerado and "\"colunas_passagem\"" not in html_gerado   # o ba.json só é baixado ao abrir a aba


def test_ba_js_sob_demanda(html_gerado):
    """O código da aba Busca e Apreensão vem com o ba.json, só quando a aba abre (o HTML fica abaixo de 1 MB)."""
    assert "function linhaTempo(" not in html_gerado and "/*__BA__*/" not in html_gerado and '"ba.js"' in html_gerado


def test_docs_ba_js_em_dia():
    raiz = Path(__file__).resolve().parent.parent
    lf = lambda b: b.replace(b"\r\n", b"\n")
    assert lf((raiz / "docs" / "ba.js").read_bytes()) == lf((raiz / "src" / "ba.js").read_bytes())


def test_aba_ba_marcacao(html_gerado):
    for i in ("ba-frescor", "ba-aviso", "ba-segmentacoes", "ba-indice", "ba-gaveta", *[f"ba-sec-{s}" for s in (
            "localizados", "visao-localizados", "mandados", "apreendidos", "visao-apreendidos", "comp-analista", "meta-banco",
            "meta-relogio", "meta-analista", "meta-relogio-analista", "localizador", "linha-tempo")]):
        assert f'id="{i}"' in html_gerado, i
    assert "VLR PERFORMANCE" in html_gerado and "PERFORMACE" not in html_gerado
    assert "dados do sistema jurídico de" in html_gerado


def test_aba_padroes_trajetos_marcacao(html_gerado):
    pad = html_gerado.split('<section id="v-padroes"')[1].split("</section>")[0]
    for i in ("pd-tela-cheia", "pd-legenda", "pd-csv"):
        assert f'id="{i}"' in pad, i
    assert "pd-trajetos" in html_gerado and "Trajetos observados" in html_gerado
    assert "Liga as câmeras: não é o caminho pelas ruas." in html_gerado
    assert "#22d3ee" in html_gerado and "#c084fc" in html_gerado and "#a3e635" in html_gerado
    assert "Ainda sem dois pontos repetidos" not in html_gerado
    assert "prefers-reduced-motion" in html_gerado and "grayscale(" in html_gerado


def test_placas_json_tem_apreendidos(tmp_path, payload, cargas, sim):
    from src.padroes import ESTADOS, apreendidos_da_simulacao, bancos_por_pasta
    ap = apreendidos_da_simulacao(sim)
    montar_placas(cargas, bancos_por_pasta(sim), payload, tmp_path / "placas.json", ap)
    itens = json.loads((tmp_path / "placas.json").read_text("utf-8"))["apreendidos"]
    assert len(itens) == ap["total"] and all(len(x) == 15 for x in itens)
    na = [x for x in itens if ESTADOS[x[3]] in ("PADRAO_OBSERVADO", "PADRAO_EM_FORMACAO", "APRENDENDO")]
    assert len(na) == ap["na_janela"] and all(x[10] is not None and x[9] >= 0 for x in na)
    assert (tmp_path / "placas.json").stat().st_size < 2.8 * 1024 * 1024


def test_card_apreendidos_marcacao(html_gerado):
    assert 'id="pd-apreendidos"' in html_gerado and "Apreendidos com captura antes" in html_gerado
    assert "Só os filtros de UF e advogado valem aqui." in html_gerado
    assert "Nenhuma apreensão com captura da placa nos 60 dias antes, nos filtros de UF e advogado." in html_gerado



def _funcao(html: str, nome: str) -> str:
    ini = html.index(f"function {nome}(")
    return html[ini: html.index("\nfunction ", ini + 10)]


def test_card_apreendidos_sem_placas_json_nao_reentra(html_gerado):
    # placas.json indisponível (arquivo local) ou sem a chave: avisa e para, sem pedir de novo em laço
    f = _funcao(html_gerado, "renderApreendidos")
    assert "PL === undefined" in f and "Apreensões indisponíveis" in f
    assert "if (!ap) return" in _funcao(html_gerado, "csvPadroesPd").replace("ap = apreendidosPd(); ", "")


def test_trocar_de_aba_sai_da_tela_cheia(html_gerado):
    assert "telaCheiaPd(false)" in _funcao(html_gerado, "aplicarAba")


def test_trajeto_destacado_zera_ao_trocar_a_carga(html_gerado):
    assert "PD.trajK" in _funcao(html_gerado, "renderPadroes")
