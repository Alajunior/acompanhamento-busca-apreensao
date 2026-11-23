"""docs/ba.json: as cargas do dia em delta, os marcos, as passagens, as metas e as opções das segmentações."""
import json

import pandas as pd

from src.ba_regras import linhas_pasta, localizadores_de


def linhas_no_agora(ba: dict, k: int) -> dict[str, list]:
    estado: dict[str, list] = {}
    for c in ba["cargas"][:k + 1]:
        if "base" in c:
            estado = {r[0]: r for r in c["base"]}
        else:
            for p in c["sai"]:
                estado.pop(p)
            for r in c["muda"]:
                estado[r[0]] = r
    return estado


def _iso(v):
    return None if v is None or (not isinstance(v, str) and pd.isna(v)) else (v.isoformat() if hasattr(v, "isoformat") else v)


def test_delta_reconstroi_cada_agora(ba_json, ba_fontes):
    mapa, _ = localizadores_de(ba_fontes)
    for k in (0, 5):
        agora = ba_json["agoras"][k]
        direto = linhas_pasta(ba_fontes, pd.Timestamp(f"2026-11-26 {agora}"), mapa)
        estado = linhas_no_agora(ba_json, k)
        assert set(estado) == set(direto["PASTA"])
        col = ba_json["colunas"]
        for r in direto.sample(60, random_state=k).itertuples(index=False):
            esperado = [_iso(getattr(r, c)) for c in col]
            assert estado[r.PASTA] == json.loads(json.dumps(esperado)), r.PASTA


def test_1105_mantem_0905_com_aviso(ba_json):
    c = ba_json["cargas"]
    i = ba_json["agoras"].index("11:05")
    assert c[i]["sai"] == [] and c[i]["muda"] == [] and c[i]["quando"] == "2026-11-26T09:05"
    assert c[i]["aviso"] == "Leitura de 11:05 incompleta; mantida a de 09:05."
    assert linhas_no_agora(ba_json, i) == linhas_no_agora(ba_json, i - 1)


def test_opcoes_e_metas(ba_json):
    o = ba_json["opcoes"]
    assert o["localizadores"][-1] == "(sem localizador)" and o["meses"][0] == "11/2026"
    assert o["etapas"] == ["Apreendido", "Mandado expedido", "Localizado (diligência)", "Localização encerrada sem apreensão"]
    assert all(isinstance(x["grafias"], int) for x in o["localizadores_info"].values())
    assert {m[0] for m in ba_json["metas"]["faixa"]} >= {"11/2026"} and "12/2026" not in {m[0] for m in ba_json["metas"]["faixa"]}
    assert len(ba_json["feriados"]) == 14


def test_marcos_e_passagens(ba_json):
    lin = linhas_no_agora(ba_json, 5)
    assert set(ba_json["marcos"]) <= set(lin)
    pas = ba_json["passagens"]
    assert len(pas) == 6 and "base" in pas[0] and all("muda" in x and "sai" in x for x in pas[1:])
    assert ba_json["colunas_passagem"][0] == "LOCALIZADOR"


def test_tamanho(ba_json):
    assert len(json.dumps(ba_json, ensure_ascii=False, separators=(",", ":")).encode()) < 1_600_000


def test_json_estrito_sem_nan(ba_json):
    json.dumps(ba_json, allow_nan=False)
