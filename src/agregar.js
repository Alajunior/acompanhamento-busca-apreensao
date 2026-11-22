// Agregações do painel (roda no navegador e no Node, sem DOM). Espelho de src/referencia.py, conferido pelo teste
// de paridade número a número. Ordenações com empate são sempre explícitas.
(function (g) {
  "use strict";
  const ETAPAS = ["EMENDAR INICIAL", "AGUARDANDO LIMINAR", "LIMINAR DEFERIDA", "MANDADO REQUERIDO", "MANDADO EXPEDIDO",
    "MANDADO NEGATIVO"];
  const FASES = ["MANDADO EXPEDIDO", "MANDADO NEGATIVO", "MANDADO REQUERIDO", "EMENDA REALIZADA", "EMENDAR INICIAL",
    "LIMINAR DEFERIDA", "LIMINAR INDEFERIDA", "AGUARDANDO LIMINAR"];
  const DILIGENCIA = "1º MANDADO EXPEDIDO";
  const TENTATIVAS = ["1º", "2º", "3º", "4º", "5º", "6º+"];
  const STATUS = ["REQUERIDO", "EXPEDIDO", "NEGATIVO"];
  const FAIXAS_IDADE = ["ate 5 anos", "6-10 anos", "11-15 anos", "16+ anos", "sem ano"];
  const FAIXAS_COBERTURA = ["< 50%", "50-80%", "80-100%", ">= 100%", "sem bem ou risco <= 0"];
  const SEM_ADV = "(sem advogado)", SEM_MARCA = "(sem marca)", SEM_COMARCA = "(sem comarca)";
  const GRUPOS = ["uf", "carteira", "adv", "etapa", "produto"];

  // ---------- utilitários ----------
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  const porChaves = (f) => (a, b) => { const x = f(a), y = f(b); for (let i = 0; i < x.length; i++) { const c = cmp(x[i], y[i]); if (c) return c; } return 0; };
  const soma = (xs) => { let s = 0; for (const x of xs) s += x; return s; };
  const conta = (rows, f) => { let n = 0; for (const r of rows) if (f(r)) n++; return n; };
  const contar = (rows, chave) => { const c = new Map(); for (const r of rows) { const k = chave(r); c.set(k, (c.get(k) || 0) + 1); } return c; };
  const arred = (x) => Math.floor(x + 0.5);
  const fmtInt = (n) => String(Math.trunc(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const fmtRS = (v) => v >= 1e6 ? "R$ " + (arred(v / 1e5) / 10).toFixed(1).replace(".", ",") + " mi"
    : v >= 1e3 ? "R$ " + fmtInt(arred(v / 1e3)) + " mil" : "R$ " + fmtInt(arred(v));
  const fmtPct0 = (f) => arred(f * 100) + "%";
  const plural = (n, s, p) => fmtInt(n) + " " + (n === 1 ? s : p);
  const faseDe = (t) => FASES.find((f) => t.includes(f)) || "SEM INFO";
  const mediana = (xs) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const pct = (n, base) => (base ? (n / base) * 100 : null);
  const diasEntre = (a, b) => Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);

  // ---------- estado ----------
  function fotos(pl) {
    if (pl.__cacheFotos) return pl.__cacheFotos;
    const out = []; let atual = new Map();
    for (const f of pl.fotos) {
      const e = f.estado;
      if (Array.isArray(e)) { atual = new Map(); for (const [i, t, d] of e) atual.set(i, [t, d]); }
      else { atual = new Map(atual); for (const i of e.sai) atual.delete(i); for (const [i, t, d] of e.muda) atual.set(i, [t, d]); }
      out.push(atual);
    }
    Object.defineProperty(pl, "__cacheFotos", { value: out, enumerable: false });
    return out;
  }
  const offset = (pl, dia) => diasEntre(pl.hoje, dia);

  function linhas(pl, k) {
    const p = pl.pastas, dic = pl.dic;
    const txt = (nome, i) => (p[nome][i] === null ? null : dic[nome][p[nome][i]]);
    const ids = [...fotos(pl)[k].keys()].sort((a, b) => a - b);
    return ids.map((i) => {
      const [t, d] = fotos(pl)[k].get(i); const tipo = dic.tipo[t];
      return { i, pasta: p.pasta[i], tipo, fase: faseDe(tipo), data: d, uf: txt("uf", i), carteira: txt("carteira", i),
        adv: txt("adv", i) || SEM_ADV, produto: txt("produto", i), comarca: txt("comarca", i) || SEM_COMARCA,
        marca: txt("marca", i) || SEM_MARCA, risco: p.risco[i], bem: p.bem[i], ano: p.ano_modelo[i] };
    });
  }

  function filtrar(rows, filtros, pl, sem) {
    const sel = GRUPOS.filter((gr) => gr !== sem).map((gr) => [gr === "etapa" ? "fase" : gr, new Set(filtros[gr] || [])]);
    const de = filtros.de ? offset(pl, filtros.de) : null, ate = filtros.ate ? offset(pl, filtros.ate) : null;
    return rows.filter((r) => {
      for (const [campo, v] of sel) if (v.size && !v.has(r[campo])) return false;
      if (de !== null || ate !== null) {
        if (r.data === null || (de !== null && r.data < de) || (ate !== null && r.data > ate)) return false;
      }
      return true;
    });
  }

  // ---------- cards ----------
  function kpis(rows, h) {
    return { processos: rows.length, diligencia: conta(rows, (r) => r.tipo === DILIGENCIA),
      vencidos: conta(rows, (r) => r.data !== null && r.data < h), hoje: conta(rows, (r) => r.data === h),
      prox7: conta(rows, (r) => r.data !== null && h < r.data && r.data <= h + 7),
      risco: soma(rows.filter((r) => r.risco !== null).map((r) => r.risco)) };
  }

  function tabelas(rows, ordemFollow) {
    const prod = contar(rows, (r) => r.tipo), fol = contar(rows, (r) => r.fase);
    const conhecidas = ordemFollow.filter((f) => fol.get(f));
    const outras = [...fol.keys()].filter((f) => !ordemFollow.includes(f)).sort(cmp);
    const dil = conta(rows, (r) => r.tipo === DILIGENCIA);
    return { produtivos: [...prod.keys()].sort(cmp).map((t) => [t, prod.get(t)]),
      follow: [...conhecidas, ...outras].map((f) => [f, fol.get(f)]), diligencia: dil ? [[DILIGENCIA, dil]] : [] };
  }

  function tentativa(tipo) {
    const partes = tipo.split(" MANDADO ");
    if (partes.length !== 2) return null;
    const rot = partes[0] === "6º OU +" ? "6º+" : partes[0];
    return TENTATIVAS.includes(rot) && STATUS.includes(partes[1]) ? [rot, partes[1]] : null;
  }

  function escada(rows) {
    const m = {}; for (const t of TENTATIVAS) for (const s of STATUS) m[t + "|" + s] = 0;
    for (const r of rows) { const k = tentativa(r.tipo); if (k) m[k[0] + "|" + k[1]]++; }
    const total = soma(Object.values(m));
    if (!total) return null;
    let restantes = total; const out = [];
    for (const t of TENTATIVAS) {
      const tot = m[t + "|REQUERIDO"] + m[t + "|EXPEDIDO"] + m[t + "|NEGATIVO"];
      out.push({ tentativa: t, REQUERIDO: m[t + "|REQUERIDO"], EXPEDIDO: m[t + "|EXPEDIDO"], NEGATIVO: m[t + "|NEGATIVO"],
        total: tot, chegou: (restantes / total) * 100 });
      restantes -= tot;
    }
    return { linhas: out, em_mandado: total };
  }

  function prazos(rows, h) {
    const out = [];
    for (const e of ETAPAS) {
      const d = rows.filter((r) => r.fase === e).map((r) => r.data);
      if (!d.length) continue;
      out.push([e, d.filter((x) => x !== null && x < h).length, d.filter((x) => x === h).length,
        d.filter((x) => x !== null && h < x && x <= h + 7).length, d.filter((x) => x !== null && x > h + 7).length,
        d.filter((x) => x === null).length]);
    }
    return out;
  }

  function advogados(rows, h) {
    const por = new Map();
    for (const r of rows) { if (!por.has(r.adv)) por.set(r.adv, []); por.get(r.adv).push(r); }
    const nomes = [...por.keys()].sort(porChaves((a) => [a === SEM_ADV ? 1 : 0, a]));
    const lin = nomes.map((adv) => {
      const rs = por.get(adv); const venc = conta(rs, (r) => r.data !== null && r.data < h);
      return { adv, processos: rs.length, vencidos: venc, hoje: conta(rs, (r) => r.data === h),
        risco: soma(rs.filter((r) => r.risco !== null).map((r) => r.risco)),
        etapas: ETAPAS.map((e) => conta(rs, (r) => r.fase === e)), pct_venc: (venc / rs.length) * 100 };
    });
    const totP = soma(lin.map((x) => x.processos));
    const pctCart = totP ? (soma(lin.map((x) => x.vencidos)) / totP) * 100 : null;
    const comp = lin.filter((x) => x.adv !== SEM_ADV && x.processos >= 30);
    const med = comp.length >= 3 ? mediana(comp.map((x) => x.processos)) : null;
    for (const x of lin) {
      const eComp = x.adv !== SEM_ADV && x.processos >= 30;
      x.razao = med && eComp ? x.processos / med : null;
      x.carga_alta = Boolean(med && eComp && x.processos / med >= 1.25);
      x.venc_alto = Boolean(eComp && pctCart !== null && x.pct_venc >= pctCart + 10);
    }
    return { linhas: lin, mediana: med, n_comparaveis: comp.length, pct_carteira: pctCart };
  }

  function mapaUF(rows) {
    const m = new Map();
    for (const r of rows) {
      if (r.uf === null) continue;
      if (!m.has(r.uf)) m.set(r.uf, [0, 0, 0]);
      const x = m.get(r.uf); x[0] += 1; x[1] += r.risco || 0; x[2] += r.fase === "MANDADO NEGATIVO" ? 1 : 0;
    }
    const out = {}; for (const k of [...m.keys()].sort(cmp)) out[k] = m.get(k);
    return out;
  }

  function faixaIdade(ano) {
    if (ano === null) return "sem ano";
    const idade = 2026 - ano;
    if (idade < -1 || idade > 60) return "sem ano";
    return idade <= 5 ? "ate 5 anos" : idade <= 10 ? "6-10 anos" : idade <= 15 ? "11-15 anos" : "16+ anos";
  }

  const top = (c, n) => { const it = [...c.entries()].sort(porChaves((kv) => [-kv[1], kv[0]])); return (n === null ? it : it.slice(0, n)).map(([k, v]) => [k, v]); };

  function perfil(rows, nMarcas) {
    const prod = contar(rows, (r) => r.produto || "(sem produto)");
    const idade = contar(rows, (r) => faixaIdade(r.ano));
    const marcas = top(contar(rows, (r) => r.marca), nMarcas);
    const demais = rows.length - soma(marcas.map((x) => x[1]));
    return { base: soma([...idade.values()]), produto: top(prod, null),
      idade: FAIXAS_IDADE.filter((f) => idade.get(f)).map((f) => [f, idade.get(f)]),
      marcas: demais > 0 ? [...marcas, ["(demais marcas)", demais]] : marcas };
  }

  function comarcas(rows, n) {
    const por = new Map();
    for (const r of rows) { if (!por.has(r.comarca)) por.set(r.comarca, []); por.get(r.comarca).push(r); }
    return [...por.entries()].sort(porChaves((kv) => [-kv[1].length, kv[0]])).slice(0, n).map(([nome, rs]) => {
      const ufs = contar(rs.filter((r) => r.uf), (r) => r.uf);
      const uf = ufs.size ? [...ufs.keys()].sort(porChaves((u) => [-ufs.get(u), u]))[0] : null;
      return [nome, uf, rs.length, (conta(rs, (r) => r.fase === "MANDADO NEGATIVO") / rs.length) * 100];
    });
  }

  function resumoRegiao(rows, h) {
    const k = kpis(rows, h), n = k.processos;
    const riscos = rows.filter((r) => r.risco !== null).map((r) => r.risco);
    const neg = conta(rows, (r) => r.fase === "MANDADO NEGATIVO");
    const advs = contar(rows.filter((r) => r.adv !== SEM_ADV), (r) => r.adv);
    const mais = advs.size ? [...advs.keys()].sort(porChaves((a) => [-advs.get(a), a]))[0] : null;
    const p = {}; for (const c of ["vencidos", "hoje", "prox7", "diligencia"]) p[c] = pct(k[c], n);
    return { kpis: k, pct: p, negativo: neg, pct_negativo: pct(neg, n),
      risco_medio: riscos.length ? soma(riscos) / riscos.length : null,
      etapas: ETAPAS.map((e) => [e, conta(rows, (r) => r.fase === e)]), perfil: perfil(rows, 5), comarcas: comarcas(rows, 5),
      advogados: { qtd: advs.size, sem_advogado: conta(rows, (r) => r.adv === SEM_ADV),
        mais: mais ? [mais, advs.get(mais), (advs.get(mais) / n) * 100] : null } };
  }

  function regioes(semUF, ufs, h) {
    if (!ufs.length) return null;
    const brasil = resumoRegiao(semUF, h);
    const out = [...ufs].sort(cmp).map((uf) => {
      const r = resumoRegiao(semUF.filter((x) => x.uf === uf), h);
      r.uf = uf; r.part_processos = pct(r.kpis.processos, brasil.kpis.processos);
      r.part_risco = brasil.kpis.risco ? (r.kpis.risco / brasil.kpis.risco) * 100 : null;
      return r;
    });
    return { modo: ufs.length === 1 ? 1 : ufs.length <= 4 ? 2 : 5, ufs: out, brasil };
  }

  function movimentacao(pl, pub, filtros) {
    if (pub.origem === "oficial") return { vazia: "oficial" };
    if (pub.base === null) return { vazia: "sem_base" };
    if (pub.base === pub.foto) return { vazia: "base" };
    const base = new Map(filtrar(linhas(pl, pub.base), filtros, pl).map((r) => [r.i, r]));
    const atual = new Map(filtrar(linhas(pl, pub.foto), filtros, pl).map((r) => [r.i, r]));
    const num = (a, b) => a - b;
    const entradas = [...atual.keys()].filter((i) => !base.has(i)).sort(num);
    const saidas = [...base.keys()].filter((i) => !atual.has(i)).sort(num);
    const comuns = [...atual.keys()].filter((i) => base.has(i)).sort(num);
    const mudTipo = comuns.filter((i) => atual.get(i).tipo !== base.get(i).tipo);
    const trans = new Map();
    for (const i of mudTipo) { const k = base.get(i).tipo + "\u0000" + atual.get(i).tipo; trans.set(k, (trans.get(k) || 0) + 1); }
    const pasta = pl.pastas.pasta;
    return { entradas: entradas.length, saidas: saidas.length, mud_agendamento: mudTipo.length,
      mud_etapa: conta(comuns, (i) => atual.get(i).fase !== base.get(i).fase),
      transicoes: [...trans.entries()].map(([k, n]) => [...k.split("\u0000"), n]).sort(porChaves((x) => [-x[2], x[0], x[1]])),
      movimentos: [...entradas.map((i) => ["entrada", pasta[i]]), ...saidas.map((i) => ["saida", pasta[i]]),
        ...mudTipo.map((i) => ["mudou de tipo", pasta[i]])] };
  }

  function riscoEtapa(rows) {
    const lin = [];
    for (const e of ETAPAS) {
      const rs = rows.filter((r) => r.fase === e);
      if (rs.length) lin.push([e, rs.length, soma(rs.map((r) => r.risco || 0)), soma(rs.map((r) => r.bem || 0))]);
    }
    const cob = rows.filter((r) => r.risco !== null && r.risco > 0 && r.bem !== null).map((r) => r.bem / r.risco);
    const med = mediana(cob);
    return { linhas: lin, risco_total: soma(rows.map((r) => r.risco || 0)), bem_total: soma(rows.map((r) => r.bem || 0)),
      cobertura_mediana: med !== null ? med * 100 : null, sem_estoque: conta(rows, (r) => r.risco === null) };
  }

  function faixaCobertura(r) {
    if (r.risco === null) return null;
    if (r.risco <= 0 || r.bem === null) return "sem bem ou risco <= 0";
    const c = r.bem / r.risco;
    return c < 0.5 ? "< 50%" : c < 0.8 ? "50-80%" : c < 1.0 ? "80-100%" : ">= 100%";
  }

  function riscoUF(rows) {
    const por = new Map();
    for (const r of rows) if (r.uf) { if (!por.has(r.uf)) por.set(r.uf, []); por.get(r.uf).push(r); }
    const lin = [...por.entries()].map(([uf, rs]) => {
      const risco = soma(rs.map((r) => r.risco || 0)), bem = soma(rs.map((r) => r.bem || 0));
      return [uf, rs.length, risco, bem, risco ? (bem / risco) * 100 : null];
    }).sort(porChaves((x) => [-x[2], x[0]]));
    const faixas = contar(rows.filter((r) => faixaCobertura(r)), faixaCobertura);
    return { linhas: lin, faixas: FAIXAS_COBERTURA.map((f) => [f, faixas.get(f) || 0]) };
  }

  function carteiraEtapa(rows) {
    const carts = [...new Set(rows.filter((r) => r.carteira).map((r) => r.carteira))].sort(cmp);
    return { carteiras: carts, etapas: [...ETAPAS],
      qtd: carts.map((c) => ETAPAS.map((e) => conta(rows, (r) => r.carteira === c && r.fase === e))),
      risco: carts.map((c) => ETAPAS.map((e) => soma(rows.filter((r) => r.carteira === c && r.fase === e).map((r) => r.risco || 0)))) };
  }

  const IMPACTOS = {
    liminar_deferida: "É a etapa imediatamente anterior ao pedido de mandado: priorizar esses requerimentos tende a encurtar o caminho até a diligência.",
    vencidos: "Agendamento vencido sem andamento pode atrasar a etapa seguinte do processo.",
    escada: "Cada nova tentativa consome diligência e prazo; vale revisar endereço ou estratégia desses casos.",
    uf_negativo: "A concentração pode indicar gargalo local (endereço, comarca ou diligência) — vale checar com o escritório.",
  };

  function destaques(rows, h) {
    if (!rows.length) return [];
    const out = [];
    const lim = rows.filter((r) => r.fase === "LIMINAR DEFERIDA");
    if (lim.length) {
      const venc = conta(lim, (r) => r.data !== null && r.data < h);
      out.push(["liminar_deferida", `${plural(lim.length, "processo", "processos")} com liminar deferida aguardando requerimento de mandado (${fmtRS(soma(lim.map((r) => r.risco || 0)))} em risco). ${fmtInt(venc)} deles com data de agendamento já vencida.`]);
    }
    const k = kpis(rows, h);
    if (k.vencidos) {
      const eleg = advogados(rows, h).linhas.filter((x) => x.adv !== SEM_ADV && x.processos >= 30).map((x) => x.vencidos / x.processos);
      const y = eleg.length ? Math.max(...eleg) : 0;
      const cauda = y > 0 ? `; entre advogados com 30+ processos, a maior proporção de vencidos é ${fmtPct0(y)}.` : ".";
      out.push(["vencidos", `${plural(k.vencidos, "agendamento vencido", "agendamentos vencidos")} (${fmtPct0(k.vencidos / k.processos)} da carteira filtrada)${cauda}`]);
    }
    const esc = escada(rows);
    if (esc && esc.em_mandado >= 20) {
      const n3 = soma(esc.linhas.slice(2).map((x) => x.total));
      if (n3) out.push(["escada", `${plural(n3, "processo", "processos")} (${fmtPct0(n3 / esc.em_mandado)} dos que estão em mandado) já passaram da 2ª tentativa.`]);
    }
    const mapa = mapaUF(rows), vs = Object.values(mapa), tq = soma(vs.map((v) => v[0]));
    if (tq) {
      const geral = (soma(vs.map((v) => v[2])) / tq) * 100;
      const cands = Object.entries(mapa).filter(([, v]) => v[0] >= 30).map(([uf, v]) => [(v[2] / v[0]) * 100, uf]);
      if (cands.length) {
        const [p, uf] = cands.sort(porChaves((c) => [-c[0], c[1]]))[0];
        if (p - geral >= 10) out.push(["uf_negativo", `${uf}: ${arred(p)}% dos processos da UF estão em mandado negativo, contra ${arred(geral)}% no total.`]);
      }
    }
    return out.map(([chave, achado]) => ({ chave, achado, impacto: IMPACTOS[chave] }));
  }

  function evolucao(pl, pub, filtros) {
    const fs = pl.fotos, ultima = new Map();
    fs.forEach((f, k) => {
      if (f.dia === pl.hoje) return;
      if (!ultima.has(f.dia) || f.hora >= fs[ultima.get(f.dia)].hora) ultima.set(f.dia, k);
    });
    ultima.set(pl.hoje, pub.foto);
    const dias = [...ultima.keys()].sort(cmp);
    const n = diasEntre(dias[0], dias[dias.length - 1]);
    const out = { dias: [], lacuna: [], reconstruido: [], total: [], por_etapa: {}, extintas: [] };
    for (const e of ETAPAS) out.por_etapa[e] = [];
    const d0 = Date.parse(dias[0] + "T00:00:00Z");
    for (let j = 0; j <= n; j++) {
      const d = new Date(d0 + j * 86400000).toISOString().slice(0, 10);
      out.dias.push(d);
      if (!ultima.has(d)) {
        out.lacuna.push(true); out.reconstruido.push(false); out.total.push(null); out.extintas.push(null);
        for (const e of ETAPAS) out.por_etapa[e].push(null);
        continue;
      }
      const k = ultima.get(d), rs = filtrar(linhas(pl, k), filtros, pl);
      out.lacuna.push(false); out.reconstruido.push(fs[k].origem === "reconstruido"); out.total.push(rs.length);
      out.extintas.push(conta(rs, (r) => r.fase === "EMENDA REALIZADA"));
      for (const e of ETAPAS) out.por_etapa[e].push(conta(rs, (r) => r.fase === e));
    }
    return out;
  }

  function tudo(pl, agora, filtros) {
    const pub = pl.publicacoes.find((p) => p.agora === agora);
    const todas = linhas(pl, pub.foto);
    const rows = filtrar(todas, filtros, pl), semUF = filtrar(todas, filtros, pl, "uf");
    const ref = (k) => {
      if (k === null) return null;
      const f = pl.fotos[k];
      return { kpis: kpis(filtrar(linhas(pl, k), filtros, pl), offset(pl, f.dia)), dia: f.dia, hora: f.hora, origem: f.origem };
    };
    return { kpis: { atual: kpis(rows, 0), inicio: ref(pub.base), anterior: ref(pub.anterior) },
      tabelas: tabelas(rows, pl.ordens.follow), escada: escada(rows), prazos: prazos(rows, 0), advogados: advogados(rows, 0),
      mapa_uf: mapaUF(semUF), regioes: regioes(semUF, filtros.uf || [], 0), movimentacao: movimentacao(pl, pub, filtros),
      destaques: destaques(rows, 0), risco_etapa: riscoEtapa(rows), risco_uf: riscoUF(rows), carteira_etapa: carteiraEtapa(rows),
      comarcas: comarcas(rows, 15), perfil: perfil(rows, 10), evolucao: evolucao(pl, pub, filtros) };
  }

  const A = { ETAPAS, tudo, linhas, filtrar, kpis, fmtInt, fmtRS, fmtPct0, arred, faseDe, offset };
  g.Agregar = A;
  if (typeof module !== "undefined" && module.exports) module.exports = A;
})(typeof window !== "undefined" ? window : globalThis);
