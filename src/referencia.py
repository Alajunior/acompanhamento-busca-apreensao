"""Referência em Python das agregações do painel (as mesmas de src/agregar.js, escritas de forma independente).

O navegador filtra e agrega no JS; o teste de paridade roda o JS no Node e compara número a número com esta referência.
Regras e limiares: inventário do painel real (seções 2, 3, 5 e 6), resumidos nos comentários.
Ordenações com empate são sempre explícitas (as duas linguagens precisam dar a mesma ordem).
"""
from __future__ import annotations

import math
from datetime import date

ETAPAS = ("EMENDAR INICIAL", "AGUARDANDO LIMINAR", "LIMINAR DEFERIDA", "MANDADO REQUERIDO", "MANDADO EXPEDIDO",
          "MANDADO NEGATIVO")
FASES = ("MANDADO EXPEDIDO", "MANDADO NEGATIVO", "MANDADO REQUERIDO", "EMENDA REALIZADA", "EMENDAR INICIAL",
         "LIMINAR DEFERIDA", "LIMINAR INDEFERIDA", "AGUARDANDO LIMINAR")
DILIGENCIA = "1º MANDADO EXPEDIDO"
TENTATIVAS = ("1º", "2º", "3º", "4º", "5º", "6º+")
FAIXAS_IDADE = ("ate 5 anos", "6-10 anos", "11-15 anos", "16+ anos", "sem ano")
FAIXAS_COBERTURA = ("< 50%", "50-80%", "80-100%", ">= 100%", "sem bem ou risco <= 0")
SEM_ADV, SEM_MARCA, SEM_COMARCA = "(sem advogado)", "(sem marca)", "(sem comarca)"
GRUPOS_FILTRO = ("uf", "carteira", "adv", "etapa", "produto")


# ---------- formatos (iguais aos do JS) ----------

def arred(x: float) -> int:
    return math.floor(x + 0.5)


