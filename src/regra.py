"""A regra do painel: agenda de tarefas abertas + fontes → uma linha por pasta (62 colunas).

Réplica da procedure oficial, com a precedência do fluxo no mesmo dia:
1. sai a pasta inteira se alguma tarefa dela for BAIXADO;
2. ficam só os 21 tipos (comparação sem caixa e sem espaço à direita; a saída usa o nome canônico);
3. por pasta vence: o dia de agendamento mais recente → no dia, LIMINAR DEFERIDA > EMENDAR INICIAL > AGUARDANDO LIMINAR
   (só quando todas as tarefas daquele dia estão nesse trio) → a data-hora completa → o maior ID_AGENDA.
A procedure oficial escolhe ao acaso entre tarefas do mesmo dia; `desempate="acaso"` reproduz isso (a "tabela oficial").
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

_MANDADOS = [f"{k}º MANDADO {s}" for k in range(2, 6) for s in ("EXPEDIDO", "NEGATIVO", "REQUERIDO")]
TIPOS: tuple[str, ...] = ("1º MANDADO EXPEDIDO", "1º MANDADO NEGATIVO", *_MANDADOS,
                          "6º OU + MANDADO EXPEDIDO", "6º OU + MANDADO NEGATIVO", "6º OU + MANDADO REQUERIDO",
                          "AGUARDANDO LIMINAR", "EMENDA REALIZADA", "EMENDAR INICIAL", "LIMINAR DEFERIDA")
_CANONICO = {t.upper(): t for t in TIPOS}
ORDEM_PROCESSUAL = ("EMENDAR INICIAL", "AGUARDANDO LIMINAR", "LIMINAR DEFERIDA", "MANDADO REQUERIDO", "MANDADO EXPEDIDO",
                    "MANDADO NEGATIVO")
ORDEM_FOLLOW = ("AGUARDANDO LIMINAR", "MANDADO EXPEDIDO", "MANDADO NEGATIVO", "MANDADO REQUERIDO", "EMENDAR INICIAL",
                "EMENDA REALIZADA", "LIMINAR DEFERIDA")
ORDEM_ACAO = ("MANDADO EXPEDIDO", "MANDADO NEGATIVO", "LIMINAR DEFERIDA", "MANDADO REQUERIDO", "AGUARDANDO LIMINAR",
              "EMENDAR INICIAL")
EXTINTAS = ("EMENDA REALIZADA",)
_FASES = ("MANDADO EXPEDIDO", "MANDADO NEGATIVO", "MANDADO REQUERIDO", "EMENDA REALIZADA", "EMENDAR INICIAL",
          "LIMINAR DEFERIDA", "LIMINAR INDEFERIDA", "AGUARDANDO LIMINAR")
_TRIO = {"LIMINAR DEFERIDA": 2, "EMENDAR INICIAL": 1, "AGUARDANDO LIMINAR": 0}

COLUNAS: tuple[str, ...] = (
    "PASTA", "PROCESSO_UNICO", "NUMERO_PROCESSO", "VALOR_RISCO_CONTRATO", "PARTE_CONTRARIA", "COMARCA", "UF",
    "TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "STATUS_PROCESSO", "FASE", "ADVOGADO_OPERACIONAL", "VALOR_ORIGINAL",
    "AGENDADO_PARA", "ORDEM", "DESCRICAO_TIPO_ANDAMENTO", "MEMO", "CONTROLE_INTERNO", "RENAVAM", "MOTIVO_STATUS_FINAL",
    "RESPONSAVEL_ANDAMENTO_ORIGEM", "VARA", "FORO", "DIAS_ATRASO", "CHASSI", "MARCA", "MODELO", "ANO_FABRICACAO",
    "ANO_MODELO", "PLACA", "COR", "SITUACAO", "CARTEIRA_PRODUTO", "PRODUTO_VEICULO", "STATUS", "STATUS_2",
    "DIVISAO_FILIAL", "CPF", "CPF_PARTE_CONTRARIA", "DATA_CADASTRO_ANDAMENTO_SOMENTE_DATA",
    "DATA_CADASTRO_ANDAMENTO_SOMENTE_HORA", "ACAO", "DESCRICAO_FASE", "FASE_ESTOQUE", "CONTROLE_CLIENTE", "VALOR_CAUSA",
    "VALOR_DO_BEM", "STATUS_FINAL", "BASE_PRODUCAO", "ESTADO", "AGENDAMENTO_LOCALIZACAO", "IDCOB_CLIENTE",
    "IDCOB_CONTRATO", "CONTRATO", "DATA_ATUALIZACAO", "DATA_ENTRADA", "DATA_IMPORTACAO", "VALOR_CONTRATO",
    "VALOR_RISCO_CLIENTE", "DATA_DISTRIBUICAO", "DATA_INSERT", "RKG")
_SEMPRE_NULAS = ("AGENDADO_PARA", "ORDEM", "DESCRICAO_TIPO_ANDAMENTO", "MEMO", "CONTROLE_INTERNO", "RENAVAM",
                 "MOTIVO_STATUS_FINAL", "RESPONSAVEL_ANDAMENTO_ORIGEM", "AGENDAMENTO_LOCALIZACAO")
_ENTRADA = ("ID_AGENDA", "PASTA", "TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "PROCESSO_UNICO", "NUMERO_PROCESSO",
            "PARTE_CONTRARIA", "COMARCA", "UF", "ADVOGADO_OPERACIONAL", "VARA", "FORO", "STATUS", "DIVISAO_FILIAL", "ACAO",
            "CONTROLE_CLIENTE", "VALOR_CAUSA", "STATUS_FINAL", "ESTADO")
_ESPACO = re.compile(r"\s+")


def chave(x) -> str:
    """Chave de junção: sem nenhum espaço (inclusive NBSP), maiúsculas; float inteiro vira int."""
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return _ESPACO.sub("", str(x)).upper()


def fase_de(tipo: str) -> str:
    return next((f for f in _FASES if f in str(tipo)), "SEM INFO")


def _preparar(agenda: pd.DataFrame) -> pd.DataFrame:
    faltam = [c for c in _ENTRADA if c not in agenda.columns]
    if faltam:
        raise ValueError(f"agenda sem colunas obrigatórias: {faltam}")
    ag = agenda.copy()
    ag["_k"] = ag["PASTA"].map(chave)
    tipo = ag["TIPO_AGENDAMENTO"].astype(str).str.rstrip().str.upper()
    baixadas = set(ag.loc[tipo == "BAIXADO", "_k"])
    ag["TIPO_AGENDAMENTO"] = tipo.map(_CANONICO)
    ag = ag[ag["TIPO_AGENDAMENTO"].notna() & ~ag["_k"].isin(baixadas)].copy()
    ag["DATA_AGENDAMENTO"] = pd.to_datetime(ag["DATA_AGENDAMENTO"])
    ag["_dia"] = ag["DATA_AGENDAMENTO"].dt.normalize()
    return ag


def _no_dia_mais_recente(ag: pd.DataFrame) -> pd.DataFrame:
    ultimo = ag.groupby("_k")["_dia"].transform("max")
    return ag[ag["_dia"] == ultimo]


def pastas_com_empate(agenda: pd.DataFrame) -> set[str]:
    """Pastas (como na agenda, sem espaço à direita) com mais de um TIPO no dia mais recente."""
    ag = _no_dia_mais_recente(_preparar(agenda))
    n = ag.groupby("_k")["TIPO_AGENDAMENTO"].nunique()
    k = set(n.index[n > 1])
    return set(ag.loc[ag["_k"].isin(k), "PASTA"].astype(str).str.rstrip())


def montar_painel(agenda: pd.DataFrame, estoque: pd.DataFrame, garantia: pd.DataFrame, veiculo: pd.DataFrame,
                  distribuicao: pd.DataFrame, quando: pd.Timestamp, desempate: str = "fluxo",
                  seed: int | None = None) -> pd.DataFrame:
    ag = _preparar(agenda)
    if desempate == "fluxo":
        so_trio = ag["TIPO_AGENDAMENTO"].isin(_TRIO).groupby([ag["_k"], ag["_dia"]]).transform("all")
        ag["_prec"] = np.where(so_trio, ag["TIPO_AGENDAMENTO"].map(_TRIO).fillna(0), 0)
        ag = ag.sort_values(["_k", "_dia", "_prec", "DATA_AGENDAMENTO", "ID_AGENDA"],
                            ascending=[True, False, False, False, False])
    elif desempate == "acaso":
        ag["_sorte"] = np.random.default_rng(seed).random(len(ag))
        ag = ag.sort_values(["_k", "_dia", "_sorte"], ascending=[True, False, True])
    else:
        raise ValueError(f"desempate desconhecido: {desempate}")
    esc = ag.drop_duplicates("_k").copy()
    if esc.empty:
        raise ValueError("a regra não produziu nenhuma pasta")

    est = estoque.assign(_k=estoque["CONTRATO"].map(chave)).drop_duplicates("_k", keep="last")
    gar = garantia.assign(_k=garantia["CARTEIRA_CONTRATO"].map(chave)).drop_duplicates("_k", keep="last")
    vei = (veiculo.assign(_k=veiculo["PASTA"].map(chave)).sort_values(["_k", "COR"], na_position="first")
           .drop_duplicates("_k"))
    dist = (distribuicao.assign(_k=distribuicao["PASTA"].map(chave)).sort_values("DATA_CONCLUSAO")
            .drop_duplicates("_k", keep="last"))
    df = (esc.merge(est.drop(columns=["CONTRATO"]).rename(columns={"CPF": "_cpf"}), on="_k", how="left")
          .merge(gar.drop(columns=["CARTEIRA_CONTRATO"]), on="_k", how="left")
          .merge(vei[["_k", "COR"]], on="_k", how="left")
          .merge(dist[["_k", "DATA_CONCLUSAO"]], on="_k", how="left"))

    df["PASTA"] = df["PASTA"].astype(str).str.rstrip()
    df["STATUS_PROCESSO"] = "Ativo"
    df["CARTEIRA_PRODUTO"] = df["FASE"]                  # a "FASE" do estoque é o segmento da carteira
    df["FASE"] = df["TIPO_AGENDAMENTO"].map(fase_de)     # a FASE do painel é a etapa do processo
    for c in _SEMPRE_NULAS:
        df[c] = None
    df["STATUS_2"] = df["STATUS"]
    df["CPF"] = df["_cpf"]
    df["CPF_PARTE_CONTRARIA"] = df["_cpf"]
    df["DATA_CADASTRO_ANDAMENTO_SOMENTE_DATA"] = df["DATA_AGENDAMENTO"].dt.date
    df["DATA_CADASTRO_ANDAMENTO_SOMENTE_HORA"] = df["DATA_AGENDAMENTO"].dt.time
    df["DESCRICAO_FASE"] = df["FASE_ESTOQUE"]
    df["BASE_PRODUCAO"] = "PRODUTIVO"
    df["CONTRATO"] = df["PASTA"]
    df["DATA_DISTRIBUICAO"] = df["DATA_CONCLUSAO"].dt.strftime("%d/%m/%Y")
    df["DATA_INSERT"] = quando
    df["RKG"] = 1
    df["DATA_AGENDAMENTO"] = df["DATA_AGENDAMENTO"].dt.date
    out = df[list(COLUNAS)].reset_index(drop=True)
    if not out["PASTA"].is_unique or not out["TIPO_AGENDAMENTO"].isin(TIPOS).all():
        raise ValueError("saída da regra inválida (PASTA repetida ou TIPO fora da lista)")
    return out
