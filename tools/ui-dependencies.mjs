// Lists what the web apps still need from the backend, straight from the code.
//
// Every read goes through fromFixture({ endpoint, note }, ...) or, once the backend has the
// endpoint, fromCore({ endpoint, note }, ...) (Tenant Web App) or fromPlatform({ endpoint, note }, ...)
// (Platform Console) in src/data; every action that would change data and is not
// connected is an <ActionButton endpoint="..."> (Docs/UI_Implementation.md, rule 4). This script
// collects all three and prints the Markdown tables used in that document:
//
//   node tools/ui-dependencies.mjs            print the tables
//   node tools/ui-dependencies.mjs --write    replace the generated section of the document
//   node tools/ui-dependencies.mjs --check    fail if the document is out of date
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const apps = [
  { name: "Tenant Web App", dir: "apps/tenant-web/src", backend: "IMS Core" },
  { name: "Platform Console", dir: "apps/platform-console/src", backend: "the Platform Service" },
];
const DOC = join(root, "Docs", "UI_Implementation.md");
const BEGIN = "<!-- generated: ui-dependencies begin -->";
const END = "<!-- generated: ui-dependencies end -->";

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.tsx?$/.test(entry) ? [path] : [];
  });
}

/** Joins "a" + "b" string concatenations and unescapes the simple escapes used in notes. */
function literal(source) {
  const parts = [...source.matchAll(/"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`|'((?:[^'\\]|\\.)*)'/g)];
  return parts
    .map((part) => part[1] ?? part[2] ?? part[3] ?? "")
    .join("")
    .replace(/\\(["'`\\])/g, "$1")
    .replace(/\$\{[^}]*\}/g, "{…}");
}

function routeOf(appDir, file) {
  const path = relative(join(root, appDir, "app"), file).replaceAll("\\", "/");
  const segments = path.split("/").slice(0, -1).filter((segment) => !/^\(.*\)$/.test(segment));
  return `/${segments.join("/")}`;
}

function collect(app) {
  const reads = [];
  const connected = [];
  const actions = new Map();
  for (const file of walk(join(root, app.dir))) {
    const source = readFileSync(file, "utf8");
    const where = relative(join(root, app.dir), file).replaceAll("\\", "/");

    if (where.startsWith("data/")) {
      const pattern = /fromFixture\(\s*\{\s*endpoint:\s*([\s\S]*?)(?:,\s*note:\s*([\s\S]*?))?,?\s*\}\s*,/g;
      for (const match of source.matchAll(pattern)) {
        reads.push({ endpoint: literal(match[1]), note: match[2] ? literal(match[2]) : "", file: where });
      }
      const live = /from(?:Core|Platform)(?:<[^(]*>)?\(\s*\{\s*endpoint:\s*([\s\S]*?)(?:,\s*note:\s*([\s\S]*?))?,?\s*\}\s*,/g;
      for (const match of source.matchAll(live)) {
        connected.push({ endpoint: literal(match[1]), note: match[2] ? literal(match[2]) : "", file: where });
      }
    }
    for (const match of source.matchAll(/\bendpoint=(?:"([^"]+)"|\{`([^`]+)`\}|\{"([^"]+)"\})/g)) {
      const endpoint = (match[1] ?? match[2] ?? match[3]).replace(/\$\{[^}]*\}/g, "{…}");
      const screen = where.startsWith("app/") ? routeOf(app.dir, file) : where;
      if (!actions.has(endpoint)) actions.set(endpoint, new Set());
      actions.get(endpoint).add(screen);
    }
  }
  const byEndpoint = (a, b) => a.endpoint.localeCompare(b.endpoint) || a.file.localeCompare(b.file);
  reads.sort(byEndpoint);
  connected.sort(byEndpoint);
  return { reads, connected, actions: [...actions].sort(([a], [b]) => a.localeCompare(b)) };
}

const cell = (text) => text.replaceAll("|", "\\|").replaceAll("\n", " ");

function render() {
  const lines = [];
  for (const app of apps) {
    const { reads, connected, actions } = collect(app);
    lines.push(`### ${app.name}`, "");
    if (connected.length) {
      lines.push(`Reads connected to ${app.backend} (${connected.length}):`, "");
      lines.push("| Endpoint | Data function file | Notes |", "|---|---|---|");
      for (const read of connected) lines.push(`| \`${cell(read.endpoint)}\` | \`${read.file}\` | ${cell(read.note)} |`);
      lines.push("");
    }
    lines.push(`Reads served from sample data (${reads.length}):`, "");
    lines.push("| Endpoint | Data function file | What the screen needs beyond the LLD's description |", "|---|---|---|");
    for (const read of reads) lines.push(`| \`${cell(read.endpoint)}\` | \`${read.file}\` | ${cell(read.note)} |`);
    lines.push("", `Actions that are not connected (${actions.length}):`, "");
    lines.push("| Endpoint | Screens |", "|---|---|");
    for (const [endpoint, screens] of actions) {
      lines.push(`| \`${cell(endpoint)}\` | ${[...screens].sort().map((s) => `\`${s}\``).join(", ")} |`);
    }
    lines.push("");
  }
  return lines.join("\n").trimEnd();
}

const generated = `${BEGIN}\n${render()}\n${END}`;
const mode = process.argv[2];
if (!mode) {
  console.log(render());
} else {
  const doc = readFileSync(DOC, "utf8");
  const start = doc.indexOf(BEGIN);
  const end = doc.indexOf(END);
  if (start === -1 || end === -1) throw new Error(`${DOC} has no generated section markers`);
  const updated = doc.slice(0, start) + generated + doc.slice(end + END.length);
  if (mode === "--write") {
    writeFileSync(DOC, updated);
    console.log("Docs/UI_Implementation.md updated");
  } else if (mode === "--check") {
    if (updated !== doc) {
      console.error("Docs/UI_Implementation.md is out of date: run node tools/ui-dependencies.mjs --write");
      process.exit(1);
    }
    console.log("Docs/UI_Implementation.md is up to date");
  } else {
    throw new Error(`unknown option ${mode}`);
  }
}
