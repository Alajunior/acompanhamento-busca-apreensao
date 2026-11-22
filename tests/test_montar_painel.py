import json

import pandas as pd
import pytest

from dados.gerar import HOJE, simular
from src.montar_painel import DINAMICAS_BD, montar_bd, montar_html, montar_payload
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
