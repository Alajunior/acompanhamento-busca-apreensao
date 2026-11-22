"""Simulação dos processos de busca e apreensão (dados 100% sintéticos).

Cada processo nasce no contencioso, é ajuizado e percorre o fluxo do painel:
EMENDAR INICIAL → (EMENDA REALIZADA) → AGUARDANDO LIMINAR → LIMINAR DEFERIDA → 1º MANDADO EXPEDIDO →
apreensão, ou NEGATIVO → REQUERIDO → EXPEDIDO da próxima tentativa (até "6º OU +").
Saídas (apreensão, acordo, desistência) abrem uma tarefa BAIXADO que fica alguns dias aberta junto das outras.

O sistema jurídico guarda tarefas: cada etapa é uma tarefa aberta de `inicio` até `fim`, com um prazo
(DATA_AGENDAMENTO). `agenda_em(sim, quando)` devolve as tarefas abertas naquele instante, como a consulta real.

Calibração (medianas de dias antes da apreensão, achados reais): contencioso 170, ajuizamento 71, liminar 34,
1º mandado 18; 74% apreendidos no 1º mandado; ~4.500 pastas ativas; ~1,3% apreendidas em 14 dias.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

HOJE = pd.Timestamp("2026-11-26")
DIA_EXTINCAO = pd.Timestamp("2026-11-03")          # EMENDA REALIZADA deixa de existir (episódio fiel ao real)
INICIO = HOJE - pd.Timedelta(days=1000)             # aquecimento: a carteira chega ao estado estável antes da janela
CHEGADAS_DIA = 16.8                                 # ajuizamentos por dia
P_APREENSAO = 0.22                                  # fração que termina em apreensão (o resto sai por acordo/desistência)

# UFs e peso (mesmo do projeto de Entrega Amigável)
UFS = ["SP", "MG", "RJ", "BA", "PR", "RS", "PE", "CE", "PA", "SC", "GO", "MA", "AM", "ES", "PB", "RN", "MT", "AL",
       "PI", "DF", "MS", "SE", "RO", "TO", "AC", "AP", "RR"]
PESO_UF = np.array([22, 10, 8, 7, 5.5, 5.3, 4.5, 4.3, 4.1, 3.6, 3.4, 3.3, 2, 1.9, 1.9, 1.7, 1.8, 1.6, 1.6, 1.4, 1.4,
                    1.1, 1.0, 0.8, 0.5, 0.4, 0.3])
NOME_UF = {"AC": "ACRE", "AL": "ALAGOAS", "AP": "AMAPA", "AM": "AMAZONAS", "BA": "BAHIA", "CE": "CEARA",
           "DF": "DISTRITO FEDERAL", "ES": "ESPIRITO SANTO", "GO": "GOIAS", "MA": "MARANHAO", "MT": "MATO GROSSO",
           "MS": "MATO GROSSO DO SUL", "MG": "MINAS GERAIS", "PA": "PARA", "PB": "PARAIBA", "PR": "PARANA",
           "PE": "PERNAMBUCO", "PI": "PIAUI", "RJ": "RIO DE JANEIRO", "RN": "RIO GRANDE DO NORTE",
           "RS": "RIO GRANDE DO SUL", "RO": "RONDONIA", "RR": "RORAIMA", "SC": "SANTA CATARINA", "SP": "SAO PAULO",
           "SE": "SERGIPE", "TO": "TOCANTINS"}
# comarcas = municípios (geografia pública), com o centro aproximado (lat, lon) usado na fase 2
COMARCAS = {
    "SP": [("SAO PAULO", -23.55, -46.63, 40), ("CAMPINAS", -22.91, -47.06, 8), ("GUARULHOS", -23.46, -46.53, 7),
           ("SANTOS", -23.96, -46.33, 5), ("SOROCABA", -23.50, -47.46, 5), ("RIBEIRAO PRETO", -21.18, -47.81, 5),
           ("SAO JOSE DOS CAMPOS", -23.18, -45.89, 5), ("OSASCO", -23.53, -46.79, 5)],
    "MG": [("BELO HORIZONTE", -19.92, -43.94, 40), ("CONTAGEM", -19.93, -44.05, 12), ("UBERLANDIA", -18.92, -48.28, 12),
           ("JUIZ DE FORA", -21.76, -43.35, 10)],
    "RJ": [("RIO DE JANEIRO", -22.91, -43.17, 50), ("NITEROI", -22.88, -43.10, 10), ("NOVA IGUACU", -22.76, -43.45, 10),
           ("DUQUE DE CAXIAS", -22.79, -43.31, 10), ("SAO GONCALO", -22.83, -43.06, 10)],
    "BA": [("SALVADOR", -12.97, -38.50, 50), ("FEIRA DE SANTANA", -12.27, -38.97, 15), ("VITORIA DA CONQUISTA", -14.86, -40.84, 8)],
    "PR": [("CURITIBA", -25.43, -49.27, 45), ("LONDRINA", -23.31, -51.16, 15), ("MARINGA", -23.42, -51.94, 12)],
    "RS": [("PORTO ALEGRE", -30.03, -51.23, 45), ("CAXIAS DO SUL", -29.17, -51.18, 15), ("PELOTAS", -31.77, -52.34, 10)],
    "PE": [("RECIFE", -8.05, -34.88, 50), ("JABOATAO DOS GUARARAPES", -8.11, -35.01, 15), ("CARUARU", -8.28, -35.98, 8)],
    "CE": [("FORTALEZA", -3.73, -38.53, 60), ("JUAZEIRO DO NORTE", -7.21, -39.32, 10), ("CAUCAIA", -3.74, -38.66, 8)],
    "PA": [("BELEM", -1.46, -48.49, 55), ("ANANINDEUA", -1.37, -48.37, 15), ("SANTAREM", -2.44, -54.71, 8)],
    "SC": [("FLORIANOPOLIS", -27.60, -48.55, 30), ("JOINVILLE", -26.30, -48.85, 20), ("BLUMENAU", -26.92, -49.07, 15)],
    "GO": [("GOIANIA", -16.68, -49.25, 55), ("APARECIDA DE GOIANIA", -16.82, -49.24, 15), ("ANAPOLIS", -16.33, -48.95, 10)],
    "MA": [("SAO LUIS", -2.53, -44.30, 60), ("IMPERATRIZ", -5.53, -47.49, 15)],
    "AM": [("MANAUS", -3.12, -60.02, 80)],
    "ES": [("VITORIA", -20.32, -40.34, 30), ("VILA VELHA", -20.33, -40.29, 20), ("SERRA", -20.13, -40.31, 15)],
    "PB": [("JOAO PESSOA", -7.12, -34.86, 55), ("CAMPINA GRANDE", -7.23, -35.88, 20)],
    "RN": [("NATAL", -5.79, -35.21, 60), ("MOSSORO", -5.19, -37.34, 15)],
    "MT": [("CUIABA", -15.60, -56.10, 50), ("VARZEA GRANDE", -15.65, -56.13, 15), ("RONDONOPOLIS", -16.47, -54.64, 10)],
    "AL": [("MACEIO", -9.67, -35.74, 70), ("ARAPIRACA", -9.75, -36.66, 15)],
    "PI": [("TERESINA", -5.09, -42.80, 70), ("PARNAIBA", -2.90, -41.78, 10)],
    "DF": [("BRASILIA", -15.79, -47.88, 100)],
    "MS": [("CAMPO GRANDE", -20.47, -54.62, 60), ("DOURADOS", -22.22, -54.81, 15)],
    "SE": [("ARACAJU", -10.91, -37.07, 70), ("NOSSA SENHORA DO SOCORRO", -10.86, -37.13, 10)],
    "RO": [("PORTO VELHO", -8.76, -63.90, 55), ("JI-PARANA", -10.88, -61.95, 15)],
    "TO": [("PALMAS", -10.18, -48.33, 50), ("ARAGUAINA", -7.19, -48.21, 20)],
    "AC": [("RIO BRANCO", -9.97, -67.81, 80)],
    "AP": [("MACAPA", 0.03, -51.07, 80)],
    "RR": [("BOA VISTA", 2.82, -60.67, 90)],
}
CARTEIRAS = np.array(["VAREJO 1", "VAREJO 2", "VAREJO 3", "ALTO VALOR 1", "FROTAS 1"])
P_CARTEIRA = np.array([0.34, 0.27, 0.18, 0.12, 0.09])
PRODUTOS = np.array(["LEVES", "MOTOS", "PESADOS"])
P_PRODUTO = np.array([0.82, 0.12, 0.06])
MARCAS = {
    "LEVES": [("FIAT", ["PALIO", "UNO", "ARGO", "MOBI", "STRADA"], 20), ("VOLKSWAGEN", ["GOL", "POLO", "VOYAGE", "FOX"], 18),
              ("CHEVROLET", ["ONIX", "PRISMA", "CELTA", "S10"], 18), ("RENAULT", ["SANDERO", "LOGAN", "KWID"], 9),
              ("HYUNDAI", ["HB20", "CRETA"], 9), ("FORD", ["KA", "FIESTA", "ECOSPORT"], 8), ("TOYOTA", ["COROLLA", "ETIOS", "HILUX"], 7),
              ("HONDA", ["CIVIC", "FIT", "CITY"], 5), ("NISSAN", ["MARCH", "VERSA", "KICKS"], 3), ("JEEP", ["RENEGADE", "COMPASS"], 3),
              ("PEUGEOT", ["208", "2008"], 2), ("CITROEN", ["C3", "AIRCROSS"], 2)],
    "MOTOS": [("HONDA", ["CG 160", "BIZ", "CB 300"], 60), ("YAMAHA", ["FAZER 250", "FACTOR", "LANDER"], 35), ("SUZUKI", ["YES", "INTRUDER"], 5)],
    "PESADOS": [("MERCEDES-BENZ", ["ACCELO", "ATEGO", "AXOR"], 35), ("VOLVO", ["FH", "VM"], 25), ("SCANIA", ["R 450", "P 320"], 20),
                ("IVECO", ["TECTOR", "DAILY"], 20)],
}
CORES = np.array(["PRATA", "BRANCA", "PRETA", "CINZA", "VERMELHA", "AZUL"])
TIPOS_AUX = np.array(["PROTOCOLAR PETICAO", "CONFERIR CUSTAS", "CONTATAR CLIENTE", "JUNTAR DOCUMENTO", "AUDIENCIA"])
N_ADV = 24
# empate (duas tarefas do trio no mesmo dia): na etapa real EMENDAR é comum, em AGUARDANDO é raro → ~87% dos
# empates AGUARDANDO × EMENDAR têm EMENDAR como etapa real (medido no histórico do sistema real)
P_EMPATE = {"EMENDAR INICIAL": 0.9, "AGUARDANDO LIMINAR": 0.047}
P_TRIO = 0.05
FATOR_PRAZO = {"ADV-07": 0.5, "ADV-15": 0.55}   # advogados que deixam prazo vencer mais (sinal "vencidos alto")


@dataclass
class Simulacao:
    pastas: pd.DataFrame
    tarefas: pd.DataFrame
    estoque: pd.DataFrame
    garantia: pd.DataFrame
    veiculo: pd.DataFrame
    distribuicao: pd.DataFrame


def _lognorm(rng, mediana: float, sigma: float) -> float:
    return float(mediana * np.exp(sigma * rng.standard_normal()))


def _trajetoria(rng, ajuiz: pd.Timestamp, apreende: bool, tentativa: int, saida_outro: float | None):
    """Lista de etapas (tipo, início, fim) e os marcos da pasta. Tempos em dias fracionários."""
    etapas: list[tuple[str, float]] = []   # (tipo, duração)
    if rng.random() < 0.35:
        etapas.append(("EMENDAR INICIAL", _lognorm(rng, 12 if apreende else 90, 0.6)))
        etapas.append(("EMENDA REALIZADA", _lognorm(rng, 3 if apreende else 25, 0.5)))
    etapas.append(("AGUARDANDO LIMINAR", _lognorm(rng, 26 if apreende else 85, 0.55 if apreende else 0.8)))
    etapas.append(("LIMINAR DEFERIDA", _lognorm(rng, 14.5 if apreende else 24, 0.45)))
    n_tent = tentativa if apreende else min(7, 1 + int(rng.geometric(0.45)) - 1)   # sem apreensão: poucas tentativas, depois para
    for k in range(1, n_tent + 1):
        rot = f"{k}º" if k <= 5 else "6º OU +"
        if k > 1:
            etapas.append((f"{rot} MANDADO REQUERIDO", _lognorm(rng, 9, 0.5)))
        final = apreende and k == tentativa
        parado = not apreende and k == n_tent and rng.random() < 0.6   # sem apreensão: a última diligência fica em aberto
        etapas.append((f"{rot} MANDADO EXPEDIDO", _lognorm(rng, 13.5 if final else 30, 0.6)))
        if not final and not parado:
            etapas.append((f"{rot} MANDADO NEGATIVO", _lognorm(rng, 12 if apreende else 28, 0.5)))

    t = ajuiz
    out, marcos = [], {"dia_liminar": pd.NaT, "dia_mandado1": pd.NaT}
    fim_total = ajuiz + pd.Timedelta(days=saida_outro) if saida_outro is not None else None
    for tipo, dur in etapas:
        ini, fim = t, t + pd.Timedelta(days=dur)
        if tipo == "EMENDA REALIZADA":
            if ini >= DIA_EXTINCAO:
                continue                                  # depois da extinção a emenda vai direto para AGUARDANDO
            if fim > DIA_EXTINCAO:
                fim = DIA_EXTINCAO + pd.Timedelta(hours=8)   # tarefas abertas migram no dia da extinção
        if fim_total is not None and ini >= fim_total:
            break
        if fim_total is not None and fim > fim_total:
            fim = fim_total
        out.append((tipo, ini, fim))
        if tipo == "LIMINAR DEFERIDA":
            marcos["dia_liminar"] = ini
        if tipo == "1º MANDADO EXPEDIDO":
            marcos["dia_mandado1"] = ini
        t = fim
    return out, marcos, t


def simular(seed: int = 42) -> Simulacao:
    rng = np.random.default_rng(seed)
    dias = (HOJE - INICIO).days + 30
    n = int(rng.poisson(CHEGADAS_DIA * dias))
    ajuiz = INICIO + pd.to_timedelta(np.sort(rng.uniform(0, dias, n)), unit="D")

    uf = rng.choice(UFS, n, p=PESO_UF / PESO_UF.sum())
    comarca = np.empty(n, dtype=object)
    for u in UFS:
        m = uf == u
        nomes = [c[0] for c in COMARCAS[u]]
        peso = np.array([c[3] for c in COMARCAS[u]], dtype=float)
        comarca[m] = rng.choice(nomes, m.sum(), p=peso / peso.sum())
    carga = rng.gamma(12.0, 1.0, N_ADV)       # carga desigual, mas só alguns acima de 1,25× a mediana
    adv = np.where(rng.random(n) < 0.03, None,
                   np.array([f"ADV-{i:02d}" for i in range(1, N_ADV + 1)], dtype=object)[rng.choice(N_ADV, n, p=carga / carga.sum())])

    linhas, pastas = [], []
    falsas: dict[int, bool] = {}          # ID_AGENDA da tarefa "falsa" do empate → é trio?
    id_agenda = 1_000_000
    defeito_chave = rng.random(n)
    for i in range(n):
        pasta = f"{7_000_000 + i:07d}"
        apreende = rng.random() < P_APREENSAO
        r = rng.random()
        tentativa = 1 if r < 0.74 else (int(rng.integers(2, 5)) if r < 0.98 else int(rng.integers(5, 8)))
        saida_outro = None if apreende else 5 + float(rng.exponential(330))
        etapas, marcos, t_fim = _trajetoria(rng, ajuiz[i], apreende, tentativa, saida_outro)
        dia_apreensao = t_fim if apreende else pd.NaT
        dia_saida = t_fim if (apreende or saida_outro is not None) else pd.NaT
        motivo = "APREENSAO" if apreende else rng.choice(["ACORDO", "DESISTENCIA", "QUITACAO"], p=[0.6, 0.25, 0.15])
        if not apreende and t_fim < ajuiz[i] + pd.Timedelta(days=saida_outro) - pd.Timedelta(seconds=1):
            dia_saida = ajuiz[i] + pd.Timedelta(days=saida_outro)   # acabaram as etapas antes da saída: fica na última

        chave_txt = pasta + ("\xa0" if defeito_chave[i] < 0.01 else (" " if defeito_chave[i] < 0.02 else ""))
        for tipo, ini, fim in etapas:
            if pd.notna(dia_saida) and tipo == etapas[-1][0] and fim >= t_fim:
                fim = dia_saida + pd.Timedelta(days=float(rng.uniform(1, 3)))   # a última fica aberta junto do BAIXADO
                if tipo == "EMENDA REALIZADA":
                    fim = min(fim, DIA_EXTINCAO + pd.Timedelta(hours=8)) if ini < DIA_EXTINCAO else fim
            # etapa longa = cadeia de tarefas do mesmo tipo: o escritório reagenda, cada tarefa com um prazo novo
            c_ini, primeira = ini, None
            while c_ini < fim:
                c_fim = min(fim, c_ini + pd.Timedelta(days=float(rng.uniform(25, 60))))
                dur = (c_fim - c_ini) / pd.Timedelta(days=1)
                prazo = c_ini + pd.Timedelta(days=max(dur, 1.0) * float(rng.uniform(0.2, 1.4)) * FATOR_PRAZO.get(adv[i], 1.0))
                prazo = prazo.normalize() + pd.Timedelta(minutes=int(rng.integers(8 * 60, 24 * 60)))
                tipo_txt = tipo.lower() + " " if rng.random() < 0.01 else tipo
                id_agenda += 1
                linhas.append((id_agenda, chave_txt, tipo_txt, prazo, c_ini, c_fim, pasta))
                primeira = primeira or prazo
                c_ini = c_fim
            prazo = primeira
            # empate: outra tarefa do trio no mesmo dia de prazo (a procedure oficial escolhe ao acaso entre elas)
            extras = []
            if tipo in P_EMPATE and rng.random() < P_EMPATE[tipo]:
                extras = [("AGUARDANDO LIMINAR" if tipo == "EMENDAR INICIAL" else "EMENDAR INICIAL", False)]
            elif tipo == "LIMINAR DEFERIDA" and rng.random() < P_TRIO:
                extras = [("EMENDAR INICIAL", True), ("AGUARDANDO LIMINAR", True)]
            fim_falsa = min(fim, ini + pd.Timedelta(days=float(rng.uniform(3, 12)))) if extras else None
            for outro, trio in extras:
                id_agenda += 1
                falsas[id_agenda] = trio
                linhas.append((id_agenda, chave_txt, outro, prazo.normalize() + pd.Timedelta(hours=23, minutes=59),
                               ini, fim_falsa, pasta))
            if rng.random() < 0.5:
                id_agenda += 1
                linhas.append((id_agenda, chave_txt, str(rng.choice(TIPOS_AUX)), prazo + pd.Timedelta(days=int(rng.integers(-5, 10))),
                               ini, min(fim, ini + pd.Timedelta(days=float(rng.uniform(10, 45)))), pasta))
        if pd.notna(dia_saida):
            id_agenda += 1
            linhas.append((id_agenda, chave_txt, "BAIXADO", dia_saida.normalize() + pd.Timedelta(hours=18),
                           dia_saida, dia_saida + pd.Timedelta(days=float(rng.uniform(1, 3))), pasta))

        contencioso = ajuiz[i] - pd.Timedelta(days=_lognorm(rng, 90, 0.35))
        pastas.append((pasta, uf[i], comarca[i], adv[i], contencioso, ajuiz[i], marcos["dia_liminar"], marcos["dia_mandado1"],
                       dia_apreensao, dia_saida, motivo if pd.notna(dia_saida) else None, tentativa if apreende else None))

    tarefas = pd.DataFrame(linhas, columns=["ID_AGENDA", "PASTA", "TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "inicio", "fim", "_pasta"])
    p = pd.DataFrame(pastas, columns=["PASTA", "UF", "COMARCA", "ADVOGADO_OPERACIONAL", "dia_contencioso", "dia_ajuizamento",
                                      "dia_liminar", "dia_mandado1", "dia_apreensao", "dia_saida", "motivo_saida",
                                      "tentativa_apreensao"])
    p = _atributos_processo(rng, p)
    tarefas["_falsa"] = tarefas["ID_AGENDA"].isin(falsas.keys())
    tarefas["_trio"] = tarefas["ID_AGENDA"].map(falsas).fillna(False).astype(bool)
    tarefas = tarefas.merge(p[["PASTA", *COLS_AGENDA_PASTA]].rename(columns={"PASTA": "_pasta"}), on="_pasta", how="left")
    estoque, garantia, veiculo, distribuicao = _fontes(rng, p)
    return Simulacao(p, tarefas, estoque, garantia, veiculo, distribuicao)


COLS_AGENDA_PASTA = ["PROCESSO_UNICO", "NUMERO_PROCESSO", "PARTE_CONTRARIA", "COMARCA", "UF", "ADVOGADO_OPERACIONAL",
                     "VARA", "FORO", "STATUS", "DIVISAO_FILIAL", "ACAO", "CONTROLE_CLIENTE", "VALOR_CAUSA", "STATUS_FINAL",
                     "ESTADO"]


def _atributos_processo(rng, p: pd.DataFrame) -> pd.DataFrame:
    n = len(p)
    ano = p["dia_ajuizamento"].dt.year.astype(str)
    seq = rng.integers(0, 9_999_999, n)
    p["PROCESSO_UNICO"] = [f"{s:07d}-{rng.integers(10, 99)}.{a}.8.00.{rng.integers(1, 9999):04d}" for s, a in zip(seq, ano)]
    p["NUMERO_PROCESSO"] = [f"P{x:08d}" for x in rng.integers(0, 99_999_999, n)]
    p["PARTE_CONTRARIA"] = [f"CLIENTE {i:06d}" for i in range(1, n + 1)]
    p["VARA"] = [f"{v}ª VARA CIVEL" for v in rng.integers(1, 9, n)]
    p["FORO"] = "FORO DE " + p["COMARCA"]
    p["STATUS"] = "Ativo"
    p["DIVISAO_FILIAL"] = rng.choice(["DIVISAO 1", "DIVISAO 2", "DIVISAO 3"], n)
    p["ACAO"] = "BUSCA E APREENSAO"
    p["CONTROLE_CLIENTE"] = [f"C{x:07d}" for x in rng.integers(0, 9_999_999, n)]
    p["STATUS_FINAL"] = None
    p["ESTADO"] = p["UF"].map(NOME_UF)
    p["VALOR_CAUSA"] = np.round(rng.lognormal(np.log(48000), 0.5, n), 2)
    return p


def _fontes(rng, p: pd.DataFrame):
    n = len(p)
    produto = np.where(rng.random(n) < 0.02, None, rng.choice(PRODUTOS, n, p=P_PRODUTO))
    idade = rng.choice(np.arange(0, 20), n, p=np.r_[np.full(10, 0.07), np.full(10, 0.03)])
    ano_modelo = HOJE.year - idade + (rng.random(n) < 0.04)          # ~4% com ano-modelo seguinte
    bem = np.round(rng.lognormal(np.log(39000) - 0.03 * (idade - 10), 0.45, n), 2)
    bem = np.where(produto == "MOTOS", bem * 0.3, np.where(produto == "PESADOS", bem * 4, bem))
    risco = np.round(bem / rng.uniform(0.45, 1.05, n), 2)
    carteira = np.where(rng.random(n) < 0.02, None, rng.choice(CARTEIRAS, n, p=P_CARTEIRA))
    sem_estoque = rng.random(n) < 0.01
    atraso = ((HOJE - p["dia_contencioso"]).dt.days + 71).clip(lower=31).to_numpy()
    cpf = [f"***.{a:03d}.{b:03d}-**" for a, b in rng.integers(0, 1000, (n, 2))]
    estoque = pd.DataFrame({
        "CONTRATO": p["PASTA"].str.lower().where(rng.random(n) < 0.01, p["PASTA"]),
        "VALOR_RISCO_CONTRATO": risco, "DIAS_ATRASO": atraso, "CPF": cpf,
        "DATA_ATUALIZACAO": HOJE, "DATA_ENTRADA": p["dia_contencioso"].dt.normalize(),
        "DATA_IMPORTACAO": p["dia_contencioso"].dt.normalize() + pd.Timedelta(days=1),
        "VALOR_CONTRATO": np.round(risco * rng.uniform(1.1, 1.6, n), 2), "VALOR_RISCO_CLIENTE": risco,
        "VALOR_DO_BEM": bem, "VALOR_ORIGINAL": np.round(risco * rng.uniform(0.6, 0.9, n), 2),
        "FASE": [c + " " * int(k) if c else None for c, k in zip(carteira, rng.integers(0, 4, n))],
        "SITUACAO": "JURIDICO", "PRODUTO_VEICULO": produto,
        "FASE_ESTOQUE": pd.cut(atraso, [0, 90, 180, 360, 720, 10 ** 6], labels=["FX 31-90", "FX 91-180", "FX 181-360",
                                                                            "FX 361-720", "FX 721+"]).astype(str),
        "IDCOB_CLIENTE": rng.integers(10 ** 6, 10 ** 7, n), "IDCOB_CONTRATO": rng.integers(10 ** 7, 10 ** 8, n),
    })[~sem_estoque].reset_index(drop=True)

    marca, modelo = [], []
    for prod in produto:
        lista = MARCAS[prod or "LEVES"]
        w = np.array([m[2] for m in lista], dtype=float)
        j = rng.choice(len(lista), p=w / w.sum())
        marca.append(lista[j][0])
        modelo.append(str(rng.choice(lista[j][1])))
    letras = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    placa = ["ZZ" + a + str(b) + c + f"{d:02d}" for a, b, c, d in
             zip(rng.choice(letras, n), rng.integers(0, 10, n), rng.choice(letras, n), rng.integers(0, 100, n))]
    sem_garantia = rng.random(n) < 0.02
    garantia = pd.DataFrame({
        "CARTEIRA_CONTRATO": p["PASTA"], "MARCA": marca, "MODELO": modelo, "PLACA": placa,
        "CHASSI": ["9" + "".join(rng.choice(list("ABCDEFGHJKLMNPRSTUVWXYZ0123456789"), 16)) for _ in range(n)],
        "ANO_FABRICACAO": (ano_modelo - (rng.random(n) < 0.5)).astype(str), "ANO_MODELO": ano_modelo.astype(str),
    })[~sem_garantia].reset_index(drop=True)

    cor = rng.choice(CORES, n)
    tem = rng.random(n) > 0.03
    veiculo = pd.DataFrame({"PASTA": p["PASTA"][tem], "COR": cor[tem]})
    duas = p["PASTA"][rng.random(n) < 0.02]
    veiculo = pd.concat([veiculo, pd.DataFrame({"PASTA": duas, "COR": None})], ignore_index=True)

    distribuicao = pd.DataFrame({"PASTA": p["PASTA"], "DATA_CONCLUSAO": p["dia_ajuizamento"].dt.normalize()})
    extra = p.sample(frac=0.3, random_state=int(rng.integers(1 << 30)))
    distribuicao = pd.concat([distribuicao, pd.DataFrame({"PASTA": extra["PASTA"],
                                                          "DATA_CONCLUSAO": extra["dia_ajuizamento"].dt.normalize()
                                                          + pd.Timedelta(days=3)})], ignore_index=True)
    p["PRODUTO_VEICULO"] = produto
    return estoque, garantia, veiculo, distribuicao


def agenda_em(sim: Simulacao, quando: pd.Timestamp, fracao: float = 1.0) -> pd.DataFrame:
    t = sim.tarefas
    m = (t["inicio"] <= quando) & (t["fim"] > quando)
    if fracao < 1.0:   # leitura parcial estável (mesmas linhas a cada chamada)
        m &= (t["ID_AGENDA"] * 2654435761 % 1000) < int(fracao * 1000)
    return t.loc[m, ["ID_AGENDA", "PASTA", "TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", *COLS_AGENDA_PASTA]].reset_index(drop=True)


def _verificar(sim: Simulacao) -> None:
    ap = sim.pastas.dropna(subset=["dia_apreensao"])
    for marco, alvo in [("dia_contencioso", 170), ("dia_ajuizamento", 71), ("dia_liminar", 34), ("dia_mandado1", 18)]:
        med = (ap["dia_apreensao"] - ap[marco]).dt.days.median()
        print(f"  {marco:<16} mediana {med:6.1f} dias antes da apreensão (alvo {alvo})")
    print(f"  apreendidos no 1º mandado: {(ap['tentativa_apreensao'] == 1).mean():.1%} (alvo 74%)")
    ag = agenda_em(sim, HOJE + pd.Timedelta(hours=17, minutes=5))
    tipos = ag["TIPO_AGENDAMENTO"].str.upper().str.strip()
    baix = set(ag.loc[tipos == "BAIXADO", "PASTA"].str.strip())
    print(f"  pastas com tarefa aberta hoje 17:05: {ag['PASTA'].str.strip().nunique()} ({len(baix)} com BAIXADO)")
    print("  etapas hoje:", tipos[~ag["PASTA"].str.strip().isin(baix)].value_counts().head(10).to_dict())
    from dados.capturas import FIM, capturas          # fase 2 (import tardio: capturas importa este módulo)
    cap = capturas(sim)
    placa = cap["PLATE"].str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    vistos = set(placa[pd.to_datetime(cap["CAPTURED"]) >= FIM - pd.Timedelta(days=60)])
    p = sim.pastas
    ativas = p[(p["dia_ajuizamento"] <= HOJE) & (p["dia_saida"].isna() | (p["dia_saida"] > FIM))]
    placas = ativas["PASTA"].map(sim.garantia.drop_duplicates("CARTEIRA_CONTRATO").set_index("CARTEIRA_CONTRATO")["PLACA"]).dropna()
    print(f"  capturas: {len(cap)}; vistos em 60 dias: {placas.isin(vistos).mean():.1%} das ativas com placa (alvo 35%)")
    from src.padroes import cargas
    est = pd.Series([v["resumo"]["estado"] for v in cargas(sim)[-1]["pastas"].values()]).value_counts()
    print("  estados às 17:05 (pastas com captura):", est.to_dict(), "(alvo entre os recentes: 42/20/38%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    s = simular(42)
    print(f"simulação: {len(s.pastas)} processos, {len(s.tarefas)} tarefas em {time.time() - t0:.1f} s")
    if args.verificar:
        _verificar(s)
