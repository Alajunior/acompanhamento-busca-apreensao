"""Monta o painel: payload compacto embutido em docs/index.html e a base analítica (bd.json) para a exportação.

Payload:
- `pastas`: atributos de cada pasta que aparece em alguma foto, em colunas com códigos de dicionário
  (na simulação os atributos são estáveis dentro da janela);
- `fotos`: a 1ª foto cheia ([pasta, tipo, dias até hoje]) e as demais como delta sobre a anterior
  ({"sai": [...], "muda": [...]}). O navegador reconstrói cada dia aplicando os deltas em sequência;
- `publicacoes`: o que o painel mostra em cada horário do "agora (simulado)".
"""
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from dados.gerar import HOJE, NOME_UF, simular
from src import padroes
from src.montar_ba import montar_ba
from src.publicacao import LinhaDoTempo, linha_do_tempo
from src.regra import COLUNAS, EXTINTAS, ORDEM_ACAO, ORDEM_FOLLOW, ORDEM_PROCESSUAL, TIPOS, chave

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "src" / "painel.html"
MAPA = RAIZ / "docs" / "vendor" / "br_uf.json"
SCRIPTS = {"/*__AGREGAR__*/": RAIZ / "src" / "agregar.js", "/*__EXPORTAR__*/": RAIZ / "src" / "exportar.js",
           "/*__BA__*/": RAIZ / "src" / "ba.js"}
