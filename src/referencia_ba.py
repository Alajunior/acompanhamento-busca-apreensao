"""Referência Python da aba Busca e Apreensão (modo Planilha), sobre o docs/ba.json.

Escrita de forma independente do src/ba.js: o teste de paridade roda o JS no Node e compara seção a seção. Números
crus (a formatação fica na tela); linhas de subtotal e total marcadas em "tipo" ("sub" / "total").
"""
from datetime import date, timedelta
from statistics import median

from src.ba_calendario import arred, arred_cima, dias_uteis, du_indice

ETAPAS = ("Apreendido", "Mandado expedido", "Localizado (diligência)", "Localização encerrada sem apreensão")
ABERTAS = ("Mandado expedido", "Localizado (diligência)")
FASES = ("JUDICIAL 1", "JUDICIAL 2", "JUDICIAL 3", "PREJUÍZO")
FAIXAS = (("121 A 360", ("JUDICIAL 1", "JUDICIAL 2")), ("360 A 720", ("JUDICIAL 3",)), ("> 720", ("PREJUÍZO",)))
OUTRAS = "OUTRAS FASES"
QUEBRAS = ("ATÉ DIA 10", "DO DIA 11 AO DIA 20", "DO DIA 21 AO DIA 31")
SEM_LOC = "(sem localizador)"
FATORES = (("100%", 1.0), ("120%", 1.2), ("130%", 1.3))


# ---------------- decodificação ----------------
def _mes_key(m: str) -> tuple[int, int]:
    mm, aa = m.split("/")
    return int(aa), int(mm)


def _hoje(ba: dict) -> date:
    return date.fromisoformat(ba["hoje"])


def _feriados(ba: dict) -> tuple:
    return tuple(date.fromisoformat(d) for d in ba["feriados"])


