// Aba Busca e Apreensão (modo Planilha): segmentações → recortes → as 12 seções e a linha do tempo.
// Roda no navegador e no Node, sem DOM. Conferido contra src/referencia_ba.py pelo teste de paridade.
(function (g) {
  "use strict";
  const ETAPAS = ["Apreendido", "Mandado expedido", "Localizado (diligência)", "Localização encerrada sem apreensão"];
  const ABERTAS = ["Mandado expedido", "Localizado (diligência)"];
  const FASES = ["JUDICIAL 1", "JUDICIAL 2", "JUDICIAL 3", "PREJUÍZO"];
  const FAIXAS = [["121 A 360", ["JUDICIAL 1", "JUDICIAL 2"]], ["360 A 720", ["JUDICIAL 3"]], ["> 720", ["PREJUÍZO"]]];
  const OUTRAS = "OUTRAS FASES";
  const QUEBRAS = ["ATÉ DIA 10", "DO DIA 11 AO DIA 20", "DO DIA 21 AO DIA 31"];
  const SEM_LOC = "(sem localizador)";
  const FATORES = [["100%", 1.0], ["120%", 1.2], ["130%", 1.3]];
  const DIA = 86400000;

  /* ---------- números como o Excel: o valor com 15 algarismos, arredondado no decimal ---------- */
  function arredDec(x, casas, cima) {
    const y = Number(Number(x).toPrecision(15));
    const neg = y < 0;
    let s = String(Math.abs(y));
    if (s.includes("e")) s = Math.abs(y).toFixed(20).replace(/0+$/, "");
    let [int, frac = ""] = s.split(".");
    if (frac.length <= casas) return y;
    const resto = frac.slice(casas);
    let sobe = cima ? /[1-9]/.test(resto) : resto[0] >= "5";
    let dig = (int + frac.slice(0, casas)).split("").map(Number);
    if (sobe) {
      let i = dig.length - 1;
      while (i >= 0) { if (dig[i] === 9) { dig[i] = 0; i--; } else { dig[i]++; break; } }
      if (i < 0) dig.unshift(1);
    }
    const txt = dig.join("");
    const r = casas ? Number(txt.slice(0, txt.length - casas) + "." + txt.slice(txt.length - casas)) : Number(txt);
    return neg ? -r : r;
  }
  const arred = (x, c = 0) => arredDec(x, c, false);
  const arredCima = (x, c = 0) => arredDec(x, c, true);

  /* ---------- datas (sempre em UTC, para não depender do fuso) ---------- */
  const dataUTC = iso => new Date(iso.slice(0, 10) + "T00:00:00Z");
  const isoDia = d => d.toISOString().slice(0, 10);
  const mesKey = m => { const [mm, aa] = m.split("/").map(Number); return aa * 100 + mm; };
  function feriadosDe(ba) { if (!ba.__fer) ba.__fer = new Set(ba.feriados); return ba.__fer; }
  function ehUtil(d, fer) { const w = d.getUTCDay(); return w !== 0 && w !== 6 && !fer.has(isoDia(d)); }
  function diasUteis(mes, fer) {
    const [mm, aa] = mes.split("/").map(Number);
    const out = []; const d = new Date(Date.UTC(aa, mm - 1, 1));
    while (d.getUTCMonth() === mm - 1) { if (ehUtil(d, fer)) out.push(isoDia(d)); d.setUTCDate(d.getUTCDate() + 1); }
    return out;
  }
  function duIndice(iso, fer) {
    const mes = `${Number(iso.slice(5, 7))}/${iso.slice(0, 4)}`;
    return diasUteis(mes, fer).filter(x => x <= iso).length;
  }
  function duMes(ba, mes) {
    const fer = feriadosDe(ba), total = diasUteis(mes, fer).length;
    const h = ba.hoje, kh = Number(h.slice(0, 4)) * 100 + Number(h.slice(5, 7)), km = mesKey(mes);
    if (km > kh) return [total, 0];
    if (km < kh) return [total, total];
    return [total, duIndice(h, fer)];
  }

  /* ---------- decodificação do ba.json ---------- */
  function estado(ba, agora) {
    const k = ba.agoras.indexOf(agora), cols = ba.colunas;
    let lin = new Map();
    for (const c of ba.cargas.slice(0, k + 1)) {
      if (c.base) lin = new Map(c.base.map(r => [r[0], r]));
      else { for (const p of c.sai) lin.delete(p); for (const r of c.muda) lin.set(r[0], r); }
    }
    let pas = {};
    for (const c of ba.passagens.slice(0, k + 1)) {
      if (c.base) pas = Object.assign({}, c.base);
      else { for (const p of c.sai) delete pas[p]; Object.assign(pas, c.muda); }
    }
    const o = ba.opcoes, base = new Date(ba.base_minutos + ":00Z").getTime();
    const agoraMs = new Date(`${ba.hoje}T${agora}:00Z`).getTime();
    const iso = m => (m === null ? null : new Date(base + m * 60000).toISOString().slice(0, 16));
    const passagens = [];
    for (const pasta of Object.keys(pas).sort()) {
      for (const r of pas[pasta]) {
        const rec = iso(r[1]), ate = iso(r[2]);
        passagens.push({
          PASTA: pasta, LOCALIZADOR: o.localizadores[r[0]], RECEBEU: rec, ATE: ate,
          DIAS: ate !== null ? r[3] : arred((agoraMs - (base + r[1] * 60000)) / DIA, 1),
          RESULTADO: ba.resultados[r[4]], FICHAS: r[5], UF: r[6] === null ? null : o.ufs[r[6]],
          ADVOGADO: r[7] === null ? null : o.advogados[r[7]], APREENDEU: !!r[8], VALOR_PERFORMANCE: r[9],
          DIAS_ATE_LOCALIZAR: r[10], MES_ENVIO: `${Number(rec.slice(5, 7))}/${rec.slice(0, 4)}`,
        });
      }
    }
    const linhas = [...lin.keys()].sort().map(p => Object.fromEntries(cols.map((c, i) => [c, lin.get(p)[i]])));
    const carga = ba.cargas[k];
    return { agora, quando: carga.quando, aviso: carga.aviso, linhas, passagens };
  }

  /* ---------- recortes ---------- */
  function norm(f) {
    const out = {};
    for (const k of ["adv", "fase", "uf", "etapa", "localizador"]) out[k] = (f && f[k]) ? f[k].slice() : [];
    out.mes = (f && f.mes) || null;
    return out;
  }
  function cmpLista(a, b) {
    const ea = ETAPAS.indexOf(a.ETAPA), eb = ETAPAS.indexOf(b.ETAPA);
    if (ea !== eb) return ea - eb;
    const da = a.DT_LOCALIZACAO, db = b.DT_LOCALIZACAO;
    if (!!da !== !!db) return da ? -1 : 1;
    if (da && da !== db) return da > db ? -1 : 1;
    return a.PASTA < b.PASTA ? -1 : a.PASTA > b.PASTA ? 1 : 0;
  }
  function recortes(est, filtros) {
    const f = norm(filtros), tem = (l, v) => !l.length || l.includes(v);
    const recorte = est.linhas.filter(r => tem(f.adv, r.ADVOGADO) && tem(f.fase, r.FASE) && tem(f.uf, r.UF) && tem(f.localizador, r.LOCALIZADOR));
    const etapa = r => tem(f.etapa, r.ETAPA);
    const lista = recorte.filter(r => etapa(r) && (!f.mes || r.MES_EVENTO === f.mes)).sort(cmpLista);
    const abertos = recorte.filter(r => etapa(r) && ABERTAS.includes(r.ETAPA)).sort(cmpLista);
    const passagens = est.passagens.filter(p => tem(f.adv, p.ADVOGADO) && tem(f.uf, p.UF) && tem(f.localizador, p.LOCALIZADOR) && (!f.mes || p.MES_ENVIO === f.mes));
    return { recorte, lista, lista_abertos: abertos, passagens, filtros: f };
  }

  /* ---------- pivôs ---------- */
  function soma(vals) {
    let s = 0, n = 0;
    for (const v of vals) if (v !== null && v !== undefined) { s += v; n++; }
    return n ? arred(s, 2) : null;
  }
  function ordemFase(f) {
    if (FASES.includes(f)) return [0, FASES.indexOf(f), ""];
    if (f === "SEM FASE" || f === "(vazio)") return [2, 0, f];
    return [1, 0, f];
  }
  function cmpTupla(a, b) {
    for (let i = 0; i < a.length; i++) {
      if (a[i] === b[i]) continue;
      if (typeof a[i] === "boolean") return a[i] ? 1 : -1;
      return a[i] < b[i] ? -1 : 1;
    }
    return 0;
  }
  const cmpTxt = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  const adv = a => a || "SEM ADVOGADO";
  const uniq = xs => [...new Set(xs)];

  function pivoAdvFase(linhas) {
    const grupos = new Map();
    for (const r of linhas) {
      const k = adv(r.ADVOGADO) + "\u0000" + (r.FASE || "SEM FASE");
      if (!grupos.has(k)) grupos.set(k, []);
      grupos.get(k).push(r);
    }
    const chaves = [...grupos.keys()].map(k => k.split("\u0000"));
    const ag = (rs, extra) => Object.assign({}, extra, { qtd: rs.length, valor_risco: soma(rs.map(r => r.VALOR_RISCO)),
      valor_performance: soma(rs.map(r => r.VALOR_PERFORMANCE)) });
    const advFase = [], porFase = [], porAdv = [];
    for (const a of uniq(chaves.map(k => k[0])).sort(cmpTxt)) {
      const fases = chaves.filter(k => k[0] === a).map(k => k[1]).sort((x, y) => cmpTupla(ordemFase(x), ordemFase(y)));
      let todas = [];
      for (const fa of fases) {
        const rs = grupos.get(a + "\u0000" + fa);
        advFase.push(ag(rs, { advogado: a, fase: fa, tipo: "" }));
        todas = todas.concat(rs);
      }
      const sub = ag(todas, { advogado: a, fase: null, tipo: "sub" });
      advFase.push(sub);
      porAdv.push(Object.assign({}, sub, { tipo: "" }));
    }
    if (linhas.length) {
      const tot = ag(linhas, { advogado: null, fase: null, tipo: "total" });
      advFase.push(tot);
      for (const fa of uniq(chaves.map(k => k[1])).sort((x, y) => cmpTupla(ordemFase(x), ordemFase(y)))) {
        const rs = chaves.filter(k => k[1] === fa).flatMap(k => grupos.get(k[0] + "\u0000" + k[1]));
        porFase.push(ag(rs, { fase: fa, tipo: "" }));
      }
      porFase.push(Object.assign({}, tot));
      porAdv.push(tot);
    }
    return { adv_fase: advFase, por_fase: porFase.map(x => { const y = Object.assign({}, x); delete y.advogado; return y; }), por_adv: porAdv };
  }

  function mandados(linhas) {
    const rs = linhas.filter(r => r.ETAPA === "Mandado expedido");
    const grupos = new Map();
    for (const r of rs) {
      const k = [adv(r.ADVOGADO), r.FASE || "SEM FASE", r.OBSERVACAO || "(vazio)", r.COMPLEMENTO || "(vazio)"];
      const s = k.join("\u0000");
      if (!grupos.has(s)) grupos.set(s, { k, rs: [] });
      grupos.get(s).rs.push(r);
    }
    const ag = (g2, extra) => Object.assign({}, extra, { valor_risco: soma(g2.map(r => r.VALOR_RISCO)),
      valor_performance: soma(g2.map(r => r.VALOR_PERFORMANCE)), qtd: g2.length });
    const out = [], todos = [...grupos.values()];
    for (const a of uniq(todos.map(x => x.k[0])).sort(cmpTxt)) {
      const ks = todos.filter(x => x.k[0] === a).sort((x, y) => {
        const c = cmpTupla(ordemFase(x.k[1]), ordemFase(y.k[1]));
        return c || cmpTxt(x.k[2], y.k[2]) || cmpTxt(x.k[3], y.k[3]);
      });
      for (const x of ks) out.push(ag(x.rs, { advogado: a, fase: x.k[1], observacao: x.k[2], complemento: x.k[3], tipo: "" }));
      out.push(ag(ks.flatMap(x => x.rs), { advogado: a, fase: null, observacao: null, complemento: null, tipo: "sub" }));
    }
    if (rs.length) out.push(ag(rs, { advogado: null, fase: null, observacao: null, complemento: null, tipo: "total" }));
    return out;
  }

  /* ---------- metas ---------- */
  function linhaMeta(mq, mv, rq, rv, duTotal, duAtual) {
    const rest = duTotal - duAtual;
    const div = (a, b) => (a === null || b === null || b === 0 ? null : a / b);
    const pct = (r, m) => (m === null ? null : (m === 0 ? 0 : r / m));
    const faltaQ = mq === null ? null : rq - mq;
    const faltaV = mv === null ? null : arred(rv - mv, 2);
    const tktReal = div(rv, rq);
    const projQ = duAtual > 0 ? arred(rq / duAtual * rest) + rq : null;
    const projV = projQ === null ? null : (tktReal !== null ? arred(projQ * tktReal, 2) : 0);
    return {
      meta_qtd: mq, meta_valor: mv, tkt_meta: div(mv, mq), real_qtd: rq, real_valor: rv, tkt_real: tktReal,
      pct_qtd: pct(rq, mq), pct_valor: pct(rv, mv), falta_qtd: faltaQ, falta_valor: faltaV,
      tkt_falta: faltaQ === null || faltaV === null ? null : (faltaQ === 0 ? faltaV : faltaV / faltaQ),
      falta_dia_qtd: faltaQ === null || rest <= 0 ? null : arredCima(-faltaQ / rest, 0),
      falta_dia_valor: faltaV === null || rest <= 0 ? null : arred(-faltaV / rest, 2),
      proj_qtd: projQ, proj_valor: projV,
      proj_pct_qtd: projQ === null ? null : pct(projQ, mq), proj_pct_valor: projV === null ? null : pct(projV, mv),
    };
  }
  function curva(metaTotal, fator, duTotal, realAcum) {
    const total = arred(metaTotal * fator), nec = arredCima(total / duTotal, 1);
    const acum = [], dif = [], atual = [];
    for (let d = 1; d <= duTotal; d++) acum.push(arred(nec * d, 1));
    for (let d = 0; d < duTotal; d++) {
      const r = d < realAcum.length ? realAcum[d] : null;
      dif.push(r === null ? null : arred(r - acum[d]));
      atual.push(d === 0 || r === null ? null : arred(acum[d]) - realAcum[d - 1]);
    }
    return { total, necessidade_dia: nec, acum, diferenca: dif, atual };
  }
  const chaveTxt = s => String(s).toUpperCase().split(/\s+/).filter(Boolean).join(" ");
  function metasDoMes(lista, mes) {
    const out = new Map();
    for (const [m, ch, q, v] of lista) if (m === mes) out.set(chaveTxt(ch), [q, v]);
    return out;
  }
  function metaFaixas(ba, mes) {
    const mf = metasDoMes(ba.metas.faixa, mes);
    if (!mf.size) return null;
    const gg = mf.get("121 A 360") || [null, null];
    const q1 = (mf.get("JUDICIAL 1") || [null])[0] || 0, q2 = (mf.get("JUDICIAL 2") || [null])[0] || 0;
    const out = new Map();
    for (const fa of FASES) {
      let [q, v] = mf.get(fa) || [null, null];
      if ((fa === "JUDICIAL 1" || fa === "JUDICIAL 2") && v === null && q !== null && gg[1] !== null && q1 + q2 > 0)
        v = arred(q * (gg[1] / (q1 + q2)), 2);
      out.set(fa, [q, v]);
    }
    for (const [nome, fases] of FAIXAS) {
      const qs = fases.map(f => out.get(f)[0]).filter(x => x !== null);
      const vs = fases.map(f => out.get(f)[1]).filter(x => x !== null);
      const linha = mf.get(nome) || [null, null];
      out.set(nome, [qs.length ? qs.reduce((a, b) => a + b, 0) : linha[0], vs.length ? arred(vs.reduce((a, b) => a + b, 0), 2) : linha[1]]);
    }
    return out;
  }
  const realizado = rs => [rs.length, arred(rs.reduce((s, r) => s + (r.VALOR_PERFORMANCE || 0), 0), 2)];

  function metaBanco(ba, recorte, mes) {
    const [duTotal, duAtual] = duMes(ba, mes);
    const ap = recorte.filter(r => r.MES_APREENSAO === mes);
    const metas = metaFaixas(ba, mes);
    const pega = k => (metas && metas.has(k) ? metas.get(k) : [null, null]);
    let linhas = [];
    const add = (chave, tipo, rs, meta) => {
      const [q, v] = realizado(rs);
      linhas.push(Object.assign({ chave, tipo }, linhaMeta(meta[0], meta[1], q, v, duTotal, duAtual)));
    };
    for (const [nome, fases] of FAIXAS) {
      for (const fa of fases) add(fa, "fase", ap.filter(r => r.FASE === fa), pega(fa));
      add(nome, "faixa", ap.filter(r => fases.includes(r.FASE)), pega(nome));
    }
    const outras = ap.filter(r => !FASES.includes(r.FASE));
    if (outras.length) {
      const [q, v] = realizado(outras);
      linhas.push(Object.assign({ chave: OUTRAS, tipo: "outras" }, linhaMeta(null, null, q, v, duTotal, 0)));
    }
    const mt = metas ? FAIXAS.map(([n]) => metas.get(n)) : [];
    const qs = mt.map(m => m[0]).filter(x => x !== null), vs = mt.map(m => m[1]).filter(x => x !== null);
    add("TOTAL", "total", ap, [qs.length ? qs.reduce((a, b) => a + b, 0) : null, vs.length ? arred(vs.reduce((a, b) => a + b, 0), 2) : null]);
    if (!linhas.some(l => l.real_qtd || l.meta_qtd)) linhas = [];
    return { mes, du_total: duTotal, du_atual: duAtual, aviso: metas ? null : `meta não informada para ${mes}`, linhas };
  }
  function duDe(ba, iso) { return Math.max(1, duIndice(iso, feriadosDe(ba))); }
  function serieDia(ba, rs, duTotal, duAtual) {
    const cont = new Array(duTotal).fill(0);
    for (const r of rs) cont[duDe(ba, r.DT_APREENSAO) - 1]++;
    return cont.map((c, i) => (i + 1 <= duAtual ? c : null));
  }
  function acumular(serie) {
    let s = 0;
    return serie.map(v => (v === null ? null : (s += v)));
  }
  function relogio(ba, recorte, mes, metaTotal) {
    const [duTotal, duAtual] = duMes(ba, mes);
    const ap = recorte.filter(r => r.MES_APREENSAO === mes);
    const dias = []; for (let d = 1; d <= duTotal; d++) dias.push(d);
    const por = {};
    for (const fa of FASES) if (ap.some(r => r.FASE === fa)) por[fa] = serieDia(ba, ap.filter(r => r.FASE === fa), duTotal, duAtual);
    const outras = ap.filter(r => !FASES.includes(r.FASE));
    if (outras.length) por[OUTRAS] = serieDia(ba, outras, duTotal, duAtual);
    const tot = serieDia(ba, ap, duTotal, duAtual), acum = acumular(tot);
    const curvas = {};
    if (metaTotal) for (const [nome, f] of FATORES) curvas[nome] = curva(metaTotal, f, duTotal, acum);
    return { mes, du_total: duTotal, du_atual: duAtual, dias, real_por_dia: por, total_dia: tot, real_acum: acum, curvas };
  }
  function advsMeta(ba, ap, mes) {
    const ma = metasDoMes(ba.metas.advogado, mes);
    const vistos = [], ks = new Set();
    for (const [m, ch] of ba.metas.advogado) {
      const k = chaveTxt(ch);
      if (m === mes && !ks.has(k)) { ks.add(k); vistos.push([k, ma.get(k)]); }
    }
    const resto = uniq(ap.map(r => adv(r.ADVOGADO))).filter(a => !ks.has(a)).sort(cmpTxt);
    return vistos.concat(resto.map(a => [a, [null, null]]));
  }
  function metaAnalista(ba, recorte, mes) {
    const [duTotal, duAtual] = duMes(ba, mes);
    const ap = recorte.filter(r => r.MES_APREENSAO === mes);
    const advs = advsMeta(ba, ap, mes), linhas = [];
    for (const [a, [mq, mv]] of advs) {
      const [q, v] = realizado(ap.filter(r => adv(r.ADVOGADO).toUpperCase() === a));
      linhas.push(Object.assign({ chave: a, tipo: "advogado" }, linhaMeta(mq, mv, q, v, duTotal, duAtual)));
    }
    if (linhas.length) {
      const mqs = advs.map(x => x[1][0]).filter(x => x !== null), mvs = advs.map(x => x[1][1]).filter(x => x !== null);
      const nomes = new Set(advs.map(x => x[0]));
      const [q, v] = realizado(ap.filter(r => nomes.has(adv(r.ADVOGADO).toUpperCase())));
      linhas.push(Object.assign({ chave: "TOTAL", tipo: "total" }, linhaMeta(mqs.length ? mqs.reduce((a, b) => a + b, 0) : null,
        mvs.length ? arred(mvs.reduce((a, b) => a + b, 0), 2) : null, q, v, duTotal, duAtual)));
    }
    return { mes, du_total: duTotal, du_atual: duAtual, linhas };
  }
  function relogioAnalista(ba, recorte, mes) {
    const [duTotal, duAtual] = duMes(ba, mes);
    const ap = recorte.filter(r => r.MES_APREENSAO === mes);
    return advsMeta(ba, ap, mes).map(([a, [mq]]) => {
      const dia = serieDia(ba, ap.filter(r => adv(r.ADVOGADO).toUpperCase() === a), duTotal, duAtual), acum = acumular(dia);
      return { advogado: a, meta_qtd: mq, real_dia: dia, real_acum: acum, curva: mq ? curva(mq, 1.0, duTotal, acum) : null };
    });
  }

  /* ---------- COMP. ANALISTA e localizadores ---------- */
  function compAnalista(ba, recorte) {
    const duHoje = duIndice(ba.hoje, feriadosDe(ba));
    const ap = recorte.filter(r => r.DT_APREENSAO);
    const meses = uniq(ap.map(r => r.MES_APREENSAO)).sort((a, b) => mesKey(a) - mesKey(b));
    const ok = ap.filter(r => r.DIA_UTIL <= duHoje);
    const valores = rs => Object.fromEntries(meses.map(m => [m, rs.filter(r => r.MES_APREENSAO === m).length]));
    const advs = uniq(ap.map(r => adv(r.ADVOGADO))).sort(cmpTxt);
    const porAdv = advs.map(a => ({ advogado: a, tipo: "", valores: valores(ok.filter(r => adv(r.ADVOGADO) === a)) }));
    const porQuebra = [];
    for (const a of advs) {
      const rs = ok.filter(r => adv(r.ADVOGADO) === a);
      for (const q of QUEBRAS) porQuebra.push({ advogado: a, quebra: q, tipo: "", valores: valores(rs.filter(r => r.DIA_UTIL_QUEBRA === q)) });
      porQuebra.push({ advogado: a, quebra: null, tipo: "sub", valores: valores(rs) });
    }
    if (advs.length) {
      porAdv.push({ advogado: null, tipo: "total", valores: valores(ok) });
      porQuebra.push({ advogado: null, quebra: null, tipo: "total", valores: valores(ok) });
    }
    return { meses, por_adv: porAdv, por_quebra: porQuebra };
  }
  function mediana(xs) {
    const v = xs.filter(x => x !== null && x !== undefined).sort((a, b) => a - b);
    if (!v.length) return null;
    const m = v.length >> 1;
    return arred(v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2, 1);
  }
  function comparativo(pas) {
    const ag = (rs, nome, tipo) => {
      const loc = rs.filter(p => p.RESULTADO === "localizou").length, enc = rs.filter(p => p.RESULTADO === "encerrada").length;
      const base = rs.length - enc, ufs = new Map();
      for (const p of rs) if (p.UF) ufs.set(p.UF, (ufs.get(p.UF) || 0) + 1);
      return {
        localizador: nome, tipo, pastas: new Set(rs.map(p => p.PASTA)).size, passagens: rs.length, localizou: loc,
        substituido: rs.filter(p => p.RESULTADO === "substituido").length,
        sem_localizacao: rs.filter(p => p.RESULTADO === "sem_localizacao").length, encerradas: enc,
        pct_localizou: base > 0 ? arred(loc / base, 4) : null, apreendeu: rs.filter(p => p.APREENDEU).length,
        valor_performance: soma(rs.filter(p => p.APREENDEU).map(p => p.VALOR_PERFORMANCE)),
        mediana_dias_localizar: mediana(rs.filter(p => p.RESULTADO === "localizou").map(p => p.DIAS_ATE_LOCALIZAR)),
        mediana_dias_com_ficha: mediana(rs.map(p => p.DIAS)),
        ufs: [...ufs.entries()].sort((a, b) => b[1] - a[1] || cmpTxt(a[0], b[0])).slice(0, 3).map(x => x[0]).join(", "),
      };
    };
    const grupos = new Map();
    for (const p of pas) { if (!grupos.has(p.LOCALIZADOR)) grupos.set(p.LOCALIZADOR, []); grupos.get(p.LOCALIZADOR).push(p); }
    const out = [...grupos.entries()].map(([n, rs]) => ag(rs, n, ""))
      .sort((a, b) => b.localizou - a.localizou || b.passagens - a.passagens || cmpTxt(a.localizador, b.localizador));
    if (out.length) out.push(ag(pas, null, "total"));
    return out;
  }
  function porLocalizador(recorte, mes) {
    const ap = recorte.filter(r => r.DT_APREENSAO && (!mes || r.MES_APREENSAO === mes));
    const grupos = new Map();
    for (const r of ap) {
      const l = r.LOCALIZADOR || SEM_LOC, u = r.UF || "SEM UF";
      if (!grupos.has(l)) grupos.set(l, new Map());
      const m = grupos.get(l); if (!m.has(u)) m.set(u, []); m.get(u).push(r);
    }
    const out = [];
    const locs = [...grupos.keys()].sort((a, b) => cmpTupla([a === SEM_LOC, a], [b === SEM_LOC, b]));
    for (const l of locs) {
      const ufs = grupos.get(l);
      for (const u of [...ufs.keys()].sort((a, b) => ufs.get(b).length - ufs.get(a).length || cmpTxt(a, b)))
        out.push({ localizador: l, uf: u, tipo: "", qtd: ufs.get(u).length, valor_performance: soma(ufs.get(u).map(r => r.VALOR_PERFORMANCE)) });
      const todos = [...ufs.values()].flat();
      out.push({ localizador: l, uf: null, tipo: "sub", qtd: todos.length, valor_performance: soma(todos.map(r => r.VALOR_PERFORMANCE)) });
    }
    if (ap.length) out.push({ localizador: null, uf: null, tipo: "total", qtd: ap.length, valor_performance: soma(ap.map(r => r.VALOR_PERFORMANCE)) });
    return out;
  }

  /* ---------- tudo ---------- */
  function secoes(ba, agora, filtros) {
    const est = estado(ba, agora), rc = recortes(est, filtros), f = rc.filtros;
    const mesMetas = f.mes || `${Number(ba.hoje.slice(5, 7))}/${ba.hoje.slice(0, 4)}`;
    const recorte = rc.recorte;
    const apreendidos = rc.lista.filter(r => r.DT_APREENSAO && (!f.mes || r.MES_APREENSAO === f.mes));
    const visAp = recorte.filter(r => r.DT_APREENSAO && (!f.mes || r.MES_APREENSAO === f.mes));
    const mf = metaFaixas(ba, mesMetas);
    const qs = mf ? FAIXAS.map(([n]) => mf.get(n)[0]).filter(x => x !== null) : [];
    const metaTotal = qs.length ? qs.reduce((a, b) => a + b, 0) : null;
    const [duTotal, duAtual] = duMes(ba, mesMetas);
    const va = pivoAdvFase(visAp);
    const [mm, aa] = mesMetas.split("/");
    return {
      localizados: rc.lista_abertos, visao_localizados: pivoAdvFase(rc.lista_abertos), mandados: mandados(rc.lista_abertos),
      apreendidos, visao_apreendidos: { adv_fase: va.adv_fase, por_fase: va.por_fase },
      comp_analista: compAnalista(ba, recorte), meta_banco: metaBanco(ba, recorte, mesMetas),
      meta_relogio: relogio(ba, recorte, mesMetas, metaTotal), meta_analista: metaAnalista(ba, recorte, mesMetas),
      meta_relogio_analista: relogioAnalista(ba, recorte, mesMetas), comparativo: comparativo(rc.passagens),
      por_localizador: porLocalizador(recorte, f.mes),
      nota_mes: `Mês ${String(mm).padStart(2, "0")}/${aa} · dia útil ${duAtual} de ${duTotal}`,
    };
  }

  function linhaTempo(ba, agora, filtros, janela) {
    const est = estado(ba, agora);
    const rc = recortes(est, Object.assign({}, filtros, { mes: null, etapa: [] }));
    const etapas = (filtros && filtros.etapa && filtros.etapa.length) ? filtros.etapa : ABERTAS;
    const hoje = ba.hoje;
    const sel = rc.recorte.filter(r => etapas.includes(r.ETAPA));
    const marcos = new Map(sel.map(r => [r.PASTA, ba.marcos[r.PASTA] || []]));
    let de;
    if (janela === "tudo") {
      const datas = [...marcos.values()].flat().map(m => m[2]);
      de = datas.length ? datas.reduce((a, b) => (b < a ? b : a)) : hoje;
    } else de = isoDia(new Date(dataUTC(hoje).getTime() - Number(janela) * DIA));
    const pastas = [];
    for (const r of sel) {
      const ms = marcos.get(r.PASTA), aberta = ABERTAS.includes(r.ETAPA);
      const dentro = ms.filter(m => m[2] >= de);
      if (!dentro.length && !aberta) continue;
      const antes = ms.filter(m => m[2] < de);
      const lista = (antes.length ? [antes[antes.length - 1]] : []).concat(dentro);
      let dias = null;
      if (aberta && ms.length) {
        const ult = ms.map(m => m[2]).reduce((a, b) => (b > a ? b : a));
        dias = Math.max(0, Math.round((dataUTC(hoje) - dataUTC(ult)) / DIA));
      }
      const dl = r.DT_LOCALIZACAO;
      pastas.push({ pasta: r.PASTA, financiado: r.FINANCIADO, advogado: r.ADVOGADO, uf: r.UF, fase: r.FASE,
        localizador: r.LOCALIZADOR, mes_localizacao: dl ? `${Number(dl.slice(5, 7))}/${dl.slice(0, 4)}` : null,
        etapa: r.ETAPA, em_aberto: aberta, dias_parado: dias, marcos: lista });
    }
    return { de, ate: hoje, pastas };
  }

  const BA = { ETAPAS, ABERTAS, FASES, SEM_LOC, estado, recortes, secoes, linhaTempo, linhaMeta, curva, arred, arredCima,
    duIndice: (ba, iso) => duIndice(iso, feriadosDe(ba)), diasUteis: (ba, mes) => diasUteis(mes, feriadosDe(ba)) };
  g.BA = BA;
  if (typeof module !== "undefined" && module.exports) module.exports = BA;
})(typeof window !== "undefined" ? window : globalThis);
