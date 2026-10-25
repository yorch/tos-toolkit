#!/usr/bin/env python3
"""Fail if the built site would break once deployed.

A link checker that resolves URLs on the build machine proves a *file exists*,
not that a *server will serve it*. So this checks the properties the deployment
actually depends on:

* every internal target resolves **inside** ``site/`` (a link like ``../../LICENSE``
  exists locally and 404s on Pages);
* no path escapes the project-page base (``/tos-toolkit/…`` is valid there,
  ``/rules/`` is not — it would resolve to the domain root);
* case matches exactly, because CI runs on Linux even if your laptop does not;
* every ``#fragment`` exists in the target page, and no page defines an ``id``
  twice (the first one silently wins, so anchors land somewhere unintended);
* ``search.json`` URLs point at files that exist;
* CSS ``url()`` references resolve;
* exactly one ``<h1>`` per page;
* no third-party ``src``/stylesheet/``@import`` — the site must work offline.

Run after ``scripts/build_site.py``.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")
CSS_IMPORT = re.compile(r"""@import\s+['"]([^'"]+)['"]""")


def site_base() -> str:
    """The project-page prefix, derived from the same site_url the builder uses."""
    text = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
    match = re.search(r'SITE_URL\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("could not read SITE_URL from scripts/build_site.py")
    path = urlsplit(match.group(1)).path
    return path if path.endswith("/") else path + "/"


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.refs: list[tuple[str, str, str]] = []
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        for attr in ("href", "src"):
            if a.get(attr) is not None:
                self.refs.append((f"{tag}[{attr}]", a[attr], a.get("rel") or ""))


def parse(path: Path) -> Collector:
    collector = Collector()
    collector.feed(path.read_text(encoding="utf-8"))
    return collector


def resolve(page: Path, url: str, base: str) -> tuple[Path | None, str | None]:
    """Map a URL to a file under site/. Returns (target, error)."""
    path = unquote(urlsplit(url).path)

    if path.startswith(base):
        target = SITE / path[len(base) :]
    elif path.startswith("/"):
        return None, f"root-absolute path escapes the project base ({base})"
    elif path == "":
        target = page
    else:
        target = page.parent / path

    if path.endswith("/") or target.is_dir():
        target = target / "index.html"

    resolved = target.resolve()
    if not resolved.is_relative_to(SITE.resolve()):
        return None, "resolves outside site/"
    return resolved, None


def check_case(page: Path, url: str) -> str | None:
    """CI is case-sensitive; macOS is not. Walk the path and compare exactly."""
    if urlsplit(url).path.startswith(("/",)):
        return None
    current = page.parent
    for part in unquote(urlsplit(url).path).split("/"):
        if part in ("", ".", ".."):
            continue
        if not (current / part).exists() and (current / part.lower()).exists():
            return f"case mismatch: {url!r}"
        current = current / part
    return None


def main() -> int:
    if not SITE.is_dir():
        print("error: no site/ — run scripts/build_site.py first", file=sys.stderr)
        return 2

    base = site_base()
    pages = sorted(SITE.rglob("*.html"))
    if not pages:
        print("error: no HTML in site/", file=sys.stderr)
        return 2

    parsed: dict[Path, Collector] = {}
    errors: list[str] = []

    for page in pages:
        info = parse(page)
        parsed[page.resolve()] = info
        rel = page.relative_to(SITE)

        if info.h1 != 1:
            errors.append(f"{rel}: expected exactly one <h1>, found {info.h1}")

        duplicates = [i for i, n in Counter(info.ids).items() if n > 1]
        if duplicates:
            errors.append(f"{rel}: duplicate id(s) {sorted(duplicates)}")

        for where, url, link_rel in info.refs:
            parts = urlsplit(url)
            if parts.scheme in ("http", "https") or url.startswith("//"):
                if where != "a[href]" and link_rel != "canonical":
                    errors.append(f"{rel}: third-party resource {where}={url}")
                continue
            if parts.scheme in ("mailto", "data", "javascript"):
                continue

            target, problem = resolve(page, url, base)
            if problem:
                errors.append(f"{rel}: {where} {url!r} {problem}")
                continue
            case_problem = check_case(page, url)
            if case_problem:
                errors.append(f"{rel}: {case_problem}")
            if target is None or not target.exists():
                errors.append(f"{rel}: broken {where} {url!r}")
                continue
            if parts.fragment and target.suffix == ".html":
                ids = parsed.get(target) or parse(target)
                if unquote(parts.fragment) not in ids.ids:
                    errors.append(f"{rel}: missing anchor {url!r}")

    # Stylesheet references and search-index targets are fetched, not linked.
    for css in sorted(SITE.rglob("*.css")):
        text = css.read_text(encoding="utf-8")
        rel_css = css.relative_to(SITE)
        for url in CSS_URL.findall(text) + CSS_IMPORT.findall(text):
            if url.startswith(("data:", "http://", "https://", "//")):
                if not url.startswith("data:"):
                    errors.append(f"{rel_css}: third-party CSS resource {url!r}")
                continue
            if not (css.parent / url).resolve().exists():
                errors.append(f"{rel_css}: missing CSS resource {url!r}")

    index_file = SITE / "search.json"
    if index_file.exists():
        for entry in json.loads(index_file.read_text(encoding="utf-8")):
            url = entry.get("u") or ""
            if not url:
                errors.append("search.json: entry without a url")
                continue
            target, problem = resolve(index_file, url, base)
            if problem:
                errors.append(f"search.json: {url!r} {problem}")
            elif target is None or not target.exists():
                errors.append(f"search.json: stale target {url!r}")

    for error in errors:
        print(error)
    print(f"checked {len(pages)} page(s): {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
