"""Payload mínimo montado à mão para testar as agregações (mesma estrutura do payload real)."""
from __future__ import annotations

from src.regra import EXTINTAS, ORDEM_ACAO, ORDEM_FOLLOW, ORDEM_PROCESSUAL, TIPOS

ATRIB = ("uf", "carteira", "adv", "produto", "comarca", "marca")


def pasta(id_, tipo, data=0, uf="SP", carteira="VAREJO 1", adv="ADV-01", produto="LEVES", comarca="SAO PAULO",
          marca="FIAT", risco=1000.0, bem=800.0, ano=2020):
    return {"pasta": id_, "tipo": tipo, "data": data, "uf": uf, "carteira": carteira, "adv": adv, "produto": produto,
            "comarca": comarca, "marca": marca, "risco": risco, "bem": bem, "ano": ano}


def mini_payload(fotos: list[tuple[str, str, str, list[dict]]], publicacoes: list[dict] | None = None) -> dict:
    """fotos = [(dia_iso, hora, origem, [pasta(...), ...]), ...]; todas as fotos são gravadas cheias."""
    todas = {}
    for _, _, _, rows in fotos:
        for r in rows:
            todas[r["pasta"]] = r
    ids = sorted(todas)
    dic = {"tipo": list(TIPOS), "nome_uf": {}}
    pastas = {"pasta": ids}
    for a in ATRIB:
        dic[a] = sorted({todas[i][a] for i in ids if todas[i][a] is not None})
        pastas[a] = [None if todas[i][a] is None else dic[a].index(todas[i][a]) for i in ids]
    pastas["risco"] = [todas[i]["risco"] for i in ids]
    pastas["bem"] = [todas[i]["bem"] for i in ids]
    pastas["ano_modelo"] = [todas[i]["ano"] for i in ids]
    fs = [{"dia": d, "hora": h, "origem": o,
           "estado": [[ids.index(r["pasta"]), list(TIPOS).index(r["tipo"]), r["data"]] for r in rows]}
          for d, h, o, rows in fotos]
    if publicacoes is None:
        ultimo = len(fotos) - 1
        publicacoes = [{"agora": "17:05", "foto": ultimo, "origem": fotos[ultimo][2], "quando": fotos[ultimo][1],
                        "avisos": [], "base": ultimo, "anterior": None, "conciliacao": None}]
    return {"hoje": "2026-11-26", "dic": dic, "ordens": {"processual": list(ORDEM_PROCESSUAL), "follow": list(ORDEM_FOLLOW),
            "acao": list(ORDEM_ACAO), "extintas": list(EXTINTAS)}, "pastas": pastas, "fotos": fs,
            "publicacoes": publicacoes, "fontes_bd": "bd.json"}


def um_dia(rows: list[dict]) -> dict:
    return mini_payload([("2026-11-26", "17:05", "ao_vivo", rows)])


def placas_min(pl: dict, capt: dict[str, list], placas: dict[str, str | None], agora: str = "17:05",
               falhou: bool = False) -> dict:
    """Acrescenta placas a um payload de construtores: capt = {pasta: [ult_min, (cidade, uf, bairro), n, n7, n30,
    estado, dias, principal[, passagens_janela, passagens_principal]]}; placas = {pasta: placa ou None} (pasta ausente = placa "ZZ" + id)."""
    from src.padroes import CORES, ESTADOS, ROTULOS, SUGESTAO
    ids = pl["pastas"]["pasta"]
    pl["pastas"]["placa"] = [placas.get(p, ("ZZ" + p.upper() + "00000")[:7]) for p in ids]
    local, princ, linhas = [], [], []
    for p, (ult, loc, n, n7, n30, est, dias, pp, *pas) in sorted(capt.items(), key=lambda x: ids.index(x[0])):
        if list(loc) not in local:
            local.append(list(loc))
        if pp is not None and pp not in princ:
            princ.append(pp)
        linhas.append([ids.index(p), ult, local.index(list(loc)), n, n7, n30, ESTADOS.index(est), dias,
                       None if pp is None else princ.index(pp), *(pas or [n, None])])
    pl["placas"] = {"dic": {"local": local, "principal": princ}, "estados": list(ESTADOS), "rotulos": ROTULOS,
                    "cores": CORES, "sugestao": SUGESTAO,
                    "cargas": [{"agora": agora, "ate": "2026-11-26T17:00", "falhou": falhou, "estado": linhas}]}
    return pl
