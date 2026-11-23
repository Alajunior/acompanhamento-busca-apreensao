"""Capturas de placa → resumo do localizado e padrões de circulação por pasta (inv. §7).

Descreve o que se repetiu nas capturas dos últimos 60 dias; não é previsão. Calculado uma vez por carga de
capturas (os horários do "agora"); o navegador só filtra, agrega e desenha.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

import numpy as np
import pandas as pd

from dados.gerar import HOJE, Simulacao

ESTADOS = ("PADRAO_OBSERVADO", "PADRAO_EM_FORMACAO", "APRENDENDO", "SEM_CAPTURA_RECENTE", "SEM_CAPTURA", "SEM_PLACA")
ROTULOS = {"PADRAO_OBSERVADO": "Padrão observado", "PADRAO_EM_FORMACAO": "Padrão em formação",
           "APRENDENDO": "Aprendendo padrão", "SEM_CAPTURA_RECENTE": "Sem captura recente", "SEM_CAPTURA": "Sem captura",
           "SEM_PLACA": "Sem placa"}
CORES = {"PADRAO_OBSERVADO": "#D55E00", "PADRAO_EM_FORMACAO": "#E69F00", "APRENDENDO": "#0072B2",
         "SEM_CAPTURA_RECENTE": "#9AA4B2", "SEM_CAPTURA": "#5B6472", "SEM_PLACA": "#5B6472"}
SUGESTAO = {"MANDADO EXPEDIDO": "Informar o local ao oficial de justiça",
            "MANDADO NEGATIVO": "Pedir novo mandado com o endereço da captura",
            "LIMINAR DEFERIDA": "Pedir o mandado já indicando o endereço",
            "MANDADO REQUERIDO": "Reforçar o pedido com a localização",
            "AGUARDANDO LIMINAR": "Juntar a localização ao processo",
            "EMENDAR INICIAL": "Juntar a localização ao processo"}
AGORAS = ("07:05", "09:05", "11:05", "13:05", "15:05", "17:05")
FALHA = "15:05"                       # leitura de capturas encenada como falha: repete a carga anterior
CELULA = 0.003                        # ~330 m
JANELA_DIAS = 60
MAX_LETRAS = 8
MAX_TRAJETOS = 12
TRAJETO_MAX_H = 3
RAIO_UNICO_KM = 0.3
NULOS = {"", "undefined", "null", "none", "nan", "vazio"}
TEXTOS = ["STREET", "STREET_NUMBER", "POSTAL_CODE", "LOCALITY", "CITY", "STATE", "COMPANY_NAME", "STORAGE_PATH"]


# ---------- preparação ----------

def normalizar_placa(s) -> str | None:
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return None
    p = re.sub(r"[^A-Z0-9]", "", str(s).upper())
    return p if len(p) == 7 else None


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _txt(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return None
    t = str(v).strip()
    return None if t.lower() in NULOS else t


def preparar(cap: pd.DataFrame) -> pd.DataFrame:
    df = cap.drop_duplicates(["PLATE", "CAPTURED", "DEVICE_NAME", "STORAGE_PATH"]).copy()
    for c in TEXTOS:
        df[c] = pd.Series([_txt(v) for v in df[c]], index=df.index, dtype=object)
    df["placa_n"] = [normalizar_placa(v) for v in df["PLATE"]]
    df["quando"] = pd.to_datetime(df["CAPTURED"], errors="coerce")
    df["lat_n"] = pd.to_numeric(df["LATITUDE"], errors="coerce")
    df["lon_n"] = pd.to_numeric(df["LONGITUDE"], errors="coerce")
    df["cidade_n"] = [None if c is None else re.sub(r"\s+", " ", _sem_acento(c).upper()) for c in df["CITY"]]
    df["uf_n"] = [None if u is None else re.sub(r"\s+", "", u.upper()) for u in df["STATE"]]
    ok = (df["placa_n"].notna() & df["quando"].notna() & df["lat_n"].notna() & df["lon_n"].notna()
          & ~((df["lat_n"] == 0) & (df["lon_n"] == 0)))
    return df[ok].sort_values(["quando", "IDPLACAS"], kind="stable").reset_index(drop=True)


# ---------- padrões ----------

def celula(lat: float, lon: float) -> tuple[int, int]:
    return round(lat / CELULA), round(lon / CELULA)


def faixa_2h(horas: list[int]) -> int:
    """Hora inicial da janela circular (h, h+1) com mais passagens; empate → começa em hora com passagem → mais cedo."""
    c = Counter(horas)
    return min(range(24), key=lambda h: (-(c[h] + c[(h + 1) % 24]), c[h] == 0, h))


def rotulo_faixa(h: int) -> str:
    return f"{h}h–{(h + 2) % 24}h"


def _chave_peso(c: dict):
    return (-c["dias"], -c["passagens"], -c["ultima"].value, c["id"])


def principal(cels: list[dict]) -> dict | None:
    return min(cels, key=_chave_peso) if cels else None


def estado_de(dias: int | None, templaca_n: bool, tem_captura: bool) -> str:
    if not templaca_n:
        return "SEM_PLACA"
    if not tem_captura:
        return "SEM_CAPTURA"
    if not dias:
        return "SEM_CAPTURA_RECENTE"
    return "PADRAO_OBSERVADO" if dias >= 6 else "PADRAO_EM_FORMACAO" if dias >= 4 else "APRENDENDO"


def sequencia(cels: list[dict]) -> list[dict]:
    """Os 8 pontos de maior peso com 2+ dias, ordenados pelo horário. Principal de 1 dia: nenhum ponto tem letra."""
    fortes = sorted([c for c in cels if c["dias"] >= 2], key=_chave_peso)[:MAX_LETRAS]
    seq = sorted(fortes, key=lambda c: (c["faixa"], c["hora_tipica"], c["id"]))
    return [c | {"letra": chr(65 + k)} for k, c in enumerate(seq)]


def trajetos(caps: pd.DataFrame, cels: list[dict]) -> list[dict]:
    """Capturas seguidas (por instante) em células diferentes e com até 3 h entre elas, agrupadas por origem → destino.
    `de`/`para` são índices em `cels`. Liga as câmeras; não é o caminho pelas ruas."""
    idx = {c["id"]: i for i, c in enumerate(cels)}
    grupos: dict[tuple, list] = {}
    ant = None
    for r in caps.itertuples(index=False):
        atual = (celula(r.lat_n, r.lon_n), r.quando)
        if ant is not None and ant[0] != atual[0] and atual[1] - ant[1] <= pd.Timedelta(hours=TRAJETO_MAX_H):
            grupos.setdefault((ant[0], atual[0]), []).append((ant[1], atual[1]))
        ant = atual
    out = []
    for (a, b), pares in grupos.items():
        dias = len({s.normalize() for s, _ in pares})
        ca, cb = cels[idx[a]], cels[idx[b]]
        out.append({"de": idx[a], "para": idx[b], "dias": dias, "passagens": len(pares),
                    "minutos": int(round(float(np.median([(t - s).total_seconds() / 60 for s, t in pares])))),
                    "faixa": faixa_2h([s.hour for s, _ in pares]),
                    "km": round(haversine(ca["lat"], ca["lon"], cb["lat"], cb["lon"]), 1), "recorrente": dias >= 2,
                    "_ids": (a, b)})
    out.sort(key=lambda t: (not t["recorrente"], -t["dias"], -t["passagens"], t["minutos"], t["_ids"]))
    return [{k: v for k, v in t.items() if k != "_ids"} for t in out[:MAX_TRAJETOS]]


def _local_curto(e: dict) -> str:
    return e.get("bairro") or e.get("cidade") or "local não informado"


def texto_sequencia(seq: list[dict]) -> str | None:
    if len(seq) < 2:
        return None
    partes = [f"{s['letra']} ({_local_curto(s['endereco'])}, {rotulo_faixa(s['faixa'])})" for s in seq]
    return "Costuma aparecer em " + ", depois em ".join(partes) + "."


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def area_km(pontos: list[tuple[float, float]]) -> tuple[list[tuple[float, float]], float]:
    """Envoltória convexa (cadeia monótona, em lon×lat) e a maior distância haversine entre seus vértices."""
    pts = sorted(set(pontos), key=lambda p: (p[1], p[0]))
    if len(pts) == 1:
        return pts, RAIO_UNICO_KM

    def cruz(o, a, b):
        return (a[1] - o[1]) * (b[0] - o[0]) - (a[0] - o[0]) * (b[1] - o[1])

    baixo, cima = [], []
    for p in pts:
        while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], p) <= 1e-12:
            baixo.pop()
        baixo.append(p)
    for p in reversed(pts):
        while len(cima) >= 2 and cruz(cima[-2], cima[-1], p) <= 1e-12:
            cima.pop()
        cima.append(p)
    vert = baixo[:-1] + cima[:-1]
    km = max(haversine(a[0], a[1], b[0], b[1]) for i, a in enumerate(vert) for b in vert[i + 1:])
    return vert, round(km, 2)


def endereco_banco(end_cpf: pd.DataFrame) -> dict | None:
    if end_cpf.empty:
        return None
    res = end_cpf[end_cpf["TIPO"].astype(str).str.upper().str.startswith("RESIDENC")]
    base = res if not res.empty else end_cpf
    return base.sort_values("DATA_CADASTRO", kind="stable").iloc[-1].to_dict()


def perto_de_casa(cep_ponto, cep_banco) -> bool:
    a, b = (re.sub(r"\D", "", str(x)) if x else "" for x in (cep_ponto, cep_banco))
    return len(a) == 8 and len(b) == 8 and a[:5] == b[:5]


def _endereco(r) -> dict:
    return {"rua": r.STREET, "numero": r.STREET_NUMBER, "bairro": r.LOCALITY, "cidade": r.cidade_n, "uf": r.uf_n,
            "cep": r.POSTAL_CODE}


def rotulo_local(e: dict) -> str:
    """"bairro, CIDADE/UF" (sem bairro: "CIDADE/UF"; sem nada: "local não informado")."""
    cid = "/".join(x for x in (e.get("cidade"), e.get("uf")) if x)
    return ", ".join(x for x in (e.get("bairro"), cid) if x) or "local não informado"


def celulas(caps: pd.DataFrame) -> list[dict]:
    """Uma entrada por célula de ~330 m, com as capturas da janela (já filtradas)."""
    out = []
    grupos: dict[tuple, list] = {}
    for r in caps.itertuples(index=False):
        grupos.setdefault(celula(r.lat_n, r.lon_n), []).append(r)
    for cid, rs in grupos.items():
        quando = [r.quando for r in rs]
        horas = [q.hour for q in quando]
        semana, hist = [0] * 7, [0] * 24
        for q in quando:
            semana[q.weekday()] += 1
            hist[q.hour] += 1
        ends = Counter()
        ultimo_de = {}
        for r in rs:
            e = _endereco(r)
            k = tuple(e.values())
            ends[k] += 1
            ultimo_de[k] = max(ultimo_de.get(k, r.quando), r.quando)
        k_end = max(ends, key=lambda k: (ends[k], ultimo_de[k]))
        out.append({"id": cid, "lat": float(np.median([r.lat_n for r in rs])), "lon": float(np.median([r.lon_n for r in rs])),
                    "passagens": len(rs), "dias": len({q.normalize() for q in quando}),
                    "hora_tipica": float(np.median([q.hour + q.minute / 60 for q in quando])),
                    "primeira": min(quando), "ultima": max(quando), "semana": semana, "horas": hist,
                    "faixa": faixa_2h(horas), "endereco": dict(zip(("rua", "numero", "bairro", "cidade", "uf", "cep"), k_end))})
    return out


def _pasta(caps: pd.DataFrame, instante: pd.Timestamp, banco: dict | None) -> dict:
    """Resumo e detalhe de uma pasta com as capturas ≤ instante (caps já ordenadas e com pelo menos 1 linha)."""
    q = caps["quando"]
    ult = caps.iloc[-1]
    e_ult = _endereco(ult)
    janela = caps[q > instante - pd.Timedelta(days=JANELA_DIAS)]
    cels = sorted(celulas(janela), key=_chave_peso)
    pp = principal(cels)
    est = estado_de(pp["dias"] if pp else None, True, True)
    seq = sequencia(cels)
    letra = {s["id"]: s["letra"] for s in seq}
    area = None
    if est == "APRENDENDO":
        vert, km = area_km(list(zip(janela["lat_n"], janela["lon_n"])))
        area = {"vertices": [list(v) for v in vert], "km": km}
    semana, horas = [0] * 7, [0] * 24
    for t in janela["quando"]:
        semana[t.weekday()] += 1
        horas[t.hour] += 1
    resumo = {"n": len(caps), "n7": int((q > instante - pd.Timedelta(days=7)).sum()),
              "n30": int((q > instante - pd.Timedelta(days=30)).sum()), "ult": ult["quando"],
              "loc": (e_ult["cidade"], e_ult["uf"], e_ult["bairro"]), "estado": est,
              "dias": pp["dias"] if pp else None, "principal": rotulo_local(pp["endereco"]) if pp else None,
              "passagens_janela": len(janela), "passagens_principal": pp["passagens"] if pp else None}
    detalhe = {
        "ultima": e_ult | {"quando": ult["quando"], "lat": float(ult["lat_n"]), "lon": float(ult["lon_n"]),
                           "empresa": ult["COMPANY_NAME"], "storage": ult["STORAGE_PATH"]},
        "pontos": [{"letra": letra.get(c["id"]), "lat": c["lat"], "lon": c["lon"], "dias": c["dias"],
                    "passagens": c["passagens"], "faixa": rotulo_faixa(c["faixa"]), "ultima": c["ultima"],
                    "endereco": c["endereco"], "principal": c is pp} for c in cels],
        "trajetos": trajetos(janela, cels),
        "sequencia": texto_sequencia(seq), "area": area, "semana": semana, "horas": horas,
        "ultimas": [[t, rotulo_local(_endereco(r))] for t, r in zip(caps["quando"].iloc[::-1][:20], caps.iloc[::-1][:20].itertuples(index=False))],
        "perto_de_casa": bool(pp and banco and perto_de_casa(pp["endereco"]["cep"], banco.get("CEP"))),
    }
    return {"resumo": resumo, "detalhe": detalhe}


def carga(prep: pd.DataFrame, info: pd.DataFrame, end: pd.DataFrame, instante: pd.Timestamp) -> dict[str, dict]:
    """pasta → {resumo, detalhe}, só para pastas com placa válida e alguma captura ≤ instante.
    `info`: PASTA, PLACA, UF, CPF (uma linha por pasta)."""
    caps = prep[prep["quando"] <= instante]
    porplaca_n = {p: g for p, g in caps.groupby("placa_n", sort=False)}
    bancos = _bancos(end)
    out = {}
    for pasta, placa, cpf in zip(info["PASTA"], info["PLACA"], info["CPF"]):
        g = porplaca_n.get(normalizar_placa(placa))
        if g is not None:
            out[pasta] = _pasta(g, instante, bancos.get(cpf))
    return out


def _bancos(end: pd.DataFrame) -> dict:
    return {cpf: endereco_banco(g) for cpf, g in end.groupby("CPF", sort=False)} if len(end) else {}


def info_pastas(sim: Simulacao) -> pd.DataFrame:
    gar = sim.garantia.drop_duplicates("CARTEIRA_CONTRATO").set_index("CARTEIRA_CONTRATO")["PLACA"]
    cpf = sim.estoque.drop_duplicates("CONTRATO").set_index("CONTRATO")["CPF"]
    p = sim.pastas[["PASTA", "UF"]]
    return p.assign(PLACA=p["PASTA"].map(gar), CPF=p["PASTA"].map(cpf)).reset_index(drop=True)


_cache: dict = {}


def cargas(sim: Simulacao, seed: int = 42) -> list[dict]:
    """As 6 cargas do dia simulado. Incremental: só recalcula a pasta cujas capturas (na janela, em 7 e 30 dias) mudaram."""
    chave = (id(sim), seed)
    if chave in _cache:
        return _cache[chave][1]
    from dados.capturas import capturas, enderecos
    prep = preparar(capturas(sim, seed))
    inf = info_pastas(sim)
    inf = inf[inf["PLACA"].map(normalizar_placa).isin(set(prep["placa_n"]))]
    bancos = _bancos(enderecos(sim, seed))
    grupos = {p: g.reset_index(drop=True) for p, g in prep.groupby("placa_n", sort=False)}
    out, anterior, assin_ant = [], {}, {}
    for agora in AGORAS:
        instante = HOJE + pd.Timedelta(hours=int(agora[:2]), minutes=int(agora[3:]))
        if agora == FALHA:
            out.append(out[-1] | {"agora": agora, "falhou": True})
            continue
        atual, assin = {}, {}
        for pasta, placa, cpf in zip(inf["PASTA"], inf["PLACA"], inf["CPF"]):
            g = grupos[normalizar_placa(placa)]
            q = g["quando"].to_numpy()
            fim = int(np.searchsorted(q, np.datetime64(instante), side="right"))
            if fim == 0:
                continue
            a = (fim, *(int(np.searchsorted(q, np.datetime64(instante - pd.Timedelta(days=d)), side="right"))
                        for d in (JANELA_DIAS, 30, 7)))
            atual[pasta] = anterior[pasta] if assin_ant.get(pasta) == a else _pasta(g.iloc[:fim], instante, bancos.get(cpf))
            assin[pasta] = a
        ate = max((v["resumo"]["ult"] for v in atual.values()), default=None)
        out.append({"agora": agora, "instante": instante, "ate": ate, "falhou": False, "pastas": atual})
        anterior, assin_ant = atual, assin
    _cache.clear()
    _cache[chave] = (sim, out)
    return out


def bancos_por_pasta(sim: Simulacao, seed: int = 42) -> dict[str, dict]:
    """Endereço do banco de cada pasta (por CPF), para a aba Padroes, inclusive das pastas sem captura."""
    from dados.capturas import enderecos
    b = _bancos(enderecos(sim, seed))
    inf = info_pastas(sim)
    return {p: b[c] for p, c in zip(inf["PASTA"], inf["CPF"]) if c in b and b[c] is not None}


# ---------- apreendidos com captura antes ----------

COM_CAPTURA = ("PADRAO_OBSERVADO", "PADRAO_EM_FORMACAO", "APRENDENDO")


def apreendidos_com_captura(prep: pd.DataFrame, aps: pd.DataFrame) -> dict:
    """Para cada apreensão (PASTA, PLACA, DT_APREENSAO = data real do fato, UF, ADVOGADO, LOCALIZADOR), o padrão de circulação
    calculado só com as capturas até o fim do dia da apreensão, como se o "agora" fosse esse instante."""
    porplaca = {p: g for p, g in prep.groupby("placa_n", sort=False)}
    itens = []
    for r in aps.itertuples(index=False):
        dt, placa = pd.Timestamp(r.DT_APREENSAO).normalize(), normalizar_placa(r.PLACA)
        it = {"pasta": r.PASTA, "placa": placa, "dt_apreensao": dt, "uf": _txt(r.UF), "advogado": _txt(r.ADVOGADO) or "(sem advogado)",
              "localizador": _txt(r.LOCALIZADOR), "estado": "SEM_CAPTURA" if placa else "SEM_PLACA", "passagens": None,
              "dias": None, "ultima": None, "dias_antes": None, "lat": None, "lon": None, "local": None, "principal": None,
              "p_lat": None, "p_lon": None}
        fim = dt + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        g = porplaca.get(placa) if placa else None
        g = None if g is None else g[g["quando"] <= fim]
        if g is not None and len(g):
            x = _pasta(g, fim, None)
            rs, d = x["resumo"], x["detalhe"]
            pp = next((p for p in d["pontos"] if p["principal"]), None)
            it |= {"estado": rs["estado"], "passagens": rs["passagens_janela"], "dias": rs["dias"], "ultima": rs["ult"],
                   "dias_antes": int((dt - rs["ult"].normalize()).days), "lat": d["ultima"]["lat"], "lon": d["ultima"]["lon"],
                   "local": rotulo_local(d["ultima"]), "principal": rs["principal"],
                   "p_lat": pp["lat"] if pp else None, "p_lon": pp["lon"] if pp else None}
        itens.append(it)
    itens.sort(key=lambda x: (-x["dt_apreensao"].value, x["pasta"]))
    na = [x for x in itens if x["estado"] in COM_CAPTURA]
    return {"total": len(itens), "com_placa": sum(x["estado"] != "SEM_PLACA" for x in itens),
            "com_captura_antes": sum(x["estado"] not in ("SEM_PLACA", "SEM_CAPTURA") for x in itens), "na_janela": len(na),
            "estados": {e: sum(x["estado"] == e for x in itens) for e in ESTADOS},
            "mediana_dias": float(np.median([x["dias_antes"] for x in na])) if na else None, "itens": itens}


def apreendidos_da_simulacao(sim: Simulacao, seed: int = 42) -> dict:
    """As apreensões da aba Busca e Apreensão (leitura das 17:05) com a placa pela garantia da pasta."""
    from dados.ba import fontes_ba
    from dados.capturas import capturas
    from src.ba_regras import linhas_pasta, localizadores_de
    f = fontes_ba(sim)
    lin = linhas_pasta(f, HOJE + pd.Timedelta(hours=17, minutes=5), localizadores_de(f)[0])
    ap = lin[lin["ETAPA"] == "Apreendido"]
    dt = pd.to_datetime(ap["DT_APREENSAO_REAL"]).fillna(pd.to_datetime(ap["DT_APREENSAO"]))
    placa = sim.garantia.drop_duplicates("CARTEIRA_CONTRATO").set_index("CARTEIRA_CONTRATO")["PLACA"]
    aps = pd.DataFrame({"PASTA": ap["PASTA"], "PLACA": ap["PASTA"].map(placa), "DT_APREENSAO": dt, "UF": ap["UF"],
                        "ADVOGADO": ap["ADVOGADO"], "LOCALIZADOR": ap["LOCALIZADOR"]})
    return apreendidos_com_captura(preparar(capturas(sim, seed)), aps[aps["DT_APREENSAO"].notna()])
