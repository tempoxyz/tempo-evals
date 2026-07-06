#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const lockPath = path.join(root, "config", "tempo-docs.lock.json");
const cacheRoot = path.join(root, ".cache", "tempo-docs");
const args = new Set(process.argv.slice(2));

function readLock() {
  const lock = JSON.parse(fs.readFileSync(lockPath, "utf8"));
  if (lock.schemaVersion !== 1) throw new Error(`Unsupported docs lock schema: ${lock.schemaVersion}`);
  if (!lock.repo || !lock.sha) throw new Error("Docs lock must include repo and sha");
  return lock;
}

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: options.cwd ?? root,
    env: process.env,
    stdio: options.stdio ?? "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${commandArgs.join(" ")} failed with status ${result.status}`);
  }
  return result;
}

function docsDir(lock) {
  return path.join(cacheRoot, lock.sha);
}

function repoDir(lock) {
  return path.join(docsDir(lock), "repo");
}

function publicDir(lock) {
  return path.join(docsDir(lock), "public");
}

function publicManifestPath(lock) {
  return path.join(publicDir(lock), "manifest.json");
}

function manifestPath(lock) {
  return path.join(docsDir(lock), "manifest.json");
}

function isPrepared(lock) {
  try {
    const manifest = JSON.parse(fs.readFileSync(manifestPath(lock), "utf8"));
    return (
      manifest.repo === lock.repo &&
      manifest.sha === lock.sha &&
      manifest.docCount > 0 &&
      fs.existsSync(path.join(publicDir(lock), "developers", "llms.txt")) &&
      fs.existsSync(path.join(publicDir(lock), "developers", "llms-full.txt")) &&
      fs.existsSync(path.join(publicDir(lock), "developers", "index.html"))
    );
  } catch {
    return false;
  }
}

function ensureRepo(lock) {
  const target = repoDir(lock);
  if (!fs.existsSync(path.join(target, ".git"))) {
    fs.rmSync(target, { recursive: true, force: true });
    fs.mkdirSync(path.dirname(target), { recursive: true });
    run("git", ["clone", "--filter=blob:none", "--no-checkout", lock.repo, target]);
  }
  run("git", ["fetch", "--depth=1", "origin", lock.sha], { cwd: target });
  run("git", ["checkout", "--force", lock.sha], { cwd: target });
  run("git", ["clean", "-fdx"], { cwd: target });
}

function walk(directory) {
  const entries = fs.readdirSync(directory, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(entryPath);
    if (entry.isFile() && /\.(md|mdx)$/.test(entry.name)) return [entryPath];
    return [];
  });
}

function routeFor(relativePath) {
  const withoutExtension = relativePath.replace(/\.(md|mdx)$/, "");
  const normalized = withoutExtension.split(path.sep).join("/");
  if (normalized === "index") return "/docs";
  if (normalized.endsWith("/index")) return `/docs/${normalized.slice(0, -"/index".length)}`;
  return `/docs/${normalized}`;
}

function linkRouteFor(relativePath) {
  const withoutExtension = relativePath.replace(/\.(md|mdx)$/, "");
  const normalized = withoutExtension.split(path.sep).join("/");
  if (normalized === "index") return "/docs/";
  if (normalized !== "index" && normalized.endsWith("/index")) {
    return `/docs/${normalized.slice(0, -"/index".length)}/`;
  }
  return routeFor(relativePath);
}

function parseFrontmatter(content) {
  const frontmatter = content.match(/^---\n([\s\S]*?)\n---/);
  if (!frontmatter) return {};
  const data = {};
  for (const line of frontmatter[1].split(/\r?\n/)) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*?)\s*$/);
    if (!match) continue;
    const value = match[2].replace(/^["']|["']$/g, "").trim();
    data[match[1]] = value;
  }
  return data;
}