def _min_iso(base: str, m: int | None) -> str | None:
    if m is None:
        return None
    from datetime import datetime
    return (datetime.fromisoformat(base) + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M")


def estado(ba: dict, agora: str) -> dict:
    k = ba["agoras"].index(agora)
    cols = ba["colunas"]
    lin: dict[str, list] = {}
    for c in ba["cargas"][:k + 1]:
        if "base" in c:
            lin = {r[0]: r for r in c["base"]}
        else:
            for p in c["sai"]:
                lin.pop(p, None)
            for r in c["muda"]:
                lin[r[0]] = r
    pas: dict[str, list] = {}
    for c in ba["passagens"][:k + 1]:
        if "base" in c:
            pas = dict(c["base"])
        else:
            for p in c["sai"]:
                pas.pop(p, None)
            pas.update(c["muda"])
    o = ba["opcoes"]
    from datetime import datetime
    agora_ts = datetime.fromisoformat(f"{ba['hoje']}T{agora}")
    base = ba["base_minutos"]
    passagens = []
    for pasta in sorted(pas):
        for r in pas[pasta]:
            rec = _min_iso(base, r[1])
            ate = _min_iso(base, r[2])
            dias = r[3] if ate is not None else arred((agora_ts - datetime.fromisoformat(rec)) / timedelta(days=1), 1)
            passagens.append({"PASTA": pasta, "LOCALIZADOR": o["localizadores"][r[0]], "RECEBEU": rec, "ATE": ate,
                              "DIAS": dias, "RESULTADO": ba["resultados"][r[4]], "FICHAS": r[5],
                              "UF": None if r[6] is None else o["ufs"][r[6]],
                              "ADVOGADO": None if r[7] is None else o["advogados"][r[7]], "APREENDEU": bool(r[8]),
                              "VALOR_PERFORMANCE": r[9], "DIAS_ATE_LOCALIZAR": r[10],
                              "MES_ENVIO": f"{int(rec[5:7])}/{rec[:4]}"})
    carga = ba["cargas"][k]
    return {"agora": agora, "quando": carga["quando"], "aviso": carga["aviso"],
            "linhas": [dict(zip(cols, lin[p])) for p in sorted(lin)], "passagens": passagens}


# ---------------- recortes ----------------
def _norm(filtros: dict) -> dict:
    f = {k: list(filtros.get(k) or []) for k in ("adv", "fase", "uf", "etapa", "localizador")}
    f["mes"] = filtros.get("mes") or None
    return f


def _ordem_lista(r: dict):
    d = r["DT_LOCALIZACAO"]
    return (ETAPAS.index(r["ETAPA"]), 0 if d else 1, "" if not d else _neg(d), r["PASTA"])


def _neg(d: str) -> str:
    """Chave que ordena datas ISO da mais recente para a mais antiga."""
    return "".join(chr(ord("9") - ord(c) + ord("0")) if c.isdigit() else c for c in d)


def recortes(est: dict, filtros: dict) -> dict:
    f = _norm(filtros)

    def ok(r):
        return ((not f["adv"] or r["ADVOGADO"] in f["adv"]) and (not f["fase"] or r["FASE"] in f["fase"])
                and (not f["uf"] or r["UF"] in f["uf"]) and (not f["localizador"] or r["LOCALIZADOR"] in f["localizador"]))
    recorte = [r for r in est["linhas"] if ok(r)]
    etapa = lambda r: not f["etapa"] or r["ETAPA"] in f["etapa"]
    lista = sorted((r for r in recorte if etapa(r) and (not f["mes"] or r["MES_EVENTO"] == f["mes"])), key=_ordem_lista)
    abertos = sorted((r for r in recorte if etapa(r) and r["ETAPA"] in ABERTAS), key=_ordem_lista)
    pas = [p for p in est["passagens"]
           if (not f["adv"] or p["ADVOGADO"] in f["adv"]) and (not f["uf"] or p["UF"] in f["uf"])
           and (not f["localizador"] or p["LOCALIZADOR"] in f["localizador"]) and (not f["mes"] or p["MES_ENVIO"] == f["mes"])]
    return {"recorte": recorte, "lista": lista, "lista_abertos": abertos, "passagens": pas, "filtros": f}


# ---------------- pivôs ----------------
def _soma(vals) -> float | None:
    v = [x for x in vals if x is not None]
    return arred(sum(v), 2) if v else None


def _ordem_fase(f: str):
    if f in FASES:
        return (0, FASES.index(f), "")
    if f in ("SEM FASE", "(vazio)"):
        return (2, 0, f)
    return (1, 0, f)


def _adv(a) -> str:
    return a if a else "SEM ADVOGADO"


def _pivo_adv_fase(linhas: list[dict]) -> dict:
    grupos: dict[tuple, list] = {}
    for r in linhas:
        grupos.setdefault((_adv(r["ADVOGADO"]), r["FASE"] or "SEM FASE"), []).append(r)
    adv_fase, por_fase, por_adv = [], [], []

    def ag(rs, **k):
        return {**k, "qtd": len(rs), "valor_risco": _soma(r["VALOR_RISCO"] for r in rs),
                "valor_performance": _soma(r["VALOR_PERFORMANCE"] for r in rs)}
    for a in sorted({a for a, _ in grupos}):
        fases = sorted((f for b, f in grupos if b == a), key=_ordem_fase)
        todas = []
        for fa in fases:
            adv_fase.append(ag(grupos[(a, fa)], advogado=a, fase=fa, tipo=""))
            todas += grupos[(a, fa)]
        sub = ag(todas, advogado=a, fase=None, tipo="sub")
        adv_fase.append(sub)
        por_adv.append({**sub, "tipo": ""})
    if linhas:
        tot = ag(linhas, advogado=None, fase=None, tipo="total")
        adv_fase.append(tot)
        for fa in sorted({f for _, f in grupos}, key=_ordem_fase):
            por_fase.append(ag([r for k, v in grupos.items() if k[1] == fa for r in v], fase=fa, tipo=""))
        por_fase.append({**tot, "advogado": None})
        por_adv.append(tot)
    return {"adv_fase": adv_fase, "por_fase": [{k: v for k, v in x.items() if k != "advogado"} for x in por_fase],
            "por_adv": por_adv}


def _mandados(linhas: list[dict]) -> list[dict]:
    rs = [r for r in linhas if r["ETAPA"] == "Mandado expedido"]
    chave = lambda r: (_adv(r["ADVOGADO"]), r["FASE"] or "SEM FASE", r["OBSERVACAO"] or "(vazio)", r["COMPLEMENTO"] or "(vazio)")
    grupos: dict[tuple, list] = {}
    for r in rs:
        grupos.setdefault(chave(r), []).append(r)
    out = []

    def ag(g, **k):
        return {**k, "valor_risco": _soma(r["VALOR_RISCO"] for r in g),
                "valor_performance": _soma(r["VALOR_PERFORMANCE"] for r in g), "qtd": len(g)}
    for a in sorted({k[0] for k in grupos}):
        ks = sorted((k for k in grupos if k[0] == a), key=lambda k: (_ordem_fase(k[1]), k[2], k[3]))
        for k in ks:
            out.append(ag(grupos[k], advogado=a, fase=k[1], observacao=k[2], complemento=k[3], tipo=""))
        out.append(ag([r for k in ks for r in grupos[k]], advogado=a, fase=None, observacao=None, complemento=None, tipo="sub"))
    if rs:
        out.append(ag(rs, advogado=None, fase=None, observacao=None, complemento=None, tipo="total"))
    return out


# ---------------- metas ----------------
def linha_meta(meta_qtd, meta_valor, real_qtd, real_valor, du_total: int, du_atual: int) -> dict:
    restantes = du_total - du_atual
    div = lambda a, b: None if a is None or b is None or b == 0 else a / b
    pct = lambda r, m: None if m is None else (0 if m == 0 else r / m)
    falta_qtd = None if meta_qtd is None else real_qtd - meta_qtd
    falta_valor = None if meta_valor is None else arred(real_valor - meta_valor, 2)
    tkt_real = div(real_valor, real_qtd)
    proj_qtd = int(arred(real_qtd / du_atual * restantes) + real_qtd) if du_atual > 0 else None
    proj_valor = None if proj_qtd is None else (arred(proj_qtd * tkt_real, 2) if tkt_real is not None else 0)
    return {
        "meta_qtd": meta_qtd, "meta_valor": meta_valor, "tkt_meta": div(meta_valor, meta_qtd),
        "real_qtd": real_qtd, "real_valor": real_valor, "tkt_real": tkt_real,
        "pct_qtd": pct(real_qtd, meta_qtd), "pct_valor": pct(real_valor, meta_valor),
        "falta_qtd": falta_qtd, "falta_valor": falta_valor,
        "tkt_falta": None if falta_qtd is None or falta_valor is None else (falta_valor if falta_qtd == 0 else falta_valor / falta_qtd),
        "falta_dia_qtd": None if falta_qtd is None or restantes <= 0 else int(arred_cima(-falta_qtd / restantes, 0)),
        "falta_dia_valor": None if falta_valor is None or restantes <= 0 else arred(-falta_valor / restantes, 2),
        "proj_qtd": proj_qtd, "proj_valor": proj_valor,
        "proj_pct_qtd": None if proj_qtd is None else pct(proj_qtd, meta_qtd),
        "proj_pct_valor": None if proj_valor is None else pct(proj_valor, meta_valor),
    }


def curva(meta_total: int, fator: float, du_total: int, real_acum: list) -> dict:
    total = int(arred(meta_total * fator))
    nec = arred_cima(total / du_total, 1)
    acum = [arred(nec * d, 1) for d in range(1, du_total + 1)]
    dif = [None if d >= len(real_acum) or real_acum[d] is None else int(arred(real_acum[d] - acum[d])) for d in range(du_total)]
    atual = [None if d == 0 or d >= len(real_acum) or real_acum[d] is None else int(arred(acum[d])) - real_acum[d - 1]
             for d in range(du_total)]
    return {"total": total, "necessidade_dia": nec, "acum": acum, "diferenca": dif, "atual": atual}


def _du_mes(ba: dict, mes: str) -> tuple[int, int]:
    fer, hoje = _feriados(ba), _hoje(ba)
    total = len(dias_uteis(mes, fer))
    a, m = _mes_key(mes)
    if (a, m) > (hoje.year, hoje.month):
        return total, 0
    if (a, m) < (hoje.year, hoje.month):
        return total, total
    return total, du_indice(hoje, fer)


def _metas_do_mes(lista: list, mes: str) -> dict[str, list]:
    out = {}
    for m, ch, q, v in lista:
        if m == mes:
            out[" ".join(str(ch).upper().split())] = [q, v]      # chave repetida no mês: vale a última
    return out


def _meta_faixas(ba: dict, mes: str) -> dict[str, tuple]:
    mf = _metas_do_mes(ba["metas"]["faixa"], mes)
    if not mf:
        return {}
    g = mf.get("121 A 360", [None, None])
    q1, q2 = (mf.get("JUDICIAL 1", [None])[0] or 0), (mf.get("JUDICIAL 2", [None])[0] or 0)
    out = {}
    for fa in FASES:
        q, v = mf.get(fa, [None, None])
        if fa in ("JUDICIAL 1", "JUDICIAL 2") and v is None and q is not None and g[1] is not None and q1 + q2 > 0:
            v = arred(q * (g[1] / (q1 + q2)), 2)
        out[fa] = (q, v)
    for nome, fases in FAIXAS:
        qs = [out[f][0] for f in fases if out[f][0] is not None]
        vs = [out[f][1] for f in fases if out[f][1] is not None]
        linha = mf.get(nome, [None, None])
        out[nome] = (sum(qs) if qs else linha[0], arred(sum(vs), 2) if vs else linha[1])
    return out


def _realizado(apreendidos: list[dict]) -> tuple[int, float]:
    return len(apreendidos), arred(sum(r["VALOR_PERFORMANCE"] or 0 for r in apreendidos), 2)


def _meta_banco(ba: dict, recorte: list, mes: str) -> dict:
    du_total, du_atual = _du_mes(ba, mes)
    ap = [r for r in recorte if r["MES_APREENSAO"] == mes]
    metas = _meta_faixas(ba, mes)
    linhas = []

    def add(chave, tipo, rs, meta):
        q, v = _realizado(rs)
        linhas.append({"chave": chave, "tipo": tipo, **linha_meta(meta[0], meta[1], q, v, du_total, du_atual)})
    for nome, fases in FAIXAS:
        for fa in fases:
            add(fa, "fase", [r for r in ap if r["FASE"] == fa], metas.get(fa, (None, None)))
        add(nome, "faixa", [r for r in ap if r["FASE"] in fases], metas.get(nome, (None, None)))
    outras = [r for r in ap if r["FASE"] not in FASES]
    if outras:
        q, v = _realizado(outras)
        linhas.append({"chave": OUTRAS, "tipo": "outras", **linha_meta(None, None, q, v, du_total, 0)})
    mt = [metas[n] for n, _ in FAIXAS if n in metas]
    tq = sum(m[0] for m in mt if m[0] is not None) if mt and any(m[0] is not None for m in mt) else None
    tv = arred(sum(m[1] for m in mt if m[1] is not None), 2) if mt and any(m[1] is not None for m in mt) else None
    add("TOTAL", "total", ap, (tq, tv))
    if not any(l["real_qtd"] or l["meta_qtd"] for l in linhas):
        linhas = []
    return {"mes": mes, "du_total": du_total, "du_atual": du_atual,
            "aviso": None if metas else f"meta não informada para {mes}", "linhas": linhas}


def _du_de(ba: dict, iso: str, mes: str) -> int:
    d = date.fromisoformat(iso)
    return max(1, du_indice(d, _feriados(ba)))


def _relogio(ba: dict, recorte: list, mes: str, meta_total) -> dict:
    du_total, du_atual = _du_mes(ba, mes)
    ap = [r for r in recorte if r["MES_APREENSAO"] == mes]
    dias = list(range(1, du_total + 1))

    def serie(rs):
        cont = [0] * du_total
        for r in rs:
            cont[_du_de(ba, r["DT_APREENSAO"], mes) - 1] += 1
        return [c if d <= du_atual else None for d, c in zip(dias, cont)]
    por = {fa: serie([r for r in ap if r["FASE"] == fa]) for fa in FASES if any(r["FASE"] == fa for r in ap)}
    outras = [r for r in ap if r["FASE"] not in FASES]
    if outras:
        por[OUTRAS] = serie(outras)
    tot = serie(ap)
    acum, s = [], 0
    for v in tot:
        if v is None:
            acum.append(None)
        else:
            s += v
            acum.append(s)
    curvas = {nome: curva(meta_total, f, du_total, acum) for nome, f in FATORES} if meta_total else {}
    return {"mes": mes, "du_total": du_total, "du_atual": du_atual, "dias": dias, "real_por_dia": por,
            "total_dia": tot, "real_acum": acum, "curvas": curvas}


def _advs_meta(ba: dict, ap: list, mes: str) -> list[tuple[str, tuple]]:
    ma = _metas_do_mes(ba["metas"]["advogado"], mes)
    vistos = []
    for m, ch, q, v in ba["metas"]["advogado"]:
        k = " ".join(str(ch).upper().split())
        if m == mes and k not in [x for x, _ in vistos]:
            vistos.append((k, tuple(ma[k])))
    resto = sorted({_adv(r["ADVOGADO"]) for r in ap} - {k for k, _ in vistos})
    return vistos + [(a, (None, None)) for a in resto]


def _meta_analista(ba: dict, recorte: list, mes: str) -> dict:
    du_total, du_atual = _du_mes(ba, mes)
    ap = [r for r in recorte if r["MES_APREENSAO"] == mes]
    linhas = []
    advs = _advs_meta(ba, ap, mes)
    for a, (mq, mv) in advs:
        q, v = _realizado([r for r in ap if _adv(r["ADVOGADO"]).upper() == a])
        linhas.append({"chave": a, "tipo": "advogado", **linha_meta(mq, mv, q, v, du_total, du_atual)})
    if linhas:
        mqs = [m[0] for _, m in advs if m[0] is not None]
        mvs = [m[1] for _, m in advs if m[1] is not None]
        q, v = _realizado([r for r in ap if _adv(r["ADVOGADO"]).upper() in {a for a, _ in advs}])
        linhas.append({"chave": "TOTAL", "tipo": "total", **linha_meta(sum(mqs) if mqs else None,
                                                                        arred(sum(mvs), 2) if mvs else None, q, v, du_total, du_atual)})
    return {"mes": mes, "du_total": du_total, "du_atual": du_atual, "linhas": linhas}


def _relogio_analista(ba: dict, recorte: list, mes: str) -> list[dict]:
    du_total, du_atual = _du_mes(ba, mes)
    ap = [r for r in recorte if r["MES_APREENSAO"] == mes]
    out = []
    for a, (mq, _) in _advs_meta(ba, ap, mes):
        rs = [r for r in ap if _adv(r["ADVOGADO"]).upper() == a]
        cont = [0] * du_total
        for r in rs:
            cont[_du_de(ba, r["DT_APREENSAO"], mes) - 1] += 1
        dia = [c if d <= du_atual else None for d, c in zip(range(1, du_total + 1), cont)]
        acum, s = [], 0
        for v in dia:
            if v is None:
                acum.append(None)
            else:
                s += v
                acum.append(s)
        out.append({"advogado": a, "meta_qtd": mq, "real_dia": dia, "real_acum": acum,
                    "curva": curva(mq, 1.0, du_total, acum) if mq else None})
    return out


# ---------------- COMP. ANALISTA, localizadores ----------------
def _comp_analista(ba: dict, recorte: list) -> dict:
    du_hoje = du_indice(_hoje(ba), _feriados(ba))
    ap = [r for r in recorte if r["DT_APREENSAO"]]
    meses = sorted({r["MES_APREENSAO"] for r in ap}, key=_mes_key)
    ok = [r for r in ap if r["DIA_UTIL"] <= du_hoje]

    def valores(rs):
        return {m: sum(1 for r in rs if r["MES_APREENSAO"] == m) for m in meses}
    advs = sorted({_adv(r["ADVOGADO"]) for r in ap})
    por_adv = [{"advogado": a, "tipo": "", "valores": valores([r for r in ok if _adv(r["ADVOGADO"]) == a])} for a in advs]
    por_quebra = []
    for a in advs:
        rs = [r for r in ok if _adv(r["ADVOGADO"]) == a]
        for q in QUEBRAS:
            por_quebra.append({"advogado": a, "quebra": q, "tipo": "", "valores": valores([r for r in rs if r["DIA_UTIL_QUEBRA"] == q])})
        por_quebra.append({"advogado": a, "quebra": None, "tipo": "sub", "valores": valores(rs)})
    if advs:
        por_adv.append({"advogado": None, "tipo": "total", "valores": valores(ok)})
        por_quebra.append({"advogado": None, "quebra": None, "tipo": "total", "valores": valores(ok)})
    return {"meses": meses, "por_adv": por_adv, "por_quebra": por_quebra}


def _mediana(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return arred(median(xs), 1) if xs else None


def _comparativo(pas: list[dict]) -> list[dict]:
    def ag(rs, nome, tipo):
        loc = sum(1 for p in rs if p["RESULTADO"] == "localizou")
        enc = sum(1 for p in rs if p["RESULTADO"] == "encerrada")
        base = len(rs) - enc
        ufs: dict[str, int] = {}
        for p in rs:
            if p["UF"]:
                ufs[p["UF"]] = ufs.get(p["UF"], 0) + 1
        return {"localizador": nome, "tipo": tipo, "pastas": len({p["PASTA"] for p in rs}), "passagens": len(rs),
                "localizou": loc, "substituido": sum(1 for p in rs if p["RESULTADO"] == "substituido"),
                "sem_localizacao": sum(1 for p in rs if p["RESULTADO"] == "sem_localizacao"), "encerradas": enc,
                "pct_localizou": arred(loc / base, 4) if base > 0 else None,
                "apreendeu": sum(1 for p in rs if p["APREENDEU"]),
                "valor_performance": _soma(p["VALOR_PERFORMANCE"] for p in rs if p["APREENDEU"]),
                "mediana_dias_localizar": _mediana(p["DIAS_ATE_LOCALIZAR"] for p in rs if p["RESULTADO"] == "localizou"),
                "mediana_dias_com_ficha": _mediana(p["DIAS"] for p in rs),
                "ufs": ", ".join(u for u, _ in sorted(ufs.items(), key=lambda x: (-x[1], x[0]))[:3])}
    grupos: dict[str, list] = {}
    for p in pas:
        grupos.setdefault(p["LOCALIZADOR"], []).append(p)
    out = sorted((ag(rs, n, "") for n, rs in grupos.items()), key=lambda x: (-x["localizou"], -x["passagens"], x["localizador"]))
    if out:
        out.append(ag(pas, None, "total"))
    return out


def _por_localizador(recorte: list, mes: str | None) -> list[dict]:
    ap = [r for r in recorte if r["DT_APREENSAO"] and (not mes or r["MES_APREENSAO"] == mes)]
    grupos: dict[str, dict[str, list]] = {}
    for r in ap:
        grupos.setdefault(r["LOCALIZADOR"] or SEM_LOC, {}).setdefault(r["UF"] or "SEM UF", []).append(r)
    out = []
    for loc in sorted(grupos, key=lambda x: (x == SEM_LOC, x)):
        ufs = grupos[loc]
        for uf in sorted(ufs, key=lambda u: (-len(ufs[u]), u)):
            out.append({"localizador": loc, "uf": uf, "tipo": "", "qtd": len(ufs[uf]),
                        "valor_performance": _soma(r["VALOR_PERFORMANCE"] for r in ufs[uf])})
        todos = [r for v in ufs.values() for r in v]
        out.append({"localizador": loc, "uf": None, "tipo": "sub", "qtd": len(todos),
                    "valor_performance": _soma(r["VALOR_PERFORMANCE"] for r in todos)})
    if ap:
        out.append({"localizador": None, "uf": None, "tipo": "total", "qtd": len(ap),
                    "valor_performance": _soma(r["VALOR_PERFORMANCE"] for r in ap)})
    return out


# ---------------- tudo ----------------
def secoes(ba: dict, agora: str, filtros: dict) -> dict:
    est = estado(ba, agora)
    rc = recortes(est, filtros)
    f = rc["filtros"]
    hoje = _hoje(ba)
    mes_metas = f["mes"] or f"{hoje.month}/{hoje.year}"
    recorte = rc["recorte"]
    apreendidos = [r for r in rc["lista"] if r["DT_APREENSAO"] and (not f["mes"] or r["MES_APREENSAO"] == f["mes"])]
    vis_ap = [r for r in recorte if r["DT_APREENSAO"] and (not f["mes"] or r["MES_APREENSAO"] == f["mes"])]
    mb = _meta_banco(ba, recorte, mes_metas)
    total = next((l for l in mb["linhas"] if l["chave"] == "TOTAL"), None)
    meta_total = total["meta_qtd"] if total else None
    if meta_total is None:
        meta_total = (_meta_faixas(ba, mes_metas).get("121 A 360", (None,))[0] or 0) + \
            (_meta_faixas(ba, mes_metas).get("360 A 720", (None,))[0] or 0) + (_meta_faixas(ba, mes_metas).get("> 720", (None,))[0] or 0) or None
    du_total, du_atual = _du_mes(ba, mes_metas)
    return {
        "localizados": rc["lista_abertos"],
        "visao_localizados": _pivo_adv_fase(rc["lista_abertos"]),
        "mandados": _mandados(rc["lista_abertos"]),
        "apreendidos": apreendidos,
        "visao_apreendidos": {k: v for k, v in _pivo_adv_fase(vis_ap).items() if k != "por_adv"},
        "comp_analista": _comp_analista(ba, recorte),
        "meta_banco": mb,
        "meta_relogio": _relogio(ba, recorte, mes_metas, meta_total),
        "meta_analista": _meta_analista(ba, recorte, mes_metas),
        "meta_relogio_analista": _relogio_analista(ba, recorte, mes_metas),
        "comparativo": _comparativo(rc["passagens"]),
        "por_localizador": _por_localizador(recorte, f["mes"]),
        "nota_mes": f"Mês {_mes_key(mes_metas)[1]:02d}/{_mes_key(mes_metas)[0]} · dia útil {du_atual} de {du_total}",
    }


def linha_tempo(ba: dict, agora: str, filtros: dict, janela: str) -> dict:
    est = estado(ba, agora)
    rc = recortes(est, {**filtros, "mes": None, "etapa": []})
    etapas = list(filtros.get("etapa") or []) or list(ABERTAS)
    hoje = _hoje(ba)
    sel = [r for r in rc["recorte"] if r["ETAPA"] in etapas]
    marcos = {r["PASTA"]: [m for m in ba["marcos"].get(r["PASTA"], []) if m[2] <= hoje.isoformat() or r["ETAPA"] in ABERTAS]
              for r in sel}
    if janela == "tudo":
        datas = [m[2] for ms in marcos.values() for m in ms]
        de = min(datas) if datas else hoje.isoformat()
    else:
        de = (hoje - timedelta(days=int(janela))).isoformat()
    pastas = []
    for r in sel:
        ms = marcos[r["PASTA"]]
        aberta = r["ETAPA"] in ABERTAS
        dentro = [m for m in ms if m[2] >= de]
        if not dentro and not aberta:
            continue
        antes = [m for m in ms if m[2] < de]
        lista = ([antes[-1]] if antes else []) + dentro
        dias = None
        if aberta and ms:
            dias = max(0, (hoje - date.fromisoformat(max(m[2] for m in ms))).days)
        dl = r["DT_LOCALIZACAO"]
        pastas.append({"pasta": r["PASTA"], "financiado": r["FINANCIADO"], "advogado": r["ADVOGADO"], "uf": r["UF"],
                       "fase": r["FASE"], "localizador": r["LOCALIZADOR"],
                       "mes_localizacao": f"{int(dl[5:7])}/{dl[:4]}" if dl else None, "etapa": r["ETAPA"],
                       "em_aberto": aberta, "dias_parado": dias, "marcos": lista})
    return {"de": de, "ate": hoje.isoformat(), "pastas": pastas}
