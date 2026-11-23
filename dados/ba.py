"""Fontes sintéticas da aba Busca e Apreensão, derivadas da simulação de processos (dados/gerar.py).

O painel real lê do sistema jurídico as tarefas abertas desde 01/01/2026: mandados, liminar, localização do veículo
("EM DILIGÊNCIA - VEÍCULO LOCALIZADO"), apreensão ("BEM APREENDIDO") e fichas enviadas a localizadores, mais os campos
do formulário da apreensão, as ações dos advogados, a fase da carteira, as metas e os feriados. Aqui tudo sai da mesma
simulação que alimenta o resto do painel: nenhuma apreensão é inventada, as datas de apreensão são as da simulação.

Defeitos da fonte real que aparecem de propósito: registro da apreensão depois das 19h e no fim de semana, data da
apreensão digitada com o ano errado, avaliação do bem fora da faixa, localização "AGENDADO EQUIVOCADAMENTE", nome do
localizador em texto livre (com telefone, prefixo "LOC.", UF solta, só telefone, só um ponto), xarás e chave da pasta com
espaço. Localizadores são codinomes fictícios e os telefones usam o DDD 00, que não existe.
"""
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from dados.gerar import HOJE, Simulacao
from src.ba_calendario import FERIADOS_2026

INICIO_BA = pd.Timestamp("2026-01-01")
FIM = HOJE + pd.Timedelta(hours=17, minutes=5)       # último "agora" do dia simulado
LOC = "EM DILIGÊNCIA - VEÍCULO LOCALIZADO"
APREENSAO = "BEM APREENDIDO"
FICHA = "ENVIAR FICHA LOCALIZADOR"
P_LOC_APREENDIDA = 0.88          # apreensões precedidas de localização registrada
P_LOC_EXPEDIDO = 0.09            # pastas com mandado expedido aberto que ganham localização aberta
P_LOC_SEM_EXPEDIDO = 0.03        # pastas com liminar, negativo ou requerido aberto que ganham localização aberta
P_LOC_ENCERRADA = 0.025          # pastas com mandado em 2026, sem apreensão, com localização encerrada
P_RELOCALIZADA = 0.012           # apreendidas que voltam a ser procuradas
P_FICHAS = 0.62                  # pastas com liminar/mandado em 2026 que recebem ficha de localizador
TIQUETE = {"JUDICIAL 1": 21_000, "JUDICIAL 2": 17_500, "JUDICIAL 3": 12_500, "PREJUÍZO": 8_500}

_AVES = ["ARARA", "TUCANO", "SABIA", "BEM TE VI", "CANARIO", "GAVIAO", "CORUJA", "GARCA", "TIZIU", "SERIEMA", "JACU",
         "MUTUM", "URUTAU", "ANU", "CARCARA", "SOCO", "JACANA", "SAIRA", "TANGARA", "UIRAPURU", "PINTASSILGO", "CURIO",
         "AZULAO", "JURITI", "ARAPONGA", "CAMBACICA", "TICO TICO", "QUERO QUERO", "MARTIM", "BIGUA"]
_RIOS = ["RIO DOCE", "RIO VERDE", "RIO PRETO", "RIO CLARO", "RIO BRANCO", "RIO NEGRO", "RIO TIETE", "RIO URUGUAI",
         "RIO PARDO", "RIO MOGI", "RIO GRANDE", "RIO SAPUCAI", "RIO PIRACICABA", "RIO IVAI", "RIO JACUI", "RIO MEARIM",
         "RIO PARNAIBA", "RIO XINGU", "RIO TAPAJOS", "RIO JURUA"]
_SERRAS = ["SERRA AZUL", "SERRA DOURADA", "SERRA VERDE", "SERRA NEGRA", "SERRA DO MAR", "SERRA BRANCA", "SERRA ALTA",
           "SERRA DA CANASTRA", "SERRA FINA", "SERRA PELADA"]
_SUFIXOS = ["", " SUL", " NORTE", " LESTE"]


@dataclass
class FontesBA:
    tarefas: pd.DataFrame
    campos: pd.DataFrame
    acoes: pd.DataFrame
    fase_base: pd.DataFrame
    fichas: pd.DataFrame
    estoque: pd.DataFrame
    metas_faixa: pd.DataFrame
    metas_advogado: pd.DataFrame
    feriados: tuple[date, ...]


