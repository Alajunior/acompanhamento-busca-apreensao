"""Paridade: as agregações do painel (src/agregar.js, rodando no Node) contra a referência em Python."""
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from dados.gerar import simular
from src import referencia
from src.montar_painel import montar_payload
from src.publicacao import linha_do_tempo
from tests.construtores import pasta, um_dia

RAIZ = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node não instalado")

CASOS_FIXOS = [("17:05", {}), ("07:05", {}), ("11:05", {}), ("13:05", {}), ("17:05", {"uf": ["SP"]}),
               ("17:05", {"uf": ["SP", "RJ", "MG"]}), ("17:05", {"uf": ["SP", "RJ", "MG", "BA", "PR", "RS"]}),
               ("17:05", {"uf": ["AC"], "adv": ["ADV-01"]}),
               ("09:05", {"de": "2026-11-20", "ate": "2026-12-03", "etapa": ["AGUARDANDO LIMINAR", "MANDADO EXPEDIDO"]}),
               ("15:05", {}), ("15:05", {"uf": ["AM"]}), ("07:05", {"uf": ["SP", "RJ"]})]


def casos_sorteados(pl: dict, n: int = 40, seed: int = 1) -> list:
    rng = random.Random(seed)
    agoras = [p["agora"] for p in pl["publicacoes"]]
    out = []
    for _ in range(n):
        f = {}
        for g in ("uf", "carteira", "adv", "produto"):
            if rng.random() < 0.35:
                f[g] = rng.sample(pl["dic"][g], k=rng.randint(1, min(3, len(pl["dic"][g]))))
        if rng.random() < 0.3:
            f["etapa"] = rng.sample(pl["ordens"]["processual"], k=rng.randint(1, 3))
        if rng.random() < 0.3:
            f["de"] = rng.choice(["2026-11-01", "2026-11-20", "2026-11-26", None])
            f["ate"] = rng.choice(["2026-11-25", "2026-11-26", "2026-12-03", None])
        out.append((rng.choice(agoras), f))
    return out


def rodar_node(pl: dict, casos: list, tmp_path: Path, modo: str = "tudo") -> list:
    (tmp_path / "p.json").write_text(json.dumps(pl), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps(casos), encoding="utf-8")
    r = subprocess.run(["node", str(RAIZ / "tests" / "rodar_agregar.mjs"), str(tmp_path / "p.json"), str(tmp_path / "c.json"), modo],
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def diferencas(a, b, caminho="") -> list[str]:
    if isinstance(a, float) or isinstance(b, float):
        if a is None or b is None or not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
            return [f"{caminho}: js={a!r} py={b!r}"]
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{caminho}: chaves js={sorted(set(a) - set(b))} py={sorted(set(b) - set(a))}"]
        return [d for k in a for d in diferencas(a[k], b[k], f"{caminho}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{caminho}: tamanho js={len(a)} py={len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diferencas(x, y, f"{caminho}[{i}]")]
    return [] if a == b else [f"{caminho}: js={a!r} py={b!r}"]


def sem_cache(pl):
    return {k: v for k, v in pl.items() if not k.startswith("_")}


def test_paridade_lista_padroes_busca(payload, tmp_path):
    todos = list(payload["placas"]["estados"])
    placa = next(p for p in payload["pastas"]["placa"] if p)
    busca = (placa[:3] + "-" + placa[3:6]).lower()
    vazio = {"uf": ["AC"], "adv": ["ADV-01"], "produto": ["PESADOS"], "de": "2026-12-01", "ate": "2026-11-01"}
    casos = [("17:05", {}, list(referencia.ESTADOS_PADRAO), ""), ("17:05", {"uf": ["SP"]}, todos, ""),
             ("07:05", {}, todos, busca), ("15:05", {"etapa": ["MANDADO EXPEDIDO"]}, ["APRENDENDO"], ""),
             ("17:05", vazio, todos, "")]
    js = rodar_node(sem_cache(payload), casos, tmp_path, "lista")
    for caso, res in zip(casos, js):
        d = diferencas(res, referencia.lista_padroes(payload, *caso))
        assert not d, f"{caso[:2]}: " + "; ".join(d[:5])
    assert js[2] and all(busca.replace("-", "").upper() in (payload["pastas"]["placa"][x["i"]] or "") or
                         busca.replace("-", "").upper() in x["pasta"] for x in js[2])
    assert js[4] == []


def test_paridade_js_python(payload, tmp_path):
    casos = CASOS_FIXOS + casos_sorteados(payload)
    js = rodar_node(sem_cache(payload), casos, tmp_path)
    for (agora, f), res in zip(casos, js):
        d = diferencas(res, referencia.tudo(payload, agora, f))
        assert not d, f"{agora} {f}: " + "; ".join(d[:5])


def test_paridade_recorte_vazio(payload, tmp_path):
    caso = [("17:05", {"uf": ["AC"], "adv": ["ADV-01"], "produto": ["PESADOS"], "de": "2026-12-01", "ate": "2026-11-01"})]
    res = rodar_node(sem_cache(payload), caso, tmp_path)[0]
    assert res["kpis"]["atual"]["processos"] == 0 and res["escada"] is None and res["destaques"] == []
    assert "NaN" not in json.dumps(res) and not diferencas(res, referencia.tudo(payload, *caso[0]))


def test_paridade_formatos(tmp_path):
    rows = [pasta(f"l{i}", "LIMINAR DEFERIDA", -1, risco=r) for i, r in enumerate([1_249_999.0, 1_250_000.0, 500.5, 999.4])]
    pl = um_dia(rows)
    js = rodar_node(pl, [("17:05", {})], tmp_path)[0]
    assert js["destaques"] == referencia.tudo(pl, "17:05", {})["destaques"]


def test_paridade_placas_bordas(tmp_path):
    from tests.construtores import placas_min
    ag = 17 * 60 + 5
    rows = [pasta(x, "1º MANDADO EXPEDIDO", uf="SP") for x in "abcde"]
    cap = lambda ult, loc: [ult, loc, 2, 1, 1, "APRENDENDO", 2, None]  # noqa: E731
    pl = placas_min(um_dia(rows), {"a": cap(ag - 1440, ("X", "RJ", None)), "b": cap(ag - 1441, ("X", "SP", "B")),
                                   "c": cap(ag - 10080, (None, None, None)), "d": cap(ag - 43200, ("Y", "SP", None))},
                    {"e": None})
    js = rodar_node(pl, [("17:05", {}), ("17:05", {"uf": ["SP"]})], tmp_path)
    for f, res in zip(({}, {"uf": ["SP"]}), js):
        assert not diferencas(res, referencia.tudo(pl, "17:05", f))
    assert (js[0]["localizado"]["j24"], js[0]["localizado"]["j7"], js[0]["localizado"]["j30"]) == (1, 3, 4)
    sed = js[0]["localizado"]
    assert sed["estados"]["SEM_PLACA"] == 1 and sed["fora_uf"] == 1