def fmt_int(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def fmt_rs(v: float) -> str:
    if v >= 1e6:
        return "R$ " + f"{arred(v / 1e5) / 10:.1f}".replace(".", ",") + " mi"
    if v >= 1e3:
        return f"R$ {fmt_int(arred(v / 1e3))} mil"
    return f"R$ {fmt_int(arred(v))}"


def fmt_pct0(fracao: float) -> str:
    return f"{arred(fracao * 100)}%"


def plural(n: int, sing: str, plur: str) -> str:
    return f"{fmt_int(n)} {sing if n == 1 else plur}"


def fase_de(tipo: str) -> str:
    return next((f for f in FASES if f in tipo), "SEM INFO")


def mediana(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


# ---------- estado: fotos decodificadas ----------

def _fotos(payload: dict) -> list[dict[int, tuple]]:
    cache = payload.get("_cache_ref")
    if cache is not None:
        return cache
    out, atual = [], {}
    for f in payload["fotos"]:
        e = f["estado"]
        if isinstance(e, list):
            atual = {i: (t, d) for i, t, d in e}
        else:
            atual = dict(atual)
            for i in e["sai"]:
                atual.pop(i, None)
            for i, t, d in e["muda"]:
                atual[i] = (t, d)
        out.append(atual)
    payload["_cache_ref"] = out
    return out


def _offset(payload: dict, dia_iso: str) -> int:
    return (date.fromisoformat(dia_iso) - date.fromisoformat(payload["hoje"])).days


def linhas(payload: dict, k: int) -> list[dict]:
    """Linhas da foto k: um dict por pasta, com atributos em texto."""
    p, dic = payload["pastas"], payload["dic"]

    def txt(nome, i):
        c = p[nome][i]
        return None if c is None else dic[nome][c]

    out = []
    for i, (t, d) in sorted(_fotos(payload)[k].items()):
        tipo = dic["tipo"][t]
        out.append({"i": i, "pasta": p["pasta"][i], "tipo": tipo, "fase": fase_de(tipo), "data": d,
                    "uf": txt("uf", i), "carteira": txt("carteira", i), "adv": txt("adv", i) or SEM_ADV,
                    "produto": txt("produto", i), "comarca": txt("comarca", i) or SEM_COMARCA,
                    "marca": txt("marca", i) or SEM_MARCA, "risco": p["risco"][i], "bem": p["bem"][i],
                    "ano": p["ano_modelo"][i]})
    return out


def filtrar(rows: list[dict], filtros: dict, payload: dict, sem: str | None = None) -> list[dict]:
    """E entre grupos, OU dentro do grupo; datas inclusivas (absolutas). `sem` ignora um grupo (o mapa ignora a UF)."""
    sel = {g: set(filtros.get(g) or []) for g in GRUPOS_FILTRO if g != sem}
    de = _offset(payload, filtros["de"]) if filtros.get("de") else None
    ate = _offset(payload, filtros["ate"]) if filtros.get("ate") else None
    out = []
    for r in rows:
        if any(v and r[g if g != "etapa" else "fase"] not in v for g, v in sel.items()):
            continue
        if de is not None or ate is not None:
            if r["data"] is None or (de is not None and r["data"] < de) or (ate is not None and r["data"] > ate):
                continue
        out.append(r)
    return out


# ---------- cards ----------

def kpis(rows: list[dict], h: int) -> dict:
    return {"processos": len(rows), "diligencia": sum(r["tipo"] == DILIGENCIA for r in rows),
            "vencidos": sum(r["data"] is not None and r["data"] < h for r in rows),
            "hoje": sum(r["data"] == h for r in rows),
            "prox7": sum(r["data"] is not None and h < r["data"] <= h + 7 for r in rows),
            "risco": sum(r["risco"] for r in rows if r["risco"] is not None)}


def _contar(rows, chave) -> dict:
    c: dict = {}
    for r in rows:
        k = chave(r)
        c[k] = c.get(k, 0) + 1
    return c


def tabelas(rows: list[dict], ordem_follow: list[str]) -> dict:
    prod = _contar(rows, lambda r: r["tipo"])
    fol = _contar(rows, lambda r: r["fase"])
    conhecidas = [f for f in ordem_follow if fol.get(f)]
    outras = sorted(f for f in fol if f not in ordem_follow)
    dil = sum(r["tipo"] == DILIGENCIA for r in rows)
    return {"produtivos": [[t, prod[t]] for t in sorted(prod)],
            "follow": [[f, fol[f]] for f in conhecidas + outras],
            "diligencia": [[DILIGENCIA, dil]] if dil else []}


def _tentativa(tipo: str) -> tuple[str, str] | None:
    partes = tipo.split(" MANDADO ")
    if len(partes) != 2:
        return None
    rot = "6º+" if partes[0] == "6º OU +" else partes[0]
    return (rot, partes[1]) if rot in TENTATIVAS and partes[1] in ("EXPEDIDO", "NEGATIVO", "REQUERIDO") else None


def escada(rows: list[dict]) -> dict | None:
    m = {(t, s): 0 for t in TENTATIVAS for s in ("REQUERIDO", "EXPEDIDO", "NEGATIVO")}
    for r in rows:
        k = _tentativa(r["tipo"])
        if k:
            m[k] += 1
    total = sum(m.values())
    if not total:
        return None
    out, restantes = [], total
    for t in TENTATIVAS:
        tot = m[(t, "REQUERIDO")] + m[(t, "EXPEDIDO")] + m[(t, "NEGATIVO")]
        out.append({"tentativa": t, "REQUERIDO": m[(t, "REQUERIDO")], "EXPEDIDO": m[(t, "EXPEDIDO")],
                    "NEGATIVO": m[(t, "NEGATIVO")], "total": tot, "chegou": restantes / total * 100})
        restantes -= tot
    return {"linhas": out, "em_mandado": total}


def prazos(rows: list[dict], h: int) -> list[list]:
    out = []
    for e in ETAPAS:
        rs = [r for r in rows if r["fase"] == e]
        if not rs:
            continue
        d = [r["data"] for r in rs]
        out.append([e, sum(x is not None and x < h for x in d), sum(x == h for x in d),
                    sum(x is not None and h < x <= h + 7 for x in d), sum(x is not None and x > h + 7 for x in d),
                    sum(x is None for x in d)])
    return out


def advogados(rows: list[dict], h: int) -> dict:
    por: dict[str, list[dict]] = {}
    for r in rows:
        por.setdefault(r["adv"], []).append(r)
    linhas_ = []
    for adv in sorted(por, key=lambda a: (a == SEM_ADV, a)):
        rs = por[adv]
        venc = sum(r["data"] is not None and r["data"] < h for r in rs)
        linhas_.append({"adv": adv, "processos": len(rs), "vencidos": venc, "hoje": sum(r["data"] == h for r in rs),
                        "risco": sum(r["risco"] for r in rs if r["risco"] is not None),
                        "etapas": [sum(r["fase"] == e for r in rs) for e in ETAPAS],
                        "pct_venc": venc / len(rs) * 100})
    tot_p = sum(x["processos"] for x in linhas_)
    pct_cart = (sum(x["vencidos"] for x in linhas_) / tot_p * 100) if tot_p else None
    comp = [x for x in linhas_ if x["adv"] != SEM_ADV and x["processos"] >= 30]
    med = mediana([x["processos"] for x in comp]) if len(comp) >= 3 else None
    for x in linhas_:
        e_comp = x["adv"] != SEM_ADV and x["processos"] >= 30
        x["razao"] = x["processos"] / med if (med and e_comp) else None
        x["carga_alta"] = bool(med and e_comp and x["processos"] / med >= 1.25)
        x["venc_alto"] = bool(e_comp and pct_cart is not None and x["pct_venc"] >= pct_cart + 10)
    return {"linhas": linhas_, "mediana": med, "n_comparaveis": len(comp), "pct_carteira": pct_cart}


def mapa_uf(rows: list[dict]) -> dict:
    m: dict[str, list] = {}
    for r in rows:
        if r["uf"] is None:
            continue
        x = m.setdefault(r["uf"], [0, 0.0, 0])
        x[0] += 1
        x[1] += r["risco"] or 0.0
        x[2] += r["fase"] == "MANDADO NEGATIVO"
    return {k: m[k] for k in sorted(m)}


def _faixa_idade(ano) -> str:
    if ano is None:
        return "sem ano"
    idade = 2026 - ano
    if idade < -1 or idade > 60:
        return "sem ano"
    return "ate 5 anos" if idade <= 5 else "6-10 anos" if idade <= 10 else "11-15 anos" if idade <= 15 else "16+ anos"


def _top(contagem: dict, n: int | None) -> list[list]:
    itens = sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[k, v] for k, v in (itens if n is None else itens[:n])]


def perfil(rows: list[dict], n_marcas: int = 10) -> dict:
    prod = _contar(rows, lambda r: r["produto"] or "(sem produto)")
    idade = _contar(rows, lambda r: _faixa_idade(r["ano"]))
    marcas = _contar(rows, lambda r: r["marca"])
    top = _top(marcas, n_marcas)
    demais = len(rows) - sum(v for _, v in top)
    return {"base": sum(idade.values()), "produto": _top(prod, None),
            "idade": [[f, idade[f]] for f in FAIXAS_IDADE if idade.get(f)],
            "marcas": top + ([["(demais marcas)", demais]] if demais > 0 else [])}


def comarcas(rows: list[dict], n: int) -> list[list]:
    por: dict[str, list[dict]] = {}
    for r in rows:
        por.setdefault(r["comarca"], []).append(r)
    out = []
    for nome, rs in sorted(por.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:n]:
        ufs = _contar([r for r in rs if r["uf"]], lambda r: r["uf"])
        uf = min(ufs, key=lambda u: (-ufs[u], u)) if ufs else None
        out.append([nome, uf, len(rs), sum(r["fase"] == "MANDADO NEGATIVO" for r in rs) / len(rs) * 100])
    return out


def _pct(n: int, base: int) -> float | None:
    return n / base * 100 if base else None


def resumo_regiao(rows: list[dict], h: int) -> dict:
    k = kpis(rows, h)
    n = k["processos"]
    riscos = [r["risco"] for r in rows if r["risco"] is not None]
    neg = sum(r["fase"] == "MANDADO NEGATIVO" for r in rows)
    advs = _contar([r for r in rows if r["adv"] != SEM_ADV], lambda r: r["adv"])
    mais = min(advs, key=lambda a: (-advs[a], a)) if advs else None
    return {"kpis": k, "pct": {c: _pct(k[c], n) for c in ("vencidos", "hoje", "prox7", "diligencia")},
            "negativo": neg, "pct_negativo": _pct(neg, n), "risco_medio": sum(riscos) / len(riscos) if riscos else None,
            "etapas": [[e, sum(r["fase"] == e for r in rows)] for e in ETAPAS], "perfil": perfil(rows, 5),
            "comarcas": comarcas(rows, 5),
            "advogados": {"qtd": len(advs), "sem_advogado": sum(r["adv"] == SEM_ADV for r in rows),
                          "mais": [mais, advs[mais], advs[mais] / n * 100] if mais else None}}


def regioes(rows_sem_uf: list[dict], ufs: list[str], h: int) -> dict | None:
    if not ufs:
        return None
    brasil = resumo_regiao(rows_sem_uf, h)
    out = []
    for uf in sorted(ufs):
        r = resumo_regiao([x for x in rows_sem_uf if x["uf"] == uf], h)
        r["uf"] = uf
        r["part_processos"] = _pct(r["kpis"]["processos"], brasil["kpis"]["processos"])
        r["part_risco"] = (r["kpis"]["risco"] / brasil["kpis"]["risco"] * 100) if brasil["kpis"]["risco"] else None
        out.append(r)
    return {"modo": 1 if len(ufs) == 1 else 2 if len(ufs) <= 4 else 5, "ufs": out, "brasil": brasil}


def movimentacao(payload: dict, pub: dict, filtros: dict) -> dict:
    if pub["origem"] == "oficial":
        return {"vazia": "oficial"}
    if pub["base"] is None:
        return {"vazia": "sem_base"}
    if pub["base"] == pub["foto"]:
        return {"vazia": "base"}
    base = {r["i"]: r for r in filtrar(linhas(payload, pub["base"]), filtros, payload)}
    atual = {r["i"]: r for r in filtrar(linhas(payload, pub["foto"]), filtros, payload)}
    entradas = sorted(set(atual) - set(base))
    saidas = sorted(set(base) - set(atual))
    comuns = sorted(set(atual) & set(base))
    mud_tipo = [i for i in comuns if atual[i]["tipo"] != base[i]["tipo"]]
    trans: dict[tuple, int] = {}
    for i in mud_tipo:
        k = (base[i]["tipo"], atual[i]["tipo"])
        trans[k] = trans.get(k, 0) + 1
    pasta = payload["pastas"]["pasta"]
    return {"entradas": len(entradas), "saidas": len(saidas), "mud_agendamento": len(mud_tipo),
            "mud_etapa": sum(atual[i]["fase"] != base[i]["fase"] for i in comuns),
            "transicoes": [[a, b, n] for (a, b), n in sorted(trans.items(), key=lambda kv: (-kv[1], kv[0]))],
            "movimentos": [["entrada", pasta[i]] for i in entradas] + [["saida", pasta[i]] for i in saidas]
                          + [["mudou de tipo", pasta[i]] for i in mud_tipo]}


def risco_etapa(rows: list[dict]) -> dict:
    lin = []
    for e in ETAPAS:
        rs = [r for r in rows if r["fase"] == e]
        if rs:
            lin.append([e, len(rs), sum(r["risco"] or 0.0 for r in rs), sum(r["bem"] or 0.0 for r in rs)])
    cob = [r["bem"] / r["risco"] for r in rows if r["risco"] is not None and r["risco"] > 0 and r["bem"] is not None]
    med = mediana(cob)
    return {"linhas": lin, "risco_total": sum(r["risco"] or 0.0 for r in rows),
            "bem_total": sum(r["bem"] or 0.0 for r in rows), "cobertura_mediana": med * 100 if med is not None else None,
            "sem_estoque": sum(r["risco"] is None for r in rows)}


def _faixa_cobertura(r: dict) -> str | None:
    if r["risco"] is None:
        return None
    if r["risco"] <= 0 or r["bem"] is None:
        return "sem bem ou risco <= 0"
    c = r["bem"] / r["risco"]
    return "< 50%" if c < 0.5 else "50-80%" if c < 0.8 else "80-100%" if c < 1.0 else ">= 100%"


def risco_uf(rows: list[dict]) -> dict:
    por: dict[str, list[dict]] = {}
    for r in rows:
        if r["uf"]:
            por.setdefault(r["uf"], []).append(r)
    lin = []
    for uf, rs in por.items():
        risco = sum(r["risco"] or 0.0 for r in rs)
        bem = sum(r["bem"] or 0.0 for r in rs)
        lin.append([uf, len(rs), risco, bem, bem / risco * 100 if risco else None])
    lin.sort(key=lambda x: (-x[2], x[0]))
    faixas = _contar([r for r in rows if _faixa_cobertura(r)], _faixa_cobertura)
    return {"linhas": lin, "faixas": [[f, faixas.get(f, 0)] for f in FAIXAS_COBERTURA]}


def carteira_etapa(rows: list[dict]) -> dict:
    carts = sorted({r["carteira"] for r in rows if r["carteira"]})
    qtd = [[sum(r["carteira"] == c and r["fase"] == e for r in rows) for e in ETAPAS] for c in carts]
    risco = [[sum(r["risco"] or 0.0 for r in rows if r["carteira"] == c and r["fase"] == e) for e in ETAPAS] for c in carts]
    return {"carteiras": carts, "etapas": list(ETAPAS), "qtd": qtd, "risco": risco}


IMPACTOS = {
    "liminar_deferida": "É a etapa imediatamente anterior ao pedido de mandado: priorizar esses requerimentos tende a "
                        "encurtar o caminho até a diligência.",
    "vencidos": "Agendamento vencido sem andamento pode atrasar a etapa seguinte do processo.",
    "escada": "Cada nova tentativa consome diligência e prazo; vale revisar endereço ou estratégia desses casos.",
    "uf_negativo": "A concentração pode indicar gargalo local (endereço, comarca ou diligência) — vale checar com o "
                   "escritório.",
}


def destaques(rows: list[dict], h: int) -> list[dict]:
    if not rows:
        return []
    out = []
    lim = [r for r in rows if r["fase"] == "LIMINAR DEFERIDA"]
    if lim:
        venc = sum(r["data"] is not None and r["data"] < h for r in lim)
        out.append(("liminar_deferida",
                    f"{plural(len(lim), 'processo', 'processos')} com liminar deferida aguardando requerimento de mandado "
                    f"({fmt_rs(sum(r['risco'] or 0.0 for r in lim))} em risco). {fmt_int(venc)} deles com data de "
                    f"agendamento já vencida."))
    k = kpis(rows, h)
    if k["vencidos"]:
        adv = advogados(rows, h)
        eleg = [x["vencidos"] / x["processos"] for x in adv["linhas"] if x["adv"] != SEM_ADV and x["processos"] >= 30]
        y = max(eleg) if eleg else 0
        cauda = f"; entre advogados com 30+ processos, a maior proporção de vencidos é {fmt_pct0(y)}." if y > 0 else "."
        out.append(("vencidos", f"{plural(k['vencidos'], 'agendamento vencido', 'agendamentos vencidos')} "
                                f"({fmt_pct0(k['vencidos'] / k['processos'])} da carteira filtrada){cauda}"))
    esc = escada(rows)
    if esc and esc["em_mandado"] >= 20:
        n3 = sum(x["total"] for x in esc["linhas"][2:])
        if n3:
            out.append(("escada", f"{plural(n3, 'processo', 'processos')} ({fmt_pct0(n3 / esc['em_mandado'])} dos que estão "
                                  f"em mandado) já passaram da 2ª tentativa."))
    mapa = mapa_uf(rows)
    tq = sum(v[0] for v in mapa.values())
    if tq:
        geral = sum(v[2] for v in mapa.values()) / tq * 100
        cands = [(v[2] / v[0] * 100, uf) for uf, v in mapa.items() if v[0] >= 30]
        if cands:
            pct, uf = min(cands, key=lambda c: (-c[0], c[1]))
            if pct - geral >= 10:
                out.append(("uf_negativo", f"{uf}: {arred(pct)}% dos processos da UF estão em mandado negativo, contra "
                                           f"{arred(geral)}% no total."))
    return [{"chave": c, "achado": a, "impacto": IMPACTOS[c]} for c, a in out]


def evolucao(payload: dict, pub: dict, filtros: dict) -> dict:
    fotos = payload["fotos"]
    ultima: dict[str, int] = {}
    for k, f in enumerate(fotos):
        if f["dia"] == payload["hoje"]:
            continue
        if f["dia"] not in ultima or f["hora"] >= fotos[ultima[f["dia"]]]["hora"]:
            ultima[f["dia"]] = k
    ultima[payload["hoje"]] = pub["foto"]
    dias = sorted(ultima)
    d0, d1 = date.fromisoformat(dias[0]), date.fromisoformat(dias[-1])
    out = {"dias": [], "lacuna": [], "reconstruido": [], "total": [], "por_etapa": {e: [] for e in ETAPAS}, "extintas": []}
    for n in range((d1 - d0).days + 1):
        d = date.fromordinal(d0.toordinal() + n).isoformat()
        out["dias"].append(d)
        if d not in ultima:
            out["lacuna"].append(True)
            out["reconstruido"].append(False)
            out["total"].append(None)
            out["extintas"].append(None)
            for e in ETAPAS:
                out["por_etapa"][e].append(None)
            continue
        k = ultima[d]
        rs = filtrar(linhas(payload, k), filtros, payload)
        out["lacuna"].append(False)
        out["reconstruido"].append(fotos[k]["origem"] == "reconstruido")
        out["total"].append(len(rs))
        out["extintas"].append(sum(r["fase"] == "EMENDA REALIZADA" for r in rs))
        for e in ETAPAS:
            out["por_etapa"][e].append(sum(r["fase"] == e for r in rs))
    return out


def tudo(payload: dict, agora: str, filtros: dict) -> dict:
    pub = next(p for p in payload["publicacoes"] if p["agora"] == agora)
    fotos = payload["fotos"]
    todas = linhas(payload, pub["foto"])
    rows = filtrar(todas, filtros, payload)
    sem_uf = filtrar(todas, filtros, payload, sem="uf")

    def ref(k):
        if k is None:
            return None
        h = _offset(payload, fotos[k]["dia"])
        return {"kpis": kpis(filtrar(linhas(payload, k), filtros, payload), h), "dia": fotos[k]["dia"],
                "hora": fotos[k]["hora"], "origem": fotos[k]["origem"]}

    return {"kpis": {"atual": kpis(rows, 0), "inicio": ref(pub["base"]), "anterior": ref(pub["anterior"])},
            "tabelas": tabelas(rows, payload["ordens"]["follow"]), "escada": escada(rows), "prazos": prazos(rows, 0),
            "advogados": advogados(rows, 0), "mapa_uf": mapa_uf(sem_uf),
            "regioes": regioes(sem_uf, list(filtros.get("uf") or []), 0),
            "movimentacao": movimentacao(payload, pub, filtros), "destaques": destaques(rows, 0),
            "risco_etapa": risco_etapa(rows), "risco_uf": risco_uf(rows), "carteira_etapa": carteira_etapa(rows),
            "comarcas": comarcas(rows, 15), "perfil": perfil(rows, 10), "evolucao": evolucao(payload, pub, filtros)}