def fase_por_atraso(dias) -> str | None:
    if dias is None or pd.isna(dias):
        return None
    dias = int(dias)
    return ("ATÉ 120" if dias <= 120 else "JUDICIAL 1" if dias <= 240 else "JUDICIAL 2" if dias <= 360
            else "JUDICIAL 3" if dias <= 720 else "PREJUÍZO")


def _codinomes() -> list[str]:
    base = _AVES + _RIOS + _SERRAS
    out = [b + s for s in _SUFIXOS for b in base]
    return out[:160]


def _localizadores(rng) -> pd.DataFrame:
    """Um localizador por linha: rótulo verdadeiro, telefone (ou None) e as grafias que os advogados digitam."""
    nomes = _codinomes()
    linhas = []
    usados: set[str] = set()

    def tel():
        while True:
            t = f"9{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}"
            if t not in usados:
                usados.add(t)
                return t

    for i, nome in enumerate(nomes):
        linhas.append((nome, tel()))
        if i < 6:                                     # xarás: mesmo codinome, outro telefone
            linhas.append((nome, tel()))
    linhas += [(None, tel()), (None, tel())]          # só telefone
    ufs = ["SP", "MG", "RJ", "PR", "BA"]
    out = []
    for k, (nome, t) in enumerate(linhas):
        tel_txt = f"00 {t}"
        if nome is None:
            grafias = [tel_txt, f"(00) {t}"]
        else:
            formatos = [f"{nome} - {tel_txt}", f"LOC. {nome} {ufs[k % len(ufs)]}", f"{tel_txt} ({nome})", nome,
                        f"{nome} / (00) {t}"]
            n = int(rng.choice([1, 2, 3], p=[0.55, 0.3, 0.15]))
            grafias = [formatos[0]] + list(rng.choice(formatos[1:], n - 1, replace=False))
        out.append({"id": k, "nome": nome, "telefone": t, "grafias": grafias,
                    "peso": float(rng.gamma(1.2, 1.0))})
    return pd.DataFrame(out)