DINAMICAS_BD = ("TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "FASE", "DATA_INSERT")
_ATRIBUTOS = {"uf": ("UF", None), "carteira": ("CARTEIRA_PRODUTO", "(vazio)"), "adv": ("ADVOGADO_OPERACIONAL", "(sem advogado)"),
              "produto": ("PRODUTO_VEICULO", "(sem produto)"), "comarca": ("COMARCA", "(sem comarca)"), "marca": ("MARCA", None)}


def _texto(s: pd.Series, vazio: str | None) -> pd.Series:
    t = s.astype("string").str.strip()
    t = t.mask(t == "")
    return t.fillna(vazio) if vazio else t


def _num(v):
    return None if v is None or pd.isna(v) else float(v)


def _atributos(linha: LinhaDoTempo) -> pd.DataFrame:
    """Uma linha por pasta (chave), com os atributos da foto mais recente em que ela aparece."""
    partes = [f.df.assign(_k=f.df["PASTA"].map(chave), _ordem=i) for i, f in enumerate(linha.fotos)]
    todas = pd.concat(partes, ignore_index=True).sort_values("_ordem").drop_duplicates("_k", keep="last")
    return todas.sort_values("_k").reset_index(drop=True)


def montar_payload(linha: LinhaDoTempo, cargas: list[dict] | None = None) -> dict:
    at = _atributos(linha)
    dic = {"tipo": list(TIPOS), "nome_uf": NOME_UF}
    pastas = {"pasta": at["_k"].tolist()}
    for nome, (col, vazio) in _ATRIBUTOS.items():
        valores = _texto(at[col], vazio)
        dic[nome] = sorted(valores.dropna().unique().tolist(), key=lambda x: (x.startswith("("), x))
        cod = {v: i for i, v in enumerate(dic[nome])}
        pastas[nome] = [None if pd.isna(v) else cod[v] for v in valores]
    pastas["risco"] = [_num(v) for v in at["VALOR_RISCO_CONTRATO"]]
    pastas["bem"] = [_num(v) for v in at["VALOR_DO_BEM"]]
    pastas["ano_modelo"] = [None if pd.isna(v) else int(v) for v in pd.to_numeric(at["ANO_MODELO"], errors="coerce")]

    idx = {k: i for i, k in enumerate(pastas["pasta"])}
    tipo_cod = {t: i for i, t in enumerate(TIPOS)}
    fotos, anterior = [], None
    for f in linha.fotos:
        datas = pd.to_datetime(f.df["DATA_AGENDAMENTO"])
        dias = ((datas - HOJE).dt.days).astype("Int64")
        atual = {idx[chave(p)]: (tipo_cod[t], None if pd.isna(d) else int(d))
                 for p, t, d in zip(f.df["PASTA"], f.df["TIPO_AGENDAMENTO"], dias)}
        if anterior is None:
            estado = [[i, t, d] for i, (t, d) in sorted(atual.items())]
        else:
            estado = {"sai": sorted(set(anterior) - set(atual)),
                      "muda": [[i, t, d] for i, (t, d) in sorted(atual.items()) if anterior.get(i) != (t, d)]}
        fotos.append({"dia": f.dia.isoformat(), "hora": f.hora, "origem": f.origem, "estado": estado})
        anterior = atual

    out = {"hoje": HOJE.date().isoformat(), "dic": dic,
           "ordens": {"processual": list(ORDEM_PROCESSUAL), "follow": list(ORDEM_FOLLOW), "acao": list(ORDEM_ACAO),
                      "extintas": list(EXTINTAS)},
           "pastas": pastas, "fotos": fotos, "publicacoes": _limpo(linha.publicacoes), "fontes_bd": "bd.json"}
    if cargas is not None:
        pastas["placa"] = [padroes.normalizar_placa(v) for v in at["PLACA"]]
        out["placas"] = _placas_payload(cargas, idx)
    return out


def _minutos(t: pd.Timestamp) -> int:
    return int((t - HOJE).total_seconds() // 60)


def _delta(anterior: dict | None, atual: dict) -> list | dict:
    if anterior is None:
        return [atual[i] for i in sorted(atual)]
    return {"sai": sorted(set(anterior) - set(atual)), "muda": [atual[i] for i in sorted(atual) if anterior.get(i) != atual[i]]}


def _placas_payload(cargas: list[dict], idx: dict) -> dict:
    """Resumo por pasta de cada carga de capturas, em delta como as fotos: [i, ult_min, loc, n, n7, n30, est, dias, pp]."""
    local, principal = {}, {}
    est_cod = {e: k for k, e in enumerate(padroes.ESTADOS)}
    saida, anterior = [], None
    for c in cargas:
        atual = {}
        for pasta, v in c["pastas"].items():
            if pasta not in idx:
                continue
            r = v["resumo"]
            loc = local.setdefault(r["loc"], len(local))
            pp = None if r["principal"] is None else principal.setdefault(r["principal"], len(principal))
            atual[idx[pasta]] = [idx[pasta], _minutos(r["ult"]), loc, r["n"], r["n7"], r["n30"], est_cod[r["estado"]],
                                 r["dias"], pp]
        saida.append({"agora": c["agora"], "ate": c["ate"].strftime("%Y-%m-%dT%H:%M") if c["ate"] is not None else None,
                      "falhou": c["falhou"], "estado": _delta(anterior, atual)})
        anterior = atual
    return {"dic": {"local": [list(k) for k in local], "principal": list(principal)},
            "estados": list(padroes.ESTADOS), "rotulos": padroes.ROTULOS, "cores": padroes.CORES,
            "sugestao": padroes.SUGESTAO, "cargas": saida}


def _detalhe_compacto(d: dict, ends: dict, locs: dict) -> dict:
    """Detalhe da pasta para o placas.json. Instantes em minutos desde 26/11 00:00; endereços e locais por índice:
    ultima = {q, e, lat, lon, empresa, storage}; pontos = [[letra, lat, lon, dias, passagens, faixa, ultima, e, principal]];
    ultimas = [[q, local]]; area = {vertices, km} | null."""
    def e(x: dict) -> int:
        return ends.setdefault(tuple(x[k] for k in ("rua", "numero", "bairro", "cidade", "uf", "cep")), len(ends))

    def c(v):
        return round(float(v), 5)

    u = d["ultima"]
    return {"ultima": {"q": _minutos(u["quando"]), "e": e(u), "lat": c(u["lat"]), "lon": c(u["lon"]),
                       "empresa": u["empresa"], "storage": u["storage"]},
            "pontos": [[p["letra"], c(p["lat"]), c(p["lon"]), p["dias"], p["passagens"], p["faixa"], _minutos(p["ultima"]),
                        e(p["endereco"]), p["principal"]] for p in d["pontos"]],
            "sequencia": d["sequencia"],
            "area": None if d["area"] is None else {"vertices": [[c(a), c(b)] for a, b in d["area"]["vertices"]],
                                                    "km": d["area"]["km"]},
            "semana": d["semana"], "horas": d["horas"],
            "ultimas": [[_minutos(q), locs.setdefault(l, len(locs))] for q, l in d["ultimas"]],
            "perto_de_casa": d["perto_de_casa"]}


def _texto_banco(b: dict) -> str:
    linha1 = ", ".join(str(x) for x in (b.get("ENDERECO"), b.get("NUMERO"), b.get("COMPLEMENTO")) if x and not pd.isna(x))
    cid = "/".join(str(x) for x in (b.get("CIDADE"), b.get("UF")) if x)
    return " · ".join(x for x in (linha1, ", ".join(y for y in (b.get("BAIRRO"), cid) if y),
                                  f"CEP {b['CEP']}" if b.get("CEP") else "") if x)


def montar_placas(cargas: list[dict], bancos: dict[str, dict], payload: dict, saida: Path) -> None:
    """docs/placas.json: detalhe de cada pasta por carga (delta) e o endereço do banco; carregado sob demanda."""
    idx = {k: i for i, k in enumerate(payload["pastas"]["pasta"])}
    out, anterior, ends, locs = [], None, {}, {}
    for c in cargas:
        atual = {idx[p]: _detalhe_compacto(v["detalhe"], ends, locs) for p, v in c["pastas"].items() if p in idx}
        if anterior is None:
            out.append({str(i): atual[i] for i in sorted(atual)})
        else:
            out.append({"sai": sorted(set(anterior) - set(atual)),
                        "muda": {str(i): atual[i] for i in sorted(atual) if anterior.get(i) != atual[i]}})
        anterior = atual
    banco = {str(idx[p]): _texto_banco(b) for p, b in bancos.items() if p in idx}
    saida.write_text(json.dumps({"enderecos": [list(k) for k in ends], "locais": list(locs), "cargas": out, "banco": banco},
                                ensure_ascii=False, allow_nan=False,
                                separators=(",", ":")), encoding="utf-8")


def _limpo(x):
    """Tipos do numpy/pandas → JSON puro."""
    if isinstance(x, dict):
        return {str(k): _limpo(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_limpo(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _json(x) -> str:
    return json.dumps(x, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("</", r"<\/")


def montar_html(payload: dict, saida: Path) -> None:
    payload = {k: v for k, v in payload.items() if not k.startswith("_")}   # caches internos (ex.: referencia) não vão para a página
    html = MODELO.read_text(encoding="utf-8").replace("/*__DADOS__*/", "const DADOS = " + _json(payload) + ";")
    mapa = json.loads(MAPA.read_text(encoding="utf-8"))   # embutido: o mapa funciona também abrindo o arquivo local
    html = html.replace("/*__MAPA__*/", "const MAPA_UF = " + _json(mapa) + ";")
    for marca, arq in SCRIPTS.items():
        html = html.replace(marca, arq.read_text(encoding="utf-8").replace("</", r"<\/") if arq.exists() else "")
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")


def _valor_bd(v):
    if v is None or (not isinstance(v, (str, date, time)) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (date, time)):
        return v.isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v)
    return v


def montar_bd(linha: LinhaDoTempo, payload: dict, saida: Path) -> None:
    """Base analítica (aba BD do .xlsx): uma linha por pasta das fotos de hoje, com as colunas estáveis.
    TIPO_AGENDAMENTO, DATA_AGENDAMENTO, FASE e DATA_INSERT vêm da foto da publicação (no navegador)."""
    hoje = HOJE.date()
    partes = [f.df.assign(_ordem=i) for i, f in enumerate(linha.fotos) if f.dia == hoje]
    df = pd.concat(partes, ignore_index=True).sort_values("_ordem").drop_duplicates("PASTA", keep="last")
    idx = {k: i for i, k in enumerate(payload["pastas"]["pasta"])}
    colunas = [c for c in COLUNAS if c not in DINAMICAS_BD]
    bd = {"colunas": colunas, "todas": list(COLUNAS), "pastas": [idx[chave(p)] for p in df["PASTA"]],
          "valores": [[_valor_bd(v) for v in linha_] for linha_ in df[colunas].itertuples(index=False, name=None)]}
    saida.write_text(json.dumps(bd, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    sim = simular(42)
    linha = linha_do_tempo(sim)
    cargas = padroes.cargas(sim)
    payload = montar_payload(linha, cargas)
    montar_html(payload, RAIZ / "docs" / "index.html")
    montar_bd(linha, payload, RAIZ / "docs" / "bd.json")
    montar_placas(cargas, padroes.bancos_por_pasta(sim), payload, RAIZ / "docs" / "placas.json")
    montar_ba(sim, RAIZ / "docs" / "ba.json")
    print(" · ".join(f"docs/{a}: {(RAIZ / 'docs' / a).stat().st_size / 1024:.0f} KB" for a in ("index.html", "bd.json", "placas.json", "ba.json")))


if __name__ == "__main__":
    main()
