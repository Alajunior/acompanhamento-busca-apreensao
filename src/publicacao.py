"""Linha do tempo de fotos e publicações: o "ao vivo" do painel real, encenado num dia simulado.

Toda publicação vira foto. A guarda de volume rejeita uma rodada com menos de 85% das linhas da publicação
anterior (e aceita a queda se a rodada seguinte confirmar a mesma contagem com até 2% de diferença).
Se a via ao vivo falha, publica-se a tabela oficial (a hora do dado é a da recarga).

Roteiro de hoje (26/11/2026): 07:05 e 09:05 ao vivo; 11:05 leitura parcial → rejeitada; 13:05 a via ao vivo falha →
tabela oficial das 09:04; 15:05 e 17:05 ao vivo. Recargas oficiais 09:04, 15:04 e 17:04, conciliadas com a primeira
rodada ao vivo seguinte. Histórico: 12/10 a 25/11, sem domingo; os 10 primeiros dias são reconstruídos (18:00).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from dados.gerar import HOJE, Simulacao, agenda_em
from src.conciliacao import conciliar
from src.regra import montar_painel, pastas_com_empate

GUARDA = 0.85
CONFIRMACAO = 0.02
PRIORIDADE = {"ao_vivo": 0, "oficial": 1, "reconstruido": 2}
INICIO_HISTORICO = pd.Timestamp("2026-10-12")
N_RECONSTRUIDOS = 10
HORAS_HOJE = ("07:05", "09:05", "11:05", "13:05", "15:05", "17:05")
RECARGAS = ("09:04", "15:04", "17:04")
PARCIAL = {"11:05": 0.6}          # leitura incompleta da agenda
FALHA = {"13:05"}                 # via ao vivo fora do ar


@dataclass
class Foto:
    dia: date
    hora: str
    origem: str
    df: pd.DataFrame = field(repr=False)


@dataclass
class LinhaDoTempo:
    fotos: list[Foto]
    oficiais: dict[str, pd.DataFrame]
    publicacoes: list[dict]


def avaliar_rodada(n_nova: int, n_publicada: int, n_rejeitada_antes: int | None, hora: str) -> tuple[bool, str | None]:
    if n_nova >= GUARDA * n_publicada:
        return True, None
    if n_rejeitada_antes is not None and abs(n_nova - n_rejeitada_antes) <= CONFIRMACAO * n_rejeitada_antes:
        return True, f"Queda de volume confirmada em duas rodadas seguidas: {n_nova} linhas (antes {n_publicada})."
    return False, (f"Rodada das {hora} rejeitada: {n_nova} linhas contra {n_publicada} da publicacao anterior "
                   f"(guarda de 85%).")


def base_do_dia(fotos: list[Foto], dia: date) -> Foto | None:
    candidatas = [f for f in fotos if f.dia == dia and f.origem != "reconstruido"]
    return min(candidatas, key=lambda f: (PRIORIDADE[f.origem], f.hora), default=None)


def anterior(fotos: list[Foto], dia: date) -> Foto | None:
    candidatas = [f for f in fotos if f.dia < dia]
    return max(candidatas, key=lambda f: (f.dia, f.hora, -PRIORIDADE[f.origem]), default=None)


def _instante(dia: pd.Timestamp, hora: str) -> pd.Timestamp:
    h, m = map(int, hora.split(":"))
    return dia + pd.Timedelta(hours=h, minutes=m)


def linha_do_tempo(sim: Simulacao) -> LinhaDoTempo:
    fontes = (sim.estoque, sim.garantia, sim.veiculo, sim.distribuicao)

    def regra(q: pd.Timestamp, fracao: float = 1.0, **kw) -> pd.DataFrame:
        return montar_painel(agenda_em(sim, q, fracao), *fontes, quando=q, **kw)

    fotos: list[Foto] = []
    dias = [d for d in pd.date_range(INICIO_HISTORICO, HOJE - pd.Timedelta(days=1)) if d.weekday() != 6]
    for i, d in enumerate(dias):
        hora, origem = ("18:00", "reconstruido") if i < N_RECONSTRUIDOS else ("17:05", "ao_vivo")
        fotos.append(Foto(d.date(), hora, origem, regra(_instante(d, hora))))

    oficiais = {h: regra(_instante(HOJE, h), desempate="acaso", seed=int(h.replace(":", ""))) for h in RECARGAS}
    hoje = HOJE.date()
    publicacoes, publicada, rejeitada = [], len(fotos) - 1, None
    for hora in HORAS_HOJE:
        q = _instante(HOJE, hora)
        avisos = []
        if hora in FALHA:
            rec = max(h for h in RECARGAS if h <= hora)
            fotos.append(Foto(hoje, rec, "oficial", oficiais[rec]))
            publicada = len(fotos) - 1
            avisos.append(f"Rodada das {hora} falhou na via ao vivo: publicada a tabela oficial (dados das {rec}).")
            rejeitada = None
        else:
            df = regra(q, PARCIAL.get(hora, 1.0))
            ok, aviso = avaliar_rodada(len(df), len(fotos[publicada].df), rejeitada, hora)
            if aviso:
                avisos.append(aviso)
            if ok:
                fotos.append(Foto(hoje, hora, "ao_vivo", df))
                publicada, rejeitada = len(fotos) - 1, None
            else:
                rejeitada = len(df)
        existentes = fotos[:]   # só as fotos criadas até "agora"
        base = base_do_dia(existentes, hoje)
        recs = [h for h in RECARGAS if h <= hora]
        conc = None
        if recs:
            rec = recs[-1]
            nosso_q = next(_instante(HOJE, h) for h in HORAS_HOJE if h > rec)
            ag = agenda_em(sim, nosso_q)
            conc = conciliar(montar_painel(ag, *fontes, quando=nosso_q), oficiais[rec], pastas_com_empate(ag))
            conc["recarga"] = rec
        publicacoes.append({"agora": hora, "foto": publicada, "origem": fotos[publicada].origem,
                            "quando": fotos[publicada].hora, "avisos": avisos,
                            "base": fotos.index(base) if base is not None else None,
                            "anterior": fotos.index(anterior(existentes, hoje)), "conciliacao": conc})
    return LinhaDoTempo(fotos, oficiais, publicacoes)
