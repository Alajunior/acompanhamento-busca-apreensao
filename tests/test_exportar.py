"""Exportação (src/exportar.js, rodando no Node): CSV por card e as abas do .xlsx."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src import referencia
from src.regra import COLUNAS

RAIZ = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node não instalado")


@pytest.fixture
def node(tmp_path):
    def chamar(fn, *args):
        arq = tmp_path / "chamada.json"
        arq.write_text(json.dumps({"fn": fn, "args": list(args)}), encoding="utf-8")
        r = subprocess.run(["node", str(RAIZ / "tests" / "rodar_exportar.mjs"), str(arq)], capture_output=True, text=True,
                           encoding="utf-8", check=True)
        return json.loads(r.stdout)
    return chamar


def test_csv_escapa(node):
    out = node("csv", ["A", "B"], [["x;y", 1.5], ['diz "oi"', None], ["linha\nnova", 2]])
    assert out == '﻿A;B\r\n"x;y";1,5\r\n"diz ""oi""";\r\n"linha\nnova";2\r\n'


CABECALHOS = {
    "escada": ["Tentativa", "REQUERIDO", "EXPEDIDO", "NEGATIVO", "Total", "Chegou %"],
    "prazos": ["Etapa", "vencidos", "hoje", "7 dias", "depois", "sem data"],
    "uf": ["UF", "Processos", "Risco", "Mandado negativo"],
    "movimentacao": ["De", "Para", "Processos"],
    "risco_etapa": ["Etapa", "Processos", "Risco", "Valor do bem"],
    "risco_uf": ["UF", "Processos", "Risco", "Valor do bem"],
    "comarcas": ["Comarca", "UF", "Processos", "% negativo"],
    "perfil": ["Grupo", "Item", "Processos", "% do total"],
    "produtivos": ["Agendamento", "Quantidade", "%"],
    "follow": ["Fase", "Quantidade", "%"],
    "diligencia": ["Diligência", "Quantidade", "%"],
}


def test_cabecalhos_dos_cards(node, payload):
    R = referencia.tudo(payload, "17:05", {"uf": ["SP"]})
    for chave, cab in CABECALHOS.items():
        out = node("csvDoCard", chave, R, payload["hoje"])
        primeira = out["texto"].lstrip("﻿").split("\r\n")[0]
        assert primeira == ";".join(cab), chave
        assert out["nome"] == (f"uf_sem_filtro_uf_{payload['hoje']}.csv" if chave == "uf" else f"{chave}_{payload['hoje']}.csv")
    adv = node("csvDoCard", "advogados", R, payload["hoje"])["texto"].lstrip("﻿").split("\r\n")[0].split(";")
    assert adv[:5] == ["Advogado", "Processos", "Vencidos", "Hoje", "Risco"] and adv[-4:] == ["% vencidos", "Processos / mediana", "Carga alta", "Vencidos alto"]
    evo = node("csvDoCard", "evolucao", R, payload["hoje"])["texto"].lstrip("﻿").split("\r\n")
    assert evo[0].split(";")[:3] == ["Dia", "Lacuna (sim/nao)", "Total"] and len(evo[0].split(";")) == 9


def test_planilhas_abas_e_regioes_so_com_uf(node, payload):
    pub = next(p for p in payload["publicacoes"] if p["agora"] == "17:05")
    bd = {"colunas": [c for c in COLUNAS if c not in ("TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "FASE", "DATA_INSERT")],
          "todas": list(COLUNAS), "pastas": [], "valores": []}
    sem_uf = node("planilhas", referencia.tudo(payload, "17:05", {}), [], bd, {}, pub, payload["fotos"][pub["foto"]], payload["hoje"])
    assert list(sem_uf) == ["BD", "Resumo", "Prazos", "Advogados", "Movimentacao", "Filtros"]
    assert sem_uf["BD"][0] == list(COLUNAS)
    assert sem_uf["Resumo"][0] == ["Indicador", "Valor"] and ["Agendamento", "Quantidade", "%"] in sem_uf["Resumo"]
    assert ["UF", "(todos)"] in sem_uf["Filtros"] and ["Agendamento de", "(sem limite)"] in sem_uf["Filtros"]
    com_uf = node("planilhas", referencia.tudo(payload, "17:05", {"uf": ["SP", "RJ"]}), [], bd, {"uf": ["SP", "RJ"]}, pub,
                  payload["fotos"][pub["foto"]], payload["hoje"])
    assert "Regioes" in com_uf and com_uf["Regioes"][0] == ["Indicador", "RJ", "SP", "Brasil"]


def test_planilha_bd_sem_base_avisa(node, payload):
    pub = next(p for p in payload["publicacoes"] if p["agora"] == "17:05")
    out = node("planilhas", referencia.tudo(payload, "17:05", {}), [], None, {}, pub, payload["fotos"][pub["foto"]], payload["hoje"])
    assert "indisponível" in out["BD"][0][0]


def test_csv_localizacao(node, payload):
    R = referencia.tudo(payload, "17:05", {})
    out = node("csvDoCard", "localizacao", R, payload["hoje"])
    linhas = out["texto"].lstrip("﻿").rstrip("\r\n").split("\r\n")
    assert linhas[0] == "Etapa;24 horas;7 dias;30 dias;Sugestão"
    assert len(linhas) == 8 and linhas[1].startswith("MANDADO EXPEDIDO;")
    L = R["localizado"]
    assert linhas[-1] == f"Total (todas as etapas);{L['j24']};{L['j7']};{L['j30']};"
    assert out["nome"] == f"localizacao_{payload['hoje']}.csv"


def test_regioes_com_localizados(node, payload):
    R = referencia.tudo(payload, "17:05", {"uf": ["SP"]})
    pub = next(p for p in payload["publicacoes"] if p["agora"] == "17:05")
    out = node("planilhas", R, [], None, {"uf": ["SP"]}, pub, payload["fotos"][pub["foto"]], payload["hoje"])
    rot = [l[0] for l in out["Regioes"]]
    i = rot.index("Veículos localizados 30 dias")
    assert rot[i + 1] == "% da carteira localizada (30 dias)" and rot[i + 2] == "Advogados"
    assert out["Regioes"][i][1:] == [R["regioes"]["ufs"][0]["localizados"]["d30"], R["regioes"]["brasil"]["localizados"]["d30"]]
