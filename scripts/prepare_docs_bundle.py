#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "config" / "tempo-docs.lock.json"
CACHE_ROOT = ROOT / ".cache" / "tempo-docs"

LLMS_FEEDBACK_NOTICE = (
    "> Feedback: If these docs are stale, missing, or confusing, post sanitized "
    "feedback to `https://tempo.xyz/developers/api/feedback` with `source: "
    '"mcp"`, a short `message`, and any relevant `toolName`, `relatedResource`, '
    "or `client`.\n"
)

BUNDLE_SCHEMA_VERSION = 3
SKILL_ROUTE = "/developers/SKILL.md"

# Rewrite only documentation routes under the canonical docs mount. Root-host
# APIs such as the faucet, and the website skill at https://tempo.xyz/SKILL.md,
# must continue to resolve to Tempo rather than the pinned docs sidecar.
_ROUTE_END = r"""(?=[/?#.,"'`<\s)\]}]|$)"""
_MOUNT_END = r"""(?=/?(?:[?#.,"'`<\s)\]}]|$))"""
CANONICAL_DOCS_URL_PATTERN = re.compile(
    r"https://tempo\.xyz/developers(?:/(?:"
    r"docs|get-started|index\.md|llms(?:-full)?\.txt|SKILL\.md|skill\.md"
    rf"){_ROUTE_END}|{_MOUNT_END})"
)


def read_lock() -> dict[str, Any]:
    lock = json.loads(LOCK_PATH.read_text())
    if lock.get("schemaVersion") != 1:
        msg = f"Unsupported docs lock schema: {lock.get('schemaVersion')}"
        raise RuntimeError(msg)
    if not isinstance(lock.get("repo"), str) or not lock["repo"]:
        msg = "Docs lock must include repo"
        raise RuntimeError(msg)
    if lock.get("sha") is not None and not isinstance(lock["sha"], str):
        msg = "Docs lock sha must be a string or null"
        raise RuntimeError(msg)
    return lock


