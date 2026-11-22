import json

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
    for aba in ("oper", "gest", "planilha"):
        assert f'data-aba="{aba}"' in html
    for h in ("07:05", "09:05", "11:05", "13:05", "15:05", "17:05"):
        assert f'data-agora="{h}"' in html
    for f in ("fUF", "fCarteira", "fDe", "fAte", "fAdv", "fEtapa", "fProduto"):
        assert f'id="{f}"' in html
    for t in ("midnight", "dark", "light"):
        assert f'data-tema="{t}"' in html
    assert 'src="vendor/chart.umd.min.js"' in html and "Agregar" in html


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
            _, ult, l, n, n7, n30, est, dias, p = dec[i]
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


def test_payload_sem_placas_igual_fase1(linha, payload):
    base = montar_payload(linha)
    assert "placas" not in base and "placa" not in base["pastas"]
    com = json.loads(json.dumps(payload))
    com.pop("placas"), com["pastas"].pop("placa")
    assert com == json.loads(json.dumps(base))


def test_placa_das_pastas(payload):
    pl = payload["pastas"]["placa"]
    assert len(pl) == len(payload["pastas"]["pasta"]) and any(p is None for p in pl)
    assert all(p is None or (len(p) == 7 and p.startswith("ZZ")) for p in pl)


def test_html_abaixo_de_1mb(tmp_path, payload):
    montar_html(payload, tmp_path / "i.html")
    assert (tmp_path / "i.html").stat().st_size < 1.0 * 1024 * 1024
