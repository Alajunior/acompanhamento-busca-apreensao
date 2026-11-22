// Exportação (sem DOM): CSV por card e as abas do .xlsx, a partir do resultado de Agregar.tudo.
(function (g) {
  "use strict";
  const ETAPAS = ["EMENDAR INICIAL", "AGUARDANDO LIMINAR", "LIMINAR DEFERIDA", "MANDADO REQUERIDO", "MANDADO EXPEDIDO", "MANDADO NEGATIVO"];
  const DINAMICAS = ["TIPO_AGENDAMENTO", "DATA_AGENDAMENTO", "FASE", "DATA_INSERT"];

  function celula(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "number") return String(v).replace(".", ",");
    const s = String(v);
    return /[;"\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  // separador ";", vírgula decimal, BOM UTF-8, CRLF (abre direto no Excel em português)
  const csv = (cab, linhas) => "﻿" + [cab, ...linhas].map((l) => l.map(celula).join(";")).join("\r\n") + "\r\n";
  const pct = (n, tot) => (tot ? (n / tot) * 100 : null);
  const r2 = (v) => (v === null || v === undefined ? null : Math.round(v * 100) / 100);
  const simnao = (b) => (b ? "sim" : "nao");
  const addDias = (iso, n) => new Date(Date.parse(iso + "T00:00:00Z") + n * 86400000).toISOString().slice(0, 10);

  function tabela(rotulo, linhas) {
    const tot = linhas.reduce((s, x) => s + x[1], 0);
    return { cab: [rotulo, "Quantidade", "%"], linhas: linhas.map(([k, n]) => [k, n, pct(n, tot)]), tot };
  }

  function linhasRegioes(G) {
    const cols = [...G.ufs, G.brasil];
    const L = (rot, f) => [rot, ...cols.map(f)];
    const out = [L("Processos", (u) => u.kpis.processos), L("Participação nos processos (%)", (u) => r2(u.part_processos ?? null)),
      L("Risco total (R$)", (u) => r2(u.kpis.risco)), L("Participação no risco (%)", (u) => r2(u.part_risco ?? null)),
      L("Risco médio por processo (R$)", (u) => r2(u.risco_medio)),
      L("Vencidos (data de agendamento já passou)", (u) => u.kpis.vencidos), L("Vencidos (%)", (u) => r2(u.pct.vencidos)),
      L("Vencem hoje", (u) => u.kpis.hoje), L("Vencem hoje (%)", (u) => r2(u.pct.hoje)),
      L("Próximos 7 dias", (u) => u.kpis.prox7), L("Próximos 7 dias (%)", (u) => r2(u.pct.prox7)),
      L("Em diligência", (u) => u.kpis.diligencia), L("Em diligência (%)", (u) => r2(u.pct.diligencia)),
      L("Mandado negativo (%)", (u) => r2(u.pct_negativo))];
    ETAPAS.forEach((e, i) => { out.push(L(`Etapa: ${e} (qtd)`, (u) => u.etapas[i][1]));
      out.push(L(`Etapa: ${e} (%)`, (u) => r2(pct(u.etapas[i][1], u.kpis.processos)))); });
    if (G.brasil.localizados) out.push(L("Veículos localizados 30 dias", (u) => u.localizados.d30),
      L("% da carteira localizada (30 dias)", (u) => r2(u.localizados.pct)));
    const lead = (lista) => { const x = lista.find(([k]) => !k.startsWith("(") && k !== "sem ano"); return x ? x[0] : null; };
    out.push(L("Advogados", (u) => u.advogados.qtd), L("Advogado com mais processos", (u) => (u.advogados.mais ? `${u.advogados.mais[0]} | ${u.advogados.mais[1]}` : null)),
      L("Produto mais frequente", (u) => lead(u.perfil.produto)), L("Faixa de idade mais frequente", (u) => lead(u.perfil.idade)),
      L("Marca líder", (u) => lead(u.perfil.marcas)), L("Comarca com mais processos", (u) => (u.comarcas[0] ? u.comarcas[0][0] : null)));
    return { cab: ["Indicador", ...G.ufs.map((u) => u.uf), "Brasil"], linhas: out };
  }

  const CARDS = {
    produtivos: (R) => { const t = tabela("Agendamento", R.tabelas.produtivos); return [t.cab, t.linhas]; },
    follow: (R) => { const t = tabela("Fase", R.tabelas.follow); return [t.cab, t.linhas]; },
    diligencia: (R) => { const t = tabela("Diligência", R.tabelas.diligencia); return [t.cab, t.linhas]; },
    localizacao: (R) => [["Etapa", "24 horas", "7 dias", "30 dias", "Sugestão"], R.localizado
      ? [...R.localizado.por_etapa, ["Total (todas as etapas)", ...R.localizado.total_etapas, ""]] : []],
    escada: (R) => [["Tentativa", "REQUERIDO", "EXPEDIDO", "NEGATIVO", "Total", "Chegou %"],
      R.escada ? R.escada.linhas.map((l) => [l.tentativa, l.REQUERIDO, l.EXPEDIDO, l.NEGATIVO, l.total, r2(l.chegou)]) : []],
    prazos: (R) => [["Etapa", "vencidos", "hoje", "7 dias", "depois", "sem data"], R.prazos],
    advogados: (R) => [["Advogado", "Processos", "Vencidos", "Hoje", "Risco", ...ETAPAS, "% vencidos", "Processos / mediana", "Carga alta", "Vencidos alto"],
      R.advogados.linhas.map((x) => [x.adv, x.processos, x.vencidos, x.hoje, r2(x.risco), ...x.etapas, r2(x.pct_venc), r2(x.razao), simnao(x.carga_alta), simnao(x.venc_alto)])],
    uf: (R) => [["UF", "Processos", "Risco", "Mandado negativo"], Object.entries(R.mapa_uf).map(([uf, v]) => [uf, v[0], r2(v[1]), v[2]])],
    regioes: (R) => { if (!R.regioes) return [["Indicador"], []]; const t = linhasRegioes(R.regioes); return [t.cab, t.linhas]; },
    movimentacao: (R) => [["De", "Para", "Processos"], R.movimentacao.transicoes ? R.movimentacao.transicoes.slice(0, 12) : []],
    risco_etapa: (R) => [["Etapa", "Processos", "Risco", "Valor do bem"], R.risco_etapa.linhas.map((x) => [x[0], x[1], r2(x[2]), r2(x[3])])],
    risco_uf: (R) => [["UF", "Processos", "Risco", "Valor do bem"], R.risco_uf.linhas.map((x) => [x[0], x[1], r2(x[2]), r2(x[3])])],
    carteira_etapa: (R) => { const c = R.carteira_etapa;
      return [["Carteira", ...c.etapas.map((e) => `${e} (qtd)`), ...c.etapas.map((e) => `${e} (R$)`)], c.carteiras.map((k, i) => [k, ...c.qtd[i], ...c.risco[i].map(r2)])]; },
    comarcas: (R) => [["Comarca", "UF", "Processos", "% negativo"], R.comarcas.map((x) => [x[0], x[1], x[2], r2(x[3])])],
    perfil: (R) => { const p = R.perfil, L = [];
      for (const [grupo, lista] of [["Produto", p.produto], ["Marca", p.marcas], ["Idade", p.idade]]) for (const [k, n] of lista) L.push([grupo, k, n, r2(pct(n, p.base))]);
      return [["Grupo", "Item", "Processos", "% do total"], L]; },
    evolucao: (R) => { const e = R.evolucao;
      return [["Dia", "Lacuna (sim/nao)", "Total", ...ETAPAS], e.dias.map((d, i) => [d, simnao(e.lacuna[i]), e.total[i], ...ETAPAS.map((x) => e.por_etapa[x][i])])]; },
  };

  function csvDoCard(chave, R, hoje) {
    const [cab, linhas] = CARDS[chave](R);
    return { nome: `${chave === "uf" ? "uf_sem_filtro_uf" : chave}_${hoje}.csv`, texto: csv(cab, linhas) };
  }

  function planilhas(R, rows, bd, filtros, pub, foto, hoje) {
    const out = {};
    // BD: as 62 colunas da regra; as estáveis vêm de bd.json, as da publicação vêm da foto
    if (!bd) out.BD = [["Base analítica indisponível: abra o painel por um servidor (o arquivo bd.json é carregado à parte)."]];
    else {
      const pos = new Map(bd.pastas.map((p, j) => [p, j])), idx = new Map(bd.colunas.map((c, j) => [c, j]));
      const insert = `${foto.dia}T${pub.quando}:00`;
      out.BD = [bd.todas, ...rows.filter((r) => pos.has(r.i)).map((r) => {
        const v = bd.valores[pos.get(r.i)];
        const din = { TIPO_AGENDAMENTO: r.tipo, DATA_AGENDAMENTO: r.data === null ? null : addDias(hoje, r.data), FASE: r.fase, DATA_INSERT: insert };
        return bd.todas.map((c) => (DINAMICAS.includes(c) ? din[c] : v[idx.get(c)]));
      })];
    }
    const k = R.kpis.atual, resumo = [["Indicador", "Valor"], ["Processos", k.processos], ["Em diligencia (1o mandado expedido)", k.diligencia],
      ["Vencidos", k.vencidos], ["Vencem hoje", k.hoje], ["Proximos 7 dias", k.prox7], ["Risco total (R$)", r2(k.risco)]];
    for (const [rot, lista] of [["Agendamento", R.tabelas.produtivos], ["Fase", R.tabelas.follow], ["Diligencia", R.tabelas.diligencia]]) {
      const t = tabela(rot, lista);
      resumo.push([], t.cab, ...t.linhas.map((l) => [l[0], l[1], r2(l[2])]), ["Total Geral", t.tot, t.tot ? 100 : null]);
    }
    out.Resumo = resumo;
    out.Prazos = [["etapa", "vencidos", "hoje", "7 dias", "depois", "sem data"], ...R.prazos];
    out.Advogados = [["Advogado", "Processos", "Vencidos", "Hoje", "Risco (R$)", ...ETAPAS], ...R.advogados.linhas.map((x) => [x.adv, x.processos, x.vencidos, x.hoje, r2(x.risco), ...x.etapas])];
    const m = R.movimentacao, trans = m.transicoes || [], movs = m.movimentos || [];
    const nMov = Math.max(trans.length, movs.length);
    out.Movimentacao = [["de", "para", "qtd", "", "movimento", "pasta"]];
    for (let j = 0; j < nMov; j++) out.Movimentacao.push([...(trans[j] || ["", "", ""]), "", ...(movs[j] || ["", ""])]);
    const lista = (gr) => (filtros[gr] && filtros[gr].length ? filtros[gr].join(", ") : "(todos)");
    out.Filtros = [["Campo", "Valor"], ["Dados de", `${foto.dia.slice(8, 10)}/${foto.dia.slice(5, 7)}/${foto.dia.slice(0, 4)} ${pub.quando}`],
      ["Origem", pub.origem === "oficial" ? "tabela oficial" : "ao vivo"], ["UF", lista("uf")], ["Carteira", lista("carteira")], ["Advogado", lista("adv")],
      ["Etapa", lista("etapa")], ["Produto", lista("produto")], ["Agendamento de", filtros.de || "(sem limite)"], ["Agendamento ate", filtros.ate || "(sem limite)"]];
    if (R.regioes) { const t = linhasRegioes(R.regioes); out.Regioes = [t.cab, ...t.linhas]; }
    return out;
  }

  const E = { csv, csvDoCard, planilhas };
  g.Exportar = E;
  if (typeof module !== "undefined" && module.exports) module.exports = E;
})(typeof window !== "undefined" ? window : globalThis);