def _hora(rng, dia: pd.Timestamp, p_noite: float = 0.0) -> pd.Timestamp:
    h = int(rng.integers(19, 23)) if rng.random() < p_noite else int(rng.integers(8, 19))
    return dia.normalize() + pd.Timedelta(hours=h, minutes=int(rng.integers(0, 60)))


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fontes_ba(sim: Simulacao, seed: int = 7) -> FontesBA:
    rng = np.random.default_rng(seed)
    p = sim.pastas.set_index("PASTA")
    t = sim.tarefas.loc[~sim.tarefas["_falsa"]].copy()
    t["TAREFA"] = t["TIPO_AGENDAMENTO"].str.upper().str.strip()
    t = t[t["TAREFA"].str.contains("MANDADO|LIMINAR") & (t["inicio"] >= INICIO_BA) & (t["inicio"] <= FIM)]
    t = t.sort_values(["_pasta", "TAREFA", "inicio"])

    # ---- mandados e liminar: cada tarefa da simulação vira uma tarefa lida; a cadeia de reagendamentos fica REAGENDADO
    prox_mesmo = t.groupby(["_pasta", "TAREFA"])["inicio"].shift(-1)
    concl = t["fim"].where(t["fim"] <= FIM)
    status = np.where(concl.isna(), None, np.where(prox_mesmo.notna(), "REAGENDADO", "CONCLUIDO"))
    exp_fim = (t["TAREFA"].str.contains("EXPEDIDO")) & concl.notna() & prox_mesmo.isna()
    status = np.where(exp_fim & (rng.random(len(t)) < 0.3), "AG. RESULTADO", status)
    mand = pd.DataFrame({"PASTA": t["_pasta"].to_numpy(), "TAREFA": t["TAREFA"].to_numpy(),
                         "DATA_INICIO": t["inicio"].to_numpy(), "DATA_CONCLUSAO": concl.to_numpy(), "STATUS_FINAL": status})

    novas = []          # (pasta, tarefa, inicio, conclusao, status)
    campos = []         # (pasta, tarefa_idx, campo, valor, data_cadastro)
    apreensoes = {}     # pasta -> (data real, registro)
    ap = p["dia_apreensao"]
    ap26 = ap[(ap >= INICIO_BA - pd.Timedelta(days=3)) & ap.notna()]
    for pasta, dia in ap26.items():
        real = dia
        lag = int(rng.choice([0, 1, 2, 3], p=[0.55, 0.3, 0.1, 0.05]))
        registro = _hora(rng, real + pd.Timedelta(days=lag), p_noite=0.18)
        if rng.random() < P_LOC_APREENDIDA:
            antes = float(np.clip(9 * np.exp(0.7 * rng.standard_normal()), 1, 40))
            ini = _hora(rng, real - pd.Timedelta(days=antes))
            if INICIO_BA <= ini <= FIM:
                fim_loc = registro if registro <= FIM else pd.NaT
                novas.append((pasta, LOC, ini, fim_loc, "VEICULO APREENDIDO" if pd.notna(fim_loc) else None))
        if INICIO_BA <= registro <= FIM:
            apreensoes[pasta] = (real, registro)
            novas.append((pasta, APREENSAO, registro, registro + pd.Timedelta(days=1), "CONCLUIDO"))
            if rng.random() < P_RELOCALIZADA and real + pd.Timedelta(days=10) < FIM:
                novas.append((pasta, LOC, _hora(rng, real + pd.Timedelta(days=float(rng.uniform(5, 40)))), pd.NaT, None))

    abertos = mand.loc[mand["TAREFA"].str.contains("EXPEDIDO") & mand["DATA_CONCLUSAO"].isna(), "PASTA"].unique()
    for pasta in abertos:
        if pasta in apreensoes or pd.notna(ap.get(pasta)) and ap.get(pasta) <= FIM + pd.Timedelta(days=40):
            continue
        if rng.random() < P_LOC_EXPEDIDO:
            ini = _hora(rng, FIM - pd.Timedelta(days=float(rng.uniform(1, 60))))
            novas.append((pasta, LOC, ini, pd.NaT, None))
    # localizado sem mandado aguardando: liminar deferida, mandado negativo ou requerido em aberto
    sem_exp = mand.loc[mand["TAREFA"].str.contains("LIMINAR|NEGATIVO|REQUERIDO") & mand["DATA_CONCLUSAO"].isna(), "PASTA"].unique()
    abertos_set = set(abertos)
    for pasta in sem_exp:
        if pasta in apreensoes or pasta in abertos_set or pd.notna(ap.get(pasta)) and ap.get(pasta) <= FIM + pd.Timedelta(days=40):
            continue
        if rng.random() < P_LOC_SEM_EXPEDIDO:
            novas.append((pasta, LOC, _hora(rng, FIM - pd.Timedelta(days=float(rng.uniform(1, 45)))), pd.NaT, None))
    com_mandado = mand["PASTA"].unique()
    for pasta in com_mandado:
        if pasta in apreensoes or rng.random() >= P_LOC_ENCERRADA:
            continue
        ini = _hora(rng, INICIO_BA + pd.Timedelta(days=float(rng.uniform(0, (FIM - INICIO_BA).days - 70))))
        st = "AGENDADO EQUIVOCADAMENTE" if rng.random() < 0.5 else "NAO LOCALIZADO NO ENDERECO"
        novas.append((pasta, LOC, ini, ini + pd.Timedelta(days=float(rng.uniform(5, 60))), st))
    loc = pd.DataFrame(novas, columns=["PASTA", "TAREFA", "DATA_INICIO", "DATA_CONCLUSAO", "STATUS_FINAL"])

    # ---- fichas de localizador (dentro e fora do universo)
    locs = _localizadores(rng)
    peso = locs["peso"].to_numpy() / locs["peso"].sum()
    liminar_ou_mand = mand.groupby("PASTA")["DATA_INICIO"].min()
    primeira_loc = loc[loc["TAREFA"] == LOC].groupby("PASTA")["DATA_INICIO"].min()
    fichas, loc_da_ficha = [], {}
    for pasta, ini in liminar_ou_mand.items():
        no_universo = pasta in primeira_loc.index
        if not no_universo and rng.random() >= P_FICHAS:
            continue
        n = int(rng.choice([1, 2, 3], p=[0.55, 0.32, 0.13]))
        if no_universo:   # a ficha vem antes da localização (mediana ~30 dias)
            d0 = primeira_loc[pasta] - pd.Timedelta(days=float(np.clip(30 * np.exp(0.6 * rng.standard_normal()), 2, 150)))
            d0 = max(d0, INICIO_BA)
            if rng.random() < 0.12:     # ficha que chega com o carro já achado
                d0 = primeira_loc[pasta] + pd.Timedelta(days=float(rng.uniform(1, 10)))
        else:
            d0 = ini + pd.Timedelta(days=float(rng.uniform(0, 20)))
        d = d0
        for _ in range(n):
            if d > FIM:
                break
            j = int(rng.choice(len(locs), p=peso))
            envio = _hora(rng, d)
            st = "CANCELADO" if rng.random() < 0.04 else "ENVIADO"
            conc = envio + pd.Timedelta(hours=float(rng.uniform(1, 40)))
            fichas.append((pasta, envio, conc if conc <= FIM else pd.NaT, st if conc <= FIM else None,
                           str(rng.choice(locs.at[j, "grafias"])), j))
            if no_universo and envio <= primeira_loc[pasta]:
                loc_da_ficha[pasta] = j
            d = d + pd.Timedelta(days=float(rng.uniform(20, 70)))
    fichas = pd.DataFrame(fichas, columns=["PASTA", "DATA_INICIO", "DATA_CONCLUSAO", "STATUS_FINAL", "LOCALIZADOR", "_loc"])

    # ---- campos do formulário da apreensão
    est = sim.estoque.assign(_k=sim.estoque["CONTRATO"].str.upper().str.strip()).drop_duplicates("_k").set_index("_k")
    for pasta, (real, registro) in apreensoes.items():
        bem = float(est["VALOR_DO_BEM"].get(pasta, np.nan))
        ref = None if np.isnan(bem) else round(bem * float(rng.uniform(0.9, 1.3)), 2)
        ano = real.year - 1 if rng.random() < 0.02 else real.year          # ano digitado errado: fora da janela
        campos.append((pasta, "DATA DA APREENSÃO", f"{real.day:02d}/{real.month:02d}/{ano}", registro))
        if ref is not None and rng.random() > 0.05:
            campos.append((pasta, "TABELA FIPE", _brl(ref), registro))
        r = rng.random()
        if ref is not None and r < 0.80:
            fator = rng.uniform(0.5, 0.85) if r < 0.40 else (rng.uniform(0.86, 1.2) if r < 0.75 else rng.uniform(3.2, 5))
            campos.append((pasta, "AVALIAÇÃO DO BEM", _brl(round(ref * float(fator), 2)), registro))
        j = loc_da_ficha.get(pasta)
        if j is None or rng.random() < 0.15:
            j = int(rng.choice(len(locs), p=peso))
        texto = "." if rng.random() < 0.04 else ("" if rng.random() < 0.04 else str(rng.choice(locs.at[j, "grafias"])))
        if texto:
            campos.append((pasta, "NOME DO LOCALIZADOR", texto, registro))
    campos = pd.DataFrame(campos, columns=["PASTA", "CAMPO", "VALOR", "DATA_CADASTRO"])
    campos["TAREFA"] = APREENSAO

    # ---- tarefas finais com os atributos da pasta
    tarefas = pd.concat([mand, loc], ignore_index=True)
    attrs = p[["UF", "COMARCA", "ADVOGADO_OPERACIONAL", "PARTE_CONTRARIA"]]
    tarefas = tarefas.join(attrs, on="PASTA")
    tarefas = tarefas.rename(columns={"ADVOGADO_OPERACIONAL": "ADV_OPERACIONAL"})
    tarefas["LOGIN_OPERACIONAL"] = tarefas["ADV_OPERACIONAL"].str.replace("ADV-", "adv", regex=False)
    tarefas["RESPONSAVEL"] = tarefas["ADV_OPERACIONAL"]
    tarefas["MEMO"] = np.where(tarefas["TAREFA"] == LOC,
                               "Veículo visto em " + tarefas["COMARCA"].fillna("") + "/" + tarefas["UF"].fillna("")
                               + "; contato com o localizador; aguardando o oficial de justiça.", None)
    tarefas = tarefas.sort_values(["PASTA", "DATA_INICIO", "TAREFA"]).reset_index(drop=True)
    tarefas.insert(1, "ID_TAREFA", np.arange(5_000_000, 5_000_000 + len(tarefas)))
    espaco = rng.random(len(tarefas)) < 0.01                       # chave da pasta com espaço/NBSP, como na fonte
    tarefas.loc[espaco, "PASTA"] = tarefas.loc[espaco, "PASTA"] + "\xa0"
    id_ap = tarefas[tarefas["TAREFA"] == APREENSAO].assign(_k=lambda x: x["PASTA"].str.strip()).set_index("_k")["ID_TAREFA"]
    campos.insert(1, "ID_TAREFA", campos["PASTA"].map(id_ap).astype("int64"))

    fichas = fichas.join(attrs, on="PASTA").rename(columns={"ADVOGADO_OPERACIONAL": "ADV_OPERACIONAL"})
    fichas.insert(1, "ID_TAREFA", np.arange(8_000_000, 8_000_000 + len(fichas)))
    fichas = fichas.drop(columns=["PARTE_CONTRARIA"])

    # ---- ações do responsável (últimos 45 dias) nas pastas com localização aberta
    acoes = []
    abertas = tarefas[(tarefas["TAREFA"] == LOC) & tarefas["DATA_CONCLUSAO"].isna()]
    for pasta, login in zip(abertas["PASTA"].str.strip(), abertas["LOGIN_OPERACIONAL"]):
        if login is None or pd.isna(login):
            continue
        parado = rng.random() < 0.3
        ultimo = int(rng.integers(3, 30)) if parado else int(rng.integers(0, 2))
        for k in range(ultimo, 45, int(rng.integers(2, 6))):
            acoes.append((pasta, login, (HOJE - pd.Timedelta(days=k)).normalize(), int(rng.integers(1, 6))))
        if rng.random() < 0.4:
            acoes.append((pasta, "integracao", (HOJE - pd.Timedelta(days=int(rng.integers(0, 10)))).normalize(), 1))
    acoes = pd.DataFrame(acoes, columns=["PASTA", "LOGIN", "DIA", "ALTERACOES"])

    fase_base = pd.DataFrame({"CONTRATO": sim.estoque["CONTRATO"], "DIA_REF": HOJE.normalize(),
                              "DIAS_ATRASO_REF": sim.estoque["DIAS_ATRASO"]})
    estoque = sim.estoque[["CONTRATO", "VALOR_RISCO_CONTRATO", "VALOR_DO_BEM"]].copy()

    metas_faixa, metas_adv = _metas(rng, apreensoes, fase_base, p)
    return FontesBA(tarefas, campos, acoes, fase_base, fichas.drop(columns=["_loc"]), estoque, metas_faixa, metas_adv,
                    FERIADOS_2026)


