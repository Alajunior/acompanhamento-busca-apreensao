"""Paridade da aba Busca e Apreensão: src/ba.js (no Node) contra src/referencia_ba.py, seção a seção."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from src import referencia_ba as ref
from tests.test_paridade import diferencas

RAIZ = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node não instalado")


def rodar(ba: dict, casos: list, tmp_path: Path) -> list:
    (tmp_path / "ba.json").write_text(json.dumps(ba, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps(casos, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(RAIZ / "tests" / "rodar_ba.mjs"), str(tmp_path / "ba.json"), str(tmp_path / "c.json")],
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


def casos(ba: dict) -> list:
    o = ba["opcoes"]
    fixos = [("17:05", {}), ("07:05", {}), ("09:05", {}), ("11:05", {}), ("13:05", {}), ("15:05", {}),
             ("17:05", {"adv": o["advogados"][:2]}), ("17:05", {"fase": ["JUDICIAL 1", "ATÉ 120"]}),
             ("17:05", {"uf": ["SP", "MG"]}), ("17:05", {"mes": "10/2026"}),
             ("17:05", {"mes": "10/2026", "etapa": ["Apreendido", "Localizado (diligência)"]}),
             ("17:05", {"etapa": ["Mandado expedido"]}), ("17:05", {"mes": "12/2026"}), ("17:05", {"mes": "1/2026"}),
             ("17:05", {"adv": ["ADV-01"], "uf": ["AC"]}),
             ("17:05", {"localizador": [o["localizadores"][0], o["localizadores"][5], "(sem localizador)"]})]
    rng = random.Random(1)
    for _ in range(30):
        f = {}
        for g, lista in (("adv", o["advogados"]), ("fase", o["fases"]), ("uf", o["ufs"]), ("localizador", o["localizadores"])):
            if rng.random() < 0.3:
                f[g] = rng.sample(lista, k=rng.randint(1, min(3, len(lista))))
        if rng.random() < 0.4:
            f["mes"] = rng.choice(o["meses"])
        if rng.random() < 0.3:
            f["etapa"] = rng.sample(o["etapas"], k=rng.randint(1, 2))
        fixos.append((rng.choice(ba["agoras"]), f))
    return fixos


def test_paridade_secoes(ba_json, tmp_path):
    cs = casos(ba_json)
    js = rodar(ba_json, [["secoes", a, f] for a, f in cs], tmp_path)
    for (agora, f), res in zip(cs, js):
        d = diferencas(res, ref.secoes(ba_json, agora, f))
        assert not d, f"{agora} {f}: " + "; ".join(d[:5])


def test_paridade_linha_tempo(ba_json, tmp_path):
    cs = [(a, f, j) for j in ("30", "90", "180", "tudo") for a, f in
          (("17:05", {}), ("07:05", {"etapa": ["Apreendido"]}), ("17:05", {"adv": ["ADV-03"], "etapa": ["Mandado expedido", "Localização encerrada sem apreensão"]}))]
    js = rodar(ba_json, [["linha_tempo", a, f, j] for a, f, j in cs], tmp_path)
    for (agora, f, j), res in zip(cs, js):
        d = diferencas(res, ref.linha_tempo(ba_json, agora, f, j))
        assert not d, f"{agora} {f} {j}: " + "; ".join(d[:5])


def test_arredondamento_nao_devolve_zero_negativo():
    js = "const B=require('./src/ba.js');console.log(JSON.stringify([Object.is(B.arred(-0.3),-0),Object.is(B.arred(-0.04,1),-0),Object.is(B.arredCima(-0,0),-0)]))"
    r = subprocess.run(["node", "-e", js], cwd=RAIZ, capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == [False, False, False]      # "-0" na tela e pintado de verde
