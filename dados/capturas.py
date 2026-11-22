"""Capturas de placa por câmera e endereços do banco (dados 100% sintéticos), fase 2.

Cada veículo visto tem uma rotina: 1 a 3 pontos fixos (casa, trabalho, outro) perto do centro de uma cidade real,
com uma hora típica e dias sorteados para produzir os estados dos padrões (≥6 dias, 4–5, 1–3), mais capturas
esparsas pela cidade. Os pontos ficam no centro de uma célula de ~330 m (a dos padrões), com a câmera a ≤ 60 m,
para o estado sorteado ser o estado medido.

Usa um gerador próprio (seed + 1): nenhum número da fase 1 muda.
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from dados.gerar import COMARCAS, HOJE, PESO_UF, UFS, Simulacao

FIM = HOJE + pd.Timedelta(hours=17, minutes=5)       # última carga do dia simulado
JANELA = 58                                          # dias de rotina (dentro dos 60 da janela dos padrões)
P_VISTO = 0.35                                       # vistos nos últimos 60 dias
P_SO_ANTIGA = 0.05                                   # só capturas com mais de 60 dias
P_ESTADO = {"observado": 0.42, "formacao": 0.20, "aprendendo": 0.38}
P_OUTRA_CIDADE, P_OUTRA_UF = 0.08, 0.05
RAIO_KM = 6.0
CELULA = 0.003
HORAS = {"casa": [6, 7, 18, 19, 20], "trabalho": [7, 8, 9, 17, 18]}
BAIRROS = ["CENTRO", "VILA NOVA", "JARDIM AMERICA", "SAO JOSE", "BOA VISTA", "SANTA LUCIA", "JARDIM DAS FLORES",
           "PARQUE INDUSTRIAL", "VILA RICA", "SANTO ANTONIO", "BELA VISTA", "JARDIM PRIMAVERA"]
RUAS = ["RUA DAS ACACIAS", "AVENIDA BRASIL", "RUA DOS IPES", "RUA SETE", "AVENIDA CENTRAL", "RUA DAS PALMEIRAS",
        "RUA DO COMERCIO", "AVENIDA DAS NACOES", "RUA SAO PEDRO", "RUA DAS FLORES", "RUA QUINZE", "AVENIDA PARANA"]
EMPRESAS = ["CAMERAS 01", "CAMERAS 02", "CAMERAS 03", "CAMERAS 04"]
NULOS_TXT = ["undefined", "null", "nan"]
CIDADES = {u: [(c[0], c[1], c[2]) for c in COMARCAS[u]] for u in COMARCAS}

_cache: dict = {}


def _cep(cidade: str, bairro: str, rng) -> str:
    """CEP sintético: 3 dígitos da cidade + 2 do bairro (mesmo prefixo de 5 = mesmo bairro) + 3 sorteados."""
    base = zlib.crc32(cidade.encode()) % 900 + 100
    return f"{base:03d}{BAIRROS.index(bairro):02d}{int(rng.integers(0, 1000)):03d}"


def _centro_celula(lat: float, lon: float) -> tuple[float, float]:
    return round(lat / CELULA) * CELULA, round(lon / CELULA) * CELULA


def _ponto(rng, cidade: tuple, uf: str) -> dict:
    nome, lat0, lon0 = cidade
    r, a = RAIO_KM * np.sqrt(rng.random()), rng.uniform(0, 2 * np.pi)
    lat, lon = _centro_celula(lat0 + r * np.cos(a) / 111.0, lon0 + r * np.sin(a) / (111.0 * np.cos(np.radians(lat0))))
    bairro = str(rng.choice(BAIRROS))
    return {"lat": lat, "lon": lon, "cidade": nome, "uf": uf, "bairro": bairro, "rua": str(rng.choice(RUAS)),
            "numero": str(int(rng.integers(1, 3000))), "cep": _cep(nome, bairro, rng),
            "device": f"CAM-{int(rng.integers(1, 10000)):04d}", "empresa": str(rng.choice(EMPRESAS)),
            "tipo_cam": "FIXA" if rng.random() < 0.85 else "MOVEL"}


def _cidade_do_veiculo(rng, uf: str, comarca: str) -> tuple[tuple, str]:
    u = rng.random()
    if u < P_OUTRA_UF:
        outras = [x for x in UFS if x != uf]
        peso = np.array([PESO_UF[UFS.index(x)] for x in outras])
        uf = str(rng.choice(outras, p=peso / peso.sum()))
        return CIDADES[uf][int(rng.integers(len(CIDADES[uf])))], uf
    if u < P_OUTRA_UF + P_OUTRA_CIDADE and len(CIDADES[uf]) > 1:
        outras = [c for c in CIDADES[uf] if c[0] != comarca]
        return outras[int(rng.integers(len(outras)))], uf
    return next(c for c in CIDADES[uf] if c[0] == comarca), uf


def _passagens(rng, ponto: dict, dias_atras: np.ndarray, hora: int) -> list[tuple]:
    out = []
    for d in dias_atras:
        horas = [hora] + ([(hora + 9) % 24] if rng.random() < 0.2 else [])
        for h in horas:
            quando = HOJE - pd.Timedelta(days=int(d)) + pd.Timedelta(minutes=float(h * 60 + rng.normal(0, 40)))
            dl, da = 0.00054 * np.sqrt(rng.random()), rng.uniform(0, 2 * np.pi)   # câmera a ≤ 60 m do ponto
            out.append((quando, ponto["lat"] + dl * np.cos(da), ponto["lon"] + dl * np.sin(da), ponto))
    return out


def _veiculo(rng, uf: str, comarca: str) -> tuple[list[tuple], dict | None]:
    """Passagens de um veículo visto nos últimos 60 dias e o ponto "casa" (para o endereço do banco)."""
    cidade, uf_c = _cidade_do_veiculo(rng, uf, comarca)
    estado = rng.choice(list(P_ESTADO), p=list(P_ESTADO.values()))
    dias = {"observado": 6 + int(rng.geometric(0.25)) - 1, "formacao": int(rng.integers(4, 6)),
            "aprendendo": int(rng.integers(1, 4))}[estado]
    dias = min(dias, JANELA)
    papeis = ["casa", "trabalho", "outro"][: 1 if dias == 1 else int(rng.integers(1, 4))]
    pontos = [_ponto(rng, cidade, uf_c) for _ in papeis]
    caps = []
    for k, (papel, pt) in enumerate(zip(papeis, pontos)):
        n = dias if k == 0 else int(rng.integers(1, dias))
        hora = int(rng.choice(HORAS.get(papel, list(range(6, 23)))))
        caps += _passagens(rng, pt, rng.choice(JANELA, n, replace=False), hora)
    for _ in range(int(rng.integers(0, 5)) if estado == "aprendendo" else int(rng.integers(0, 2))):
        pt = _ponto(rng, cidade, uf_c)                        # esparsas: um dia cada, lugares diferentes
        caps += _passagens(rng, pt, rng.choice(JANELA, 1), int(rng.integers(6, 23)))
    return caps, pontos[0]


def _antigas(rng, uf: str, comarca: str) -> list[tuple]:
    cidade, uf_c = _cidade_do_veiculo(rng, uf, comarca)
    pt = _ponto(rng, cidade, uf_c)
    return _passagens(rng, pt, rng.integers(61, 200, int(rng.integers(1, 6))), int(rng.integers(6, 23)))


def _placas(sim: Simulacao, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed + 1)
    p = sim.pastas
    gar = sim.garantia.drop_duplicates("CARTEIRA_CONTRATO")
    g = dict(zip(gar["CARTEIRA_CONTRATO"], zip(gar["PLACA"], gar["MARCA"], gar["MODELO"], gar["ANO_MODELO"])))
    v = sim.veiculo.dropna().drop_duplicates("PASTA")
    cor = dict(zip(v["PASTA"], v["COR"]))
    cand = p[(p["dia_ajuizamento"] <= HOJE) & (p["dia_saida"].isna() | (p["dia_saida"] >= HOJE - pd.Timedelta(days=60)))
             & p["PASTA"].isin(g)]
    linhas, casa_de = [], {}
    for pasta, uf, comarca, saida in zip(cand["PASTA"], cand["UF"], cand["COMARCA"], cand["dia_saida"]):
        u = rng.random()
        if u < P_VISTO:
            caps, casa = _veiculo(rng, uf, comarca)
            casa_de[pasta] = casa
        elif u < P_VISTO + P_SO_ANTIGA:
            caps = _antigas(rng, uf, comarca)
        else:
            continue
        limite = min(FIM, saida) if pd.notna(saida) else FIM      # apreendido / saiu: o veículo some das câmeras
        placa, marca, modelo, ano = g[pasta]
        for quando, lat, lon, pt in caps:
            if quando <= limite:
                linhas.append((placa, marca, modelo, cor.get(pasta), ano, quando, lat, lon, pt))

    # ruído: placas que não são da carteira
    letras = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    conhecidas = set(sim.garantia["PLACA"])
    for _ in range(300):
        placa = "ZZ" + str(rng.choice(letras)) + str(int(rng.integers(10))) + str(rng.choice(letras)) + f"{int(rng.integers(100)):02d}"
        if placa in conhecidas:
            continue
        uf = str(rng.choice(UFS))
        pt = _ponto(rng, CIDADES[uf][0], uf)
        quando = FIM - pd.Timedelta(minutes=float(rng.uniform(0, 60 * 24 * 60)))
        linhas.append((placa, None, None, None, None, quando, pt["lat"], pt["lon"], pt))

    linhas.sort(key=lambda x: x[5])
    n = len(linhas)
    cap = pd.DataFrame({
        "IDPLACAS": np.arange(5_000_001, 5_000_001 + n),
        "PLATE": [x[0] for x in linhas], "BRAND": [x[1] for x in linhas], "MODEL": [x[2] for x in linhas],
        "COLOR": [x[3] for x in linhas], "YEAR_VEHICLE": [x[4] for x in linhas],
        "COMPANY_NAME": [x[8]["empresa"] for x in linhas],
        "CAPTURED": [x[5].floor("s") for x in linhas],
        "LATITUDE": [f"{x[6]:.6f}" for x in linhas], "LONGITUDE": [f"{x[7]:.6f}" for x in linhas],
        "STREET": [x[8]["rua"] for x in linhas], "STREET_NUMBER": [x[8]["numero"] for x in linhas],
        "POSTAL_CODE": [x[8]["cep"] for x in linhas], "LOCALITY": [x[8]["bairro"] for x in linhas],
        "CITY": [x[8]["cidade"] for x in linhas], "STATE": [x[8]["uf"] for x in linhas],
        "DEVICE_NAME": [x[8]["device"] for x in linhas], "CAMERA_TYPE": [x[8]["tipo_cam"] for x in linhas],
    })
    cap["STORAGE_PATH"] = [f"capturas/{q:%Y/%m/%d}/{i}.jpg" for q, i in zip(cap["CAPTURED"], cap["IDPLACAS"])]

    # defeitos de propósito (cada um tem teste em padroes)
    u = rng.random(n)
    m = u < 0.01
    cap.loc[m, "PLATE"] = [s[:3].lower() + "-" + s[3:].lower() for s in cap.loc[m, "PLATE"]]
    cap.loc[(u >= 0.01) & (u < 0.015), "LATITUDE"] = None
    zero = (u >= 0.015) & (u < 0.018)
    cap.loc[zero, ["LATITUDE", "LONGITUDE"]] = "0"
    m = (u >= 0.02) & (u < 0.03)
    cap.loc[m, "LOCALITY"] = rng.choice(NULOS_TXT, int(m.sum()))
    sao = cap["CITY"].str.startswith("SAO ") & (rng.random(n) < 0.3)
    cap.loc[sao, "CITY"] = "SÃO " + cap.loc[sao, "CITY"].str[4:]
    dup = cap[rng.random(n) < 0.005]
    cap = pd.concat([cap, dup], ignore_index=True).sort_values(["CAPTURED", "IDPLACAS"], kind="stable").reset_index(drop=True)

    # endereços do banco, por CPF (CPF repetido = o mesmo cliente com dois contratos)
    est = (sim.estoque.assign(PASTA=sim.estoque["CONTRATO"]).merge(p[["PASTA", "UF", "COMARCA"]], on="PASTA", how="left")
           .drop_duplicates("CPF").sort_values("CPF"))
    ends = []
    for cpf, pasta, uf, comarca in zip(est["CPF"], est["PASTA"], est["UF"], est["COMARCA"]):
        if pd.isna(uf):
            uf, comarca = "SP", "SAO PAULO"
        casa = casa_de.get(pasta)
        r = rng.random()
        if casa is not None and r < 0.70:
            cidade, uf_e, bairro = casa["cidade"], casa["uf"], casa["bairro"]
        elif r < 0.85 or len(CIDADES[uf]) == 1:
            cidade, uf_e, bairro = comarca, uf, str(rng.choice(BAIRROS))
        else:
            outra = [c for c in CIDADES[uf] if c[0] != comarca]
            cidade, uf_e, bairro = outra[int(rng.integers(len(outra)))][0], uf, str(rng.choice(BAIRROS))
        tipos = (["RESIDENCIAL"] if rng.random() < 0.9 else []) + (["COMERCIAL"] if rng.random() < 0.4 else [])
        tipos = tipos or ["COMERCIAL"]
        for k, tipo in enumerate(tipos):
            b = bairro if k == 0 else str(rng.choice(BAIRROS))
            ends.append((cpf, str(rng.choice(RUAS)), str(int(rng.integers(1, 3000))),
                         None if rng.random() < 0.7 else f"APTO {int(rng.integers(1, 300))}", b, cidade, uf_e,
                         _cep(cidade, b, rng), tipo,
                         pd.Timestamp("2015-01-01") + pd.Timedelta(days=int(rng.integers(0, 4300)))))
    end = pd.DataFrame(ends, columns=["CPF", "ENDERECO", "NUMERO", "COMPLEMENTO", "BAIRRO", "CIDADE", "UF", "CEP",
                                      "TIPO", "DATA_CADASTRO"])
    return cap, end


def _de_cache(sim: Simulacao, seed: int):
    chave = (id(sim), seed)
    if chave not in _cache:
        _cache.clear()
        _cache[chave] = (sim, _placas(sim, seed))       # guarda sim junto: o id não é reaproveitado enquanto vive
    return _cache[chave][1]


def capturas(sim: Simulacao, seed: int = 42) -> pd.DataFrame:
    return _de_cache(sim, seed)[0].copy()


def enderecos(sim: Simulacao, seed: int = 42) -> pd.DataFrame:
    return _de_cache(sim, seed)[1].copy()