def _metas(rng, apreensoes: dict, fase_base: pd.DataFrame, p: pd.DataFrame):
    """Metas sintéticas: perto do realizado de cada mês (nunca os números do cliente); dezembro fica sem meta."""
    atraso = fase_base.assign(_k=fase_base["CONTRATO"].str.upper().str.strip()).drop_duplicates("_k").set_index("_k")
    reg = pd.DataFrame([(k, r.month, r.year) for k, (_, r) in apreensoes.items()], columns=["PASTA", "M", "A"])
    reg = reg[reg["A"] == 2026]
    dias = reg["PASTA"].map(atraso["DIAS_ATRASO_REF"]) - [(HOJE - pd.Timestamp(2026, m, 15)).days for m in reg["M"]]
    reg["FASE"] = [fase_por_atraso(d) for d in dias]
    reg["ADV"] = reg["PASTA"].map(p["ADVOGADO_OPERACIONAL"])
    faixa, adv = [], []
    media = reg[reg["FASE"].isin(TIQUETE)].groupby("FASE").size() / reg["M"].nunique()
    top = reg["ADV"].dropna().value_counts().head(12).index
    media_adv = reg.groupby("ADV").size() / reg["M"].nunique()
    for m in range(1, 12):
        mes = f"{m:02d}/2026"
        f = {k: int(round(media.get(k, 1) * float(rng.uniform(1.0, 1.2)))) for k in TIQUETE}
        for k, q in f.items():
            faixa.append((mes, k, q, None if k in ("JUDICIAL 1", "JUDICIAL 2") else q * TIQUETE[k]))
        faixa.append((mes, "121 A 360", None, f["JUDICIAL 1"] * TIQUETE["JUDICIAL 1"] + f["JUDICIAL 2"] * TIQUETE["JUDICIAL 2"]))
        for a in top:
            q = int(round(media_adv[a] * float(rng.uniform(1.0, 1.25))))
            adv.append((mes, a, q, q * 16_000))
    cols = ["MES", "CHAVE", "QTD", "VALOR"]
    return pd.DataFrame(faixa, columns=cols), pd.DataFrame(adv, columns=cols)
