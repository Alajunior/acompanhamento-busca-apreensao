// Uso: node tests/rodar_agregar.mjs <payload.json> <casos.json> [lista]  → imprime [Agregar.tudo(...) para cada caso]
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Agregar = require("../src/agregar.js");
const payload = JSON.parse(readFileSync(process.argv[2], "utf8"));
const casos = JSON.parse(readFileSync(process.argv[3], "utf8"));
const modo = process.argv[4] || "tudo";   // "lista": casos = [agora, filtros, estados, busca]
process.stdout.write(JSON.stringify(modo === "lista"
  ? casos.map(([agora, filtros, estados, busca]) => Agregar.listaPadroes(payload, agora, filtros, estados, busca))
  : casos.map(([agora, filtros]) => Agregar.tudo(payload, agora, filtros))));
