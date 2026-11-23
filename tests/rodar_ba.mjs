// Uso: node tests/rodar_ba.mjs <ba.json> <casos.json>  → imprime, por caso, BA.secoes ou BA.linhaTempo
// caso = ["secoes", agora, filtros] | ["linha_tempo", agora, filtros, janela]
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const BA = require("../src/ba.js");
const ba = JSON.parse(readFileSync(process.argv[2], "utf8"));
const casos = JSON.parse(readFileSync(process.argv[3], "utf8"));
process.stdout.write(JSON.stringify(casos.map(([tipo, agora, f, janela]) =>
  tipo === "secoes" ? BA.secoes(ba, agora, f) : BA.linhaTempo(ba, agora, f, janela))));
