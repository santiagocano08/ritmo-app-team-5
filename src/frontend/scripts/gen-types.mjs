import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const contractsDir = resolve(repoRoot, "contracts/read");
const outDir = resolve(here, "../src/api/generated");

const targets = [
  { schema: "corridor_now.schema.json", name: "CorridorNow", out: "corridor-now.ts" },
  { schema: "source_status.schema.json", name: "SourceStatus", out: "source-status.ts" },
];

const BANNER = `// AUTO-GENERATED from contracts/read/*.schema.json v1.0.0 — do not hand-edit.\n// Regenerate with: npm run gen:types\n`;

async function main() {
  await mkdir(outDir, { recursive: true });
  const indexExports = [];

  for (const target of targets) {
    const raw = await readFile(resolve(contractsDir, target.schema), "utf8");
    const schema = JSON.parse(raw);
    const ts = await compile(schema, target.name, {
      bannerComment: "",
      additionalProperties: false,
      style: { singleQuote: false },
    });
    await writeFile(resolve(outDir, target.out), BANNER + "\n" + ts, "utf8");
    indexExports.push(`export * from "./${target.out.replace(/\.ts$/, "")}";`);
  }

  await writeFile(resolve(outDir, "index.ts"), BANNER + "\n" + indexExports.join("\n") + "\n", "utf8");
  console.log(`Generated ${targets.length} contract type files into ${outDir}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
