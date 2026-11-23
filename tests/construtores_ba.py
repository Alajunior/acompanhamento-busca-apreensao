"""Fábrica de fontes mínimas da aba Busca e Apreensão para testes de regra."""
import pandas as pd

from dados.ba import FontesBA
from src.ba_calendario import FERIADOS_2026

T = pd.Timestamp


def tarefa(pasta: str, nome: str, ini: str, fim: str | None = None, status: str | None = None, adv: str = "ADV-01",
           memo: str | None = None, cliente: str = "CLIENTE 000001") -> dict:
    return {"PASTA": pasta, "TAREFA": nome, "DATA_INICIO": T(ini), "DATA_CONCLUSAO": T(fim) if fim else pd.NaT,
            "STATUS_FINAL": status, "RESPONSAVEL": adv, "ADV_OPERACIONAL": adv,
            "LOGIN_OPERACIONAL": adv.replace("ADV-", "adv"), "UF": "SP", "COMARCA": "CAMPINAS",
            "PARTE_CONTRARIA": cliente, "MEMO": memo}


def campo(pasta: str, nome: str, valor: str, quando: str) -> dict:
    return {"PASTA": pasta, "TAREFA": "BEM APREENDIDO", "CAMPO": nome, "VALOR": valor, "DATA_CADASTRO": T(quando)}


def fontes(tarefas: list[dict], campos: list[dict] = (), atraso: dict | None = None, bem: dict | None = None,
           acoes: list[tuple] = (), fichas: list[dict] = ()) -> FontesBA:
    t = pd.DataFrame(tarefas)
    t.insert(1, "ID_TAREFA", range(1, len(t) + 1))
    c = pd.DataFrame(list(campos), columns=["PASTA", "TAREFA", "CAMPO", "VALOR", "DATA_CADASTRO"])
    c.insert(1, "ID_TAREFA", 0)
    pastas = sorted(set(t["PASTA"].str.strip()))
    atraso = atraso or {}
    bem = bem or {}
    fase = pd.DataFrame({"CONTRATO": pastas, "DIA_REF": T("2026-11-26"), "DIAS_ATRASO_REF": [atraso.get(p, 400) for p in pastas]})
    est = pd.DataFrame({"CONTRATO": pastas, "VALOR_RISCO_CONTRATO": 50_000.0, "VALOR_DO_BEM": [bem.get(p, 40_000.0) for p in pastas]})
    a = pd.DataFrame(list(acoes), columns=["PASTA", "LOGIN", "DIA", "ALTERACOES"])
    f = pd.DataFrame(list(fichas), columns=["PASTA", "ID_TAREFA", "DATA_INICIO", "DATA_CONCLUSAO", "STATUS_FINAL", "LOCALIZADOR",
                                            "UF", "COMARCA", "ADV_OPERACIONAL"])
    vazio = pd.DataFrame(columns=["MES", "CHAVE", "QTD", "VALOR"])
    return FontesBA(t, c, a, fase, f, est, vazio, vazio, FERIADOS_2026)


def ficha(pasta: str, localizador: str, envio: str, ident: int = 1) -> dict:
    return {"PASTA": pasta, "ID_TAREFA": ident, "DATA_INICIO": T(envio), "DATA_CONCLUSAO": T(envio) + pd.Timedelta(hours=2),
            "STATUS_FINAL": "ENVIADO", "LOCALIZADOR": localizador, "UF": "SP", "COMARCA": "CAMPINAS", "ADV_OPERACIONAL": "ADV-01"}
