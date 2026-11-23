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


# ---------- abas das placas ----------
COLS_LOC = ["Pasta", "Processo", "Etapa", "Tipo de agendamento", "UF do processo", "Advogado", "Placa", "Marca/modelo",
            "Capturas (total)", "Capturas 7 dias", "Capturas 30 dias", "Última captura", "Horas desde a última", "Rua", "Número",
            "Bairro", "Cidade", "UF da captura", "CEP", "Latitude", "Longitude", "Fora da UF do processo",
            "Empresa do monitoramento", "Link da foto", "storage_path"]
COLS_PAD = ["Pasta", "Placa", "Etapa", "Estado", "Dias no ponto principal", "Passagens no ponto principal", "Passagens na janela",
            "Costuma aparecer",
            "Rua", "Número", "Bairro", "Cidade", "UF", "CEP", "Última passagem", "Perto de casa (CEP)", "Área das capturas (km)",
            "Endereço do banco"]


@pytest.fixture(scope="module")
def placas_json(tmp_path_factory, payload, cargas, sim):
    from src.montar_painel import montar_placas
    from src.padroes import bancos_por_pasta
    arq = tmp_path_factory.mktemp("pl") / "placas.json"
    montar_placas(cargas, bancos_por_pasta(sim), payload, arq)
    return json.loads(arq.read_text("utf-8"))


def pacote_placas(payload, pj, agora, filtros, rows):
    k = [c["agora"] for c in payload["placas"]["cargas"]].index(agora)
    det = {}
    for c in pj["cargas"][: k + 1]:
        if "sai" in c:
            for i in c["sai"]:
                det.pop(str(i), None)
            det.update(c["muda"])
        else:
            det = dict(c)
    est = referencia.placas_estado(payload, k)
    ids = {r["i"] for r in rows}
    return {"agora_min": referencia._minutos(agora), "acao": payload["ordens"]["acao"], "rotulos": payload["placas"]["rotulos"],
            "local": payload["placas"]["dic"]["local"], "enderecos": pj["enderecos"],
            "banco": {i: b for i, b in pj["banco"].items() if int(i) in ids},
            "resumo": {str(i): v for i, v in est.items() if i in ids}, "detalhe": {i: v for i, v in det.items() if int(i) in ids},
            "lista": referencia.lista_padroes(payload, agora, filtros, list(payload["placas"]["estados"]), ""),
            "placa": payload["pastas"]["placa"]}


def _chamar_planilhas(node, payload, filtros, placas, agora="17:05"):
    pub = next(p for p in payload["publicacoes"] if p["agora"] == agora)
    rows = referencia.filtrar(referencia.linhas(payload, pub["foto"]), filtros, payload)
    R = referencia.tudo(payload, agora, filtros)
    pk = placas(rows) if callable(placas) else placas
    return node("planilhas", R, rows, None, filtros, pub, payload["fotos"][pub["foto"]], payload["hoje"], pk), rows


def test_localizados_colunas_e_ordem(node, payload, placas_json):
    f = {"uf": ["AM", "PA"]}
    out, rows = _chamar_planilhas(node, payload, f, lambda rows: pacote_placas(payload, placas_json, "17:05", f, rows))
    loc = out["Localizados"]
    assert loc[0] == COLS_LOC
    est = referencia.placas_estado(payload, 5)
    assert len(loc) - 1 == sum(r["i"] in est for r in rows) > 10
    ordem = {e: n for n, e in enumerate(payload["ordens"]["acao"])}
    chaves = [(ordem.get(l[2], 99), l[11]) for l in loc[1:]]
    assert [c[0] for c in chaves] == sorted(c[0] for c in chaves)
    for (a, qa), (b, qb) in zip(chaves, chaves[1:]):
        assert a < b or qa >= qb                      # dentro da etapa, última captura mais recente primeiro
    assert all(l[23] in ("", None) for l in loc[1:]) and {l[21] for l in loc[1:]} <= {"sim", "nao"}
    assert all(str(l[22]).startswith("CAMERAS ") for l in loc[1:])


def test_padroes_todos_os_estados(node, payload, placas_json):
    f = {"uf": ["SP"], "carteira": ["FROTAS 1"]}
    out, rows = _chamar_planilhas(node, payload, f, lambda rows: pacote_placas(payload, placas_json, "17:05", f, rows))
    pad = out["Padroes"]
    assert pad[0] == COLS_PAD and len(pad) - 1 == len(rows)
    estados = {l[3] for l in pad[1:]}
    assert {"Sem captura", "Padrão observado"} <= estados
    assert {l[COLS_PAD.index("Perto de casa (CEP)")] for l in pad[1:]} <= {"sim", "nao"}
    assert list(out)[:7] == ["BD", "Resumo", "Prazos", "Advogados", "Movimentacao", "Localizados", "Padroes"]


def test_exportar_padroes_passagens(node, payload, placas_json):
    f = {"uf": ["SP"]}
    out, rows = _chamar_planilhas(node, payload, f, lambda rows: pacote_placas(payload, placas_json, "17:05", f, rows))
    lista = {x["pasta"]: x for x in referencia.lista_padroes(payload, "17:05", f, list(payload["placas"]["estados"]), "")}
    j = COLS_PAD.index("Passagens na janela")
    com = [l for l in out["Padroes"][1:] if l[j] is not None]
    assert len(com) > 50 and all(l[j] == lista[l[0]]["passagens"] and l[j] >= (l[5] or 0) for l in com)


def test_sem_placas_sem_abas(node, payload):
    out, _ = _chamar_planilhas(node, payload, {}, None)
    assert "Localizados" not in out and "Padroes" not in out


def test_placas_indisponiveis_avisa(node, payload):
    out, _ = _chamar_planilhas(node, payload, {}, {"indisponivel": True})
    assert "indisponível" in out["Localizados"][0][0] and "indisponível" in out["Padroes"][0][0]


COLS_CSV_PAD = ["Pasta", "Placa", "Etapa", "Estado", "Dias no ponto principal", "Passagens no ponto principal",
                "Passagens na janela (60 dias)", "Rua", "Número", "Bairro", "Cidade", "UF", "CEP", "Costuma aparecer",
                "Última passagem", "Perto de casa (CEP)", "Área das capturas (km)"]


def test_csv_da_aba_padroes(node, payload, placas_json):
    f = {"uf": ["SP"]}
    pub = next(p for p in payload["publicacoes"] if p["agora"] == "17:05")
    rows = referencia.filtrar(referencia.linhas(payload, pub["foto"]), f, payload)
    out = node("csvPadroes", pacote_placas(payload, placas_json, "17:05", f, rows), payload["hoje"])
    linhas = out["texto"].lstrip("﻿").rstrip("\r\n").split("\r\n")
    assert out["nome"] == f"padroes_placa_{payload['hoje']}.csv"
    assert linhas[0].split(";") == COLS_CSV_PAD
    assert len(linhas) - 1 == len(referencia.lista_padroes(payload, "17:05", f, list(payload["placas"]["estados"]), ""))