function titleFrom(content, relativePath) {
  const { title } = parseFrontmatter(content);
  if (title) return title.trim();
  const heading = content.match(/^#\s+(.+)$/m)?.[1];
  if (heading) return heading.trim();
  return path
    .basename(relativePath, path.extname(relativePath))
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function descriptionFrom(content) {
  return parseFrontmatter(content).description?.trim() ?? "";
}

function cleanMarkdown(content, doc) {
  const withoutFrontmatter = content.replace(/^---\n[\s\S]*?\n---\n*/, "");
  const lines = withoutFrontmatter.split(/\r?\n/);
  const cleanedLines = [];
  let seenBody = false;

  for (const line of lines) {
    if (!seenBody && (line.trim() === "" || line.startsWith("import "))) continue;
    seenBody = true;
    cleanedLines.push(line);
  }

  let markdown = cleanedLines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  if (!markdown.startsWith("# ")) {
    markdown = [`# ${doc.title}`, "", doc.description, "", markdown].filter(Boolean).join("\n");
  }
  return `${llmsFeedbackNotice}${markdown}\n`;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function writeFile(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
}

function pageHtml(doc, body) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(doc.title)} - Tempo Docs</title>
</head>
<body>
<nav><a href="/developers">Tempo Docs</a> <a href="/developers/llms.txt">llms.txt</a> <a href="/developers/llms-full.txt">llms-full.txt</a></nav>
<main>
<h1>${escapeHtml(doc.title)}</h1>
<p><code>${escapeHtml(doc.route)}</code></p>
<pre>${escapeHtml(body)}</pre>
</main>
</body>
</html>
`;
}

const llmsFeedbackNotice = [
  '> Feedback: If these docs are stale, missing, or confusing, post sanitized feedback to `https://tempo.xyz/developers/api/feedback` with `source: "mcp"`, a short `message`, and any relevant `toolName`, `relatedResource`, or `client`.',
  "",
].join("\n");

function sidebarOrder(repoRoot) {
  const configPath = path.join(repoRoot, "vocs.config.ts");
  if (!fs.existsSync(configPath)) return new Map();

  const config = fs.readFileSync(configPath, "utf8");
  const orderedLinks = [...new Set([
    ...linksInConfigBlock(config, "const docsHomeSidebar = [", "const buildSidebar"),
    ...linksInConfigBlock(config, "const docsSidebar = [", "const section"),
  ])].filter((link) => link !== "/docs");
  return new Map(orderedLinks.map((link, index) => [link, index]));
}

function linksInConfigBlock(config, startMarker, endMarker) {
  const start = config.indexOf(startMarker);
  if (start === -1) return [];
  const end = config.indexOf(endMarker, start + startMarker.length);
  const block = config.slice(start, end === -1 ? undefined : end);
  const links = [...block.matchAll(/link:\s*["'](\/docs[^"']*)["']/g)].map((match) => match[1]);
  return [...new Set(links)];
}

function docSort(order) {
  return (a, b) => {
    const aOrder = order.get(a.route) ?? Number.MAX_SAFE_INTEGER;
    const bOrder = order.get(b.route) ?? Number.MAX_SAFE_INTEGER;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return a.route.localeCompare(b.route);
  };
}

function writeManifest(lock, docs, sourceDigest, outputRoot) {
  const manifest = `${JSON.stringify(
    {
      schemaVersion: 1,
      repo: lock.repo,
      sha: lock.sha,
      docCount: docs.length,
      sourceDigest,
      publicDir: outputRoot,
      agentBasePath: "/developers",
      routes: {
        index: "/developers",
        llms: "/developers/llms.txt",
        llmsFull: "/developers/llms-full.txt",
      },
    },
    null,
    2,
  )}\n`;

  writeFile(manifestPath(lock), manifest);
  writeFile(publicManifestPath(lock), manifest);
}

function buildBundle(lock) {
  const sourceRoot = path.join(repoDir(lock), "src", "pages", "docs");
  const outputRoot = publicDir(lock);
  if (!fs.existsSync(sourceRoot)) throw new Error(`Docs source directory not found: ${sourceRoot}`);

  fs.rmSync(outputRoot, { recursive: true, force: true });
  fs.mkdirSync(outputRoot, { recursive: true });

  const docs = walk(sourceRoot)
    .map((filePath) => {
      const relativePath = path.relative(sourceRoot, filePath);
      const content = fs.readFileSync(filePath, "utf8");
      const route = routeFor(relativePath);
      const title = titleFrom(content, relativePath);
      return {
        content,
        description: descriptionFrom(content),
        linkRoute: linkRouteFor(relativePath),
        markdownRoute: `/developers${route}.md`,
        relativePath,
        route,
        title,
      };
    })
    .sort(docSort(sidebarOrder(repoDir(lock))));

  const llmsLines = [
    llmsFeedbackNotice.trimEnd(),
    "",
    "# Tempo",
    "",
    "Documentation for the Tempo network and protocol specifications",
    "",
  ];
  const fullLines = [
    llmsFeedbackNotice.trimEnd(),
    "",
    "# Tempo",
    "",
    "Documentation for the Tempo network and protocol specifications",
    "",
  ];

  for (const doc of docs) {
    const markdown = cleanMarkdown(doc.content, doc);
    const markdownPath = path.join(outputRoot, doc.markdownRoute.slice(1));
    const pagePath = path.join(outputRoot, doc.route.slice(1), "index.html");
    writeFile(markdownPath, markdown);
    writeFile(pagePath, pageHtml(doc, markdown));
    llmsLines.push(
      `- [${doc.title}](${doc.linkRoute})${doc.description ? `: ${doc.description}` : ""}`,
    );
    fullLines.push(markdown.trimEnd(), "");
  }

  const index = {
    title: "Tempo",
    route: "/developers",
  };
  writeFile(
    path.join(outputRoot, "developers", "index.html"),
    pageHtml(
      index,
      [
        "# Tempo",
        "",
        "Documentation for the Tempo network and protocol specifications",
        "",
        "- [llms.txt](/developers/llms.txt)",
        "- [llms-full.txt](/developers/llms-full.txt)",
        "",
        ...docs.map(
          (doc) =>
            `- [${doc.title}](${doc.markdownRoute})${doc.description ? `: ${doc.description}` : ""}`,
        ),
      ].join("\n"),
    ),
  );
  writeFile(path.join(outputRoot, "developers", "llms.txt"), `${llmsLines.join("\n")}\n`);
  writeFile(path.join(outputRoot, "developers", "llms-full.txt"), `${fullLines.join("\n")}\n`);

  const hash = crypto.createHash("sha256");
  for (const doc of docs) hash.update(doc.relativePath).update("\0").update(doc.content).update("\0");
  writeManifest(lock, docs, `sha256:${hash.digest("hex")}`, outputRoot);
}

const lock = readLock();
if (args.has("--check")) {
  if (!isPrepared(lock)) {
    throw new Error(`Pinned docs bundle is missing. Run: npm run docs:prepare`);
  }
  console.log(`Pinned Tempo docs bundle is ready at ${publicDir(lock)}`);
  process.exit(0);
}

if (!isPrepared(lock) || args.has("--force")) {
  ensureRepo(lock);
  buildBundle(lock);
}

console.log(`Pinned Tempo docs bundle is ready at ${publicDir(lock)}`);