def run(
    command: str,
    args: list[str],
    *,
    cwd: Path = ROOT,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [command, *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        msg = f"{command} {' '.join(args)} failed with status {result.returncode}"
        raise RuntimeError(msg)
    return result


def docs_dir(lock: dict[str, Any]) -> Path:
    return CACHE_ROOT / str(lock["sha"])


def repo_dir(lock: dict[str, Any]) -> Path:
    return docs_dir(lock) / "repo"


def public_dir(lock: dict[str, Any]) -> Path:
    return docs_dir(lock) / "public"


def manifest_path(lock: dict[str, Any]) -> Path:
    return docs_dir(lock) / "manifest.json"


def public_manifest_path(lock: dict[str, Any]) -> Path:
    return public_dir(lock) / "manifest.json"


def is_prepared(lock: dict[str, Any]) -> bool:
    try:
        manifest = json.loads(manifest_path(lock).read_text())
        return (
            manifest.get("schemaVersion") == BUNDLE_SCHEMA_VERSION
            and manifest.get("repo") == lock["repo"]
            and manifest.get("sha") == lock["sha"]
            and manifest.get("docCount", 0) > 0
            and (public_dir(lock) / "developers" / "llms.txt").exists()
            and (public_dir(lock) / "developers" / "llms-full.txt").exists()
            and (public_dir(lock) / "developers" / "index.html").exists()
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def ensure_repo(lock: dict[str, Any]) -> None:
    target = repo_dir(lock)
    if not (target / ".git").exists():
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        run(
            "git",
            ["clone", "--filter=blob:none", "--no-checkout", lock["repo"], str(target)],
        )
    run("git", ["fetch", "--depth=1", "origin", lock["sha"]], cwd=target)
    run("git", ["checkout", "--force", lock["sha"]], cwd=target)
    run("git", ["clean", "-fdx"], cwd=target)


def walk(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix in {".md", ".mdx"}
    )


def route_for(relative_path: Path) -> str:
    """Return the site route for a page path relative to `src/pages`."""
    parts = relative_path.with_suffix("").parts
    if parts[-1] == "index":
        parts = parts[:-1]
    return "/" + "/".join(parts)


def link_route_for(relative_path: Path) -> str:
    route = route_for(relative_path)
    if relative_path.stem == "index" and route != "/":
        return f"{route}/"
    return route


def markdown_route_for(route: str) -> str:
    return f"/developers{'/index' if route == '/' else route}.md"


def parse_frontmatter(content: str) -> dict[str, str]:
    match = re.match(r"^---\n([\s\S]*?)\n---", content)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in re.split(r"\r?\n", match.group(1)):
        value_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if not value_match:
            continue
        value = re.sub(r"^[\"']|[\"']$", "", value_match.group(2)).strip()
        data[value_match.group(1)] = value
    return data


def title_from(content: str, relative_path: Path) -> str:
    title = parse_frontmatter(content).get("title")
    if title:
        return title.strip()
    heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    return re.sub(
        r"\b\w",
        lambda match: match.group(0).upper(),
        relative_path.stem.replace("-", " ").replace("_", " "),
    )


def description_from(content: str) -> str:
    return parse_frontmatter(content).get("description", "").strip()


def rewrite_canonical_docs_urls(content: str) -> str:
    return CANONICAL_DOCS_URL_PATTERN.sub(
        lambda match: match.group().replace(
            "https://tempo.xyz", "https://docs.tempo.xyz"
        ),
        content,
    )


def clean_markdown(content: str, doc: dict[str, str]) -> str:
    without_frontmatter = re.sub(r"^---\n[\s\S]*?\n---\n*", "", content)
    cleaned_lines: list[str] = []
    seen_body = False
    for line in re.split(r"\r?\n", without_frontmatter):
        if not seen_body and (line.strip() == "" or line.startswith("import ")):
            continue
        seen_body = True
        cleaned_lines.append(line)

    markdown = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip()
    markdown = rewrite_canonical_docs_urls(markdown)
    if not markdown.startswith("# "):
        parts = [f"# {doc['title']}", "", doc.get("description", ""), "", markdown]
        markdown = "\n".join(part for part in parts if part)
    return f"{LLMS_FEEDBACK_NOTICE}{markdown}\n"


def write_file(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def page_html(doc: dict[str, str], body: str) -> str:
    title = html.escape(doc["title"], quote=True)
    route = html.escape(doc["route"], quote=True)
    escaped_body = html.escape(body, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - Tempo Docs</title>
</head>
<body>
<nav>
<a href="/developers">Tempo Docs</a>
<a href="/developers/llms.txt">llms.txt</a>
<a href="/developers/llms-full.txt">llms-full.txt</a>
</nav>
<main>
<h1>{title}</h1>
<p><code>{route}</code></p>
<pre>{escaped_body}</pre>
</main>
</body>
</html>
"""


def links_in_config_block(config: str, start_marker: str, end_marker: str) -> list[str]:
    start = config.find(start_marker)
    if start == -1:
        return []
    end = config.find(end_marker, start + len(start_marker))
    block = config[start:] if end == -1 else config[start:end]
    links = re.findall(r"link:\s*[\"'](/(?:docs|get-started)[^\"']*)[\"']", block)
    return list(dict.fromkeys(links))


def sidebar_order(repo_root: Path) -> dict[str, int]:
    config_path = repo_root / "vocs.config.ts"
    if not config_path.exists():
        return {}
    config = config_path.read_text()
    links = [
        *links_in_config_block(
            config, "const docsHomeSidebar = [", "const buildSidebar"
        ),
        *links_in_config_block(config, "const docsSidebar = [", "const section"),
    ]
    if not links:
        # Product navigation defines every section sidebar inside one factory.
        links = links_in_config_block(config, "sidebar: (() => {", "topNav:")
    ordered_links = [link for link in dict.fromkeys(links) if link != "/docs"]
    return {link: index for index, link in enumerate(ordered_links)}


def doc_sort_key(order: dict[str, int], doc: dict[str, str]) -> tuple[int, str]:
    return (order.get(doc["route"], 2**53 - 1), doc["route"])


def write_manifest(
    lock: dict[str, Any],
    docs: list[dict[str, str]],
    source_digest: str,
    output_root: Path,
    *,
    has_skill: bool,
) -> None:
    routes = {
        "index": "/developers",
        "llms": "/developers/llms.txt",
        "llmsFull": "/developers/llms-full.txt",
    }
    if has_skill:
        routes["skill"] = SKILL_ROUTE
    manifest = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "repo": lock["repo"],
        "sha": lock["sha"],
        "docCount": len(docs),
        "sourceDigest": source_digest,
        "publicDir": str(output_root),
        "agentBasePath": "/developers",
        "routes": routes,
    }
    content = f"{json.dumps(manifest, indent=2)}\n"
    write_file(manifest_path(lock), content)
    write_file(public_manifest_path(lock), content)


def build_bundle(lock: dict[str, Any]) -> None:
    """Export every Vocs page under `src/pages` and the docs skill.

    Production serves the repository root `SKILL.md` at `/developers/SKILL.md`.
    """
    pages_root = repo_dir(lock) / "src" / "pages"
    output_root = public_dir(lock)
    if not (pages_root / "docs").exists():
        msg = f"Docs source directory not found: {pages_root / 'docs'}"
        raise RuntimeError(msg)

    shutil.rmtree(output_root, ignore_errors=True)
    output_root.mkdir(parents=True, exist_ok=True)

    docs = []
    for file_path in walk(pages_root):
        relative_path = file_path.relative_to(pages_root)
        content = file_path.read_text()
        route = route_for(relative_path)
        docs.append(
            {
                "content": content,
                "description": description_from(content),
                "linkRoute": link_route_for(relative_path),
                "markdownRoute": markdown_route_for(route),
                "relativePath": relative_path.as_posix(),
                "route": route,
                "title": title_from(content, relative_path),
            },
        )
    docs.sort(key=lambda doc: doc_sort_key(sidebar_order(repo_dir(lock)), doc))
    routes = {doc["route"] for doc in docs}

    skill_path = repo_dir(lock) / "SKILL.md"
    skill = skill_path.read_text() if skill_path.exists() else None
    if skill is not None:
        write_file(
            output_root / SKILL_ROUTE.removeprefix("/"),
            rewrite_canonical_docs_urls(skill),
        )

    llms_lines = [
        LLMS_FEEDBACK_NOTICE.rstrip(),
        "",
        "# Tempo",
        "",
        "Documentation for the Tempo network and protocol specifications",
        "",
    ]
    if skill is not None:
        llms_lines.extend(
            [
                f"[Docs skill]({SKILL_ROUTE}) · "
                "[Full documentation](/developers/llms-full.txt)",
                "",
            ]
        )
    full_lines = llms_lines.copy()

    for doc in docs:
        markdown = clean_markdown(doc["content"], doc)
        markdown_routes = [doc["markdownRoute"]]
        if doc["route"] == "/" and "/docs" not in routes:
            # Production redirects /docs.md to the site home when no docs
            # landing page exists.
            markdown_routes.append(markdown_route_for("/docs"))
        for markdown_route in markdown_routes:
            write_file(output_root / markdown_route.removeprefix("/"), markdown)
        page_path = output_root / doc["route"].removeprefix("/") / "index.html"
        write_file(page_path, page_html(doc, markdown))
        description = f": {doc['description']}" if doc["description"] else ""
        llms_lines.append(f"- [{doc['title']}]({doc['linkRoute']}){description}")
        full_lines.extend([markdown.rstrip(), ""])

    index = {"title": "Tempo", "route": "/developers"}
    index_body = "\n".join(
        [
            "# Tempo",
            "",
            "Documentation for the Tempo network and protocol specifications",
            "",
            *([f"- [SKILL.md]({SKILL_ROUTE})"] if skill is not None else []),
            "- [llms.txt](/developers/llms.txt)",
            "- [llms-full.txt](/developers/llms-full.txt)",
            "",
            *[
                f"- [{doc['title']}]({doc['markdownRoute']})"
                f"{f': {doc["description"]}' if doc['description'] else ''}"
                for doc in docs
            ],
        ],
    )
    write_file(output_root / "developers" / "index.html", page_html(index, index_body))
    write_file(output_root / "developers" / "llms.txt", f"{'\n'.join(llms_lines)}\n")
    write_file(
        output_root / "developers" / "llms-full.txt", f"{'\n'.join(full_lines)}\n"
    )

    sources = [(doc["relativePath"], doc["content"]) for doc in docs]
    if skill is not None:
        sources.append(("SKILL.md", skill))
    digest = hashlib.sha256()
    for relative_path, content in sources:
        digest.update(relative_path.encode())
        digest.update(b"\0")
        digest.update(content.encode())
        digest.update(b"\0")
    write_manifest(
        lock,
        docs,
        f"sha256:{digest.hexdigest()}",
        output_root,
        has_skill=skill is not None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--sha", help="Docs repository commit SHA to prepare")
    args = parser.parse_args()

    configured_lock = read_lock()
    if not args.sha and not configured_lock.get("sha"):
        print("No docs SHA selected; public docs mode does not need a local bundle.")
        return
    lock = {**configured_lock, "sha": args.sha or configured_lock["sha"]}
    if args.check:
        if not is_prepared(lock):
            msg = "Pinned docs bundle is missing. Run: npm run docs:prepare"
            raise RuntimeError(msg)
        print(f"Pinned Tempo docs bundle is ready at {public_dir(lock)}")
        return

    if not is_prepared(lock) or args.force:
        ensure_repo(lock)
        build_bundle(lock)

    print(f"Pinned Tempo docs bundle is ready at {public_dir(lock)}")


if __name__ == "__main__":
    main()
