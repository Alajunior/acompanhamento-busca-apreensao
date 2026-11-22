// Uso: node tests/rodar_agregar.mjs <payload.json> <casos.json>  → imprime [Agregar.tudo(...) para cada caso]
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Agregar = require("../src/agregar.js");
const payload = JSON.parse(readFileSync(process.argv[2], "utf8"));
const casos = JSON.parse(readFileSync(process.argv[3], "utf8"));
process.stdout.write(JSON.stringify(casos.map(([agora, filtros]) => Agregar.tudo(payload, agora, filtros))));
