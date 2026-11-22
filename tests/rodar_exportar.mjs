// Uso: node tests/rodar_exportar.mjs <chamada.json>  com {"fn": "csv", "args": [...]}  → imprime o retorno em JSON
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Exportar = require("../src/exportar.js");
const { fn, args } = JSON.parse(readFileSync(process.argv[2], "utf8"));
process.stdout.write(JSON.stringify(Exportar[fn](...args)));
