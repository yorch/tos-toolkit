#!/usr/bin/env python3
"""Build the documentation site from `docs/**/*.md` into `site/`.

A deliberately small static site generator: no theme engine, no plugins. It
renders Markdown with `markdown`, highlights code with `pygments` (including a
ThinkScript lexer defined below), wraps every page in
`site-src/templates/page.html`, and writes a JSON search index.

Build-time only. The `tos-toolkit` package itself keeps zero runtime
dependencies; nothing here is imported by it.

The build is strict: an internal `.md` link that does not resolve, or a
Markdown file that is missing from `NAV`, fails the build.

Usage:
    python scripts/sync_kb_docs.py   # stage the packaged knowledge base
    python scripts/build_site.py
"""

from __future__ import annotations

import html
import json
import posixpath
import re
import shutil
import string
import sys
import tomllib
import xml.etree.ElementTree as etree
from dataclasses import dataclass, field
from pathlib import Path

import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import RegexLexer, bygroups
from pygments.lexers import get_lexer_by_name
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Whitespace,
)
from pygments.util import ClassNotFound

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SRC = ROOT / "site-src"
OUT = ROOT / "site"

SITE_NAME = "tos-toolkit"
SITE_URL = "https://yorch.github.io/tos-toolkit/"
REPO_URL = "https://github.com/yorch/tos-toolkit"
DESCRIPTION = "Static analysis, scaffolding, and adversarial review for ThinkScript"

# Declared page order. Every docs/**/*.md must appear here exactly once.
NAV: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Guide",
        [
            ("index.md", "Overview"),
            ("commands.md", "Commands"),
            ("configuration.md", "Configuration"),
            ("rules.md", "Rules"),
            ("consuming.md", "Adopting it"),
            ("publishing.md", "Installing and publishing"),
            ("agents.md", "Agents and CI"),
            ("architecture.md", "Architecture"),
        ],
    ),
    (
        "ThinkScript reference",
        [
            ("knowledge-base/README.md", "Overview"),
            ("knowledge-base/language-reference.md", "Language"),
            ("knowledge-base/functions.md", "Functions"),
            ("knowledge-base/constants.md", "Constants"),
            ("knowledge-base/gotchas.md", "Gotchas"),
            ("knowledge-base/asset-classes.md", "Asset classes"),
            ("knowledge-base/artifact-rules.md", "Artifact rules"),
            ("knowledge-base/unverified-tokens.md", "Unverified tokens"),
        ],
    ),
    (
        "Decisions",
        [
            ("adr/README.md", "Overview"),
            ("adr/0001-pip-package-with-cli.md", "0001 pip package"),
            ("adr/0002-layered-core-and-profiles.md", "0002 Layered rules"),
            ("adr/0003-grammar-check-is-optional.md", "0003 Optional grammar check"),
            ("adr/0004-no-jar-redistribution.md", "0004 No jar redistribution"),
        ],
    ),
]

RULE_CODE = re.compile(r"^[EW]\d{3}$")


# --------------------------------------------------------------------------- #
# ThinkScript lexer
# --------------------------------------------------------------------------- #


class ThinkScriptLexer(RegexLexer):
    """Minimal ThinkScript lexer: enough to colour the docs, not a parser.

    ThinkScript is case-insensitive, so keywords match in any case. Enum
    members (`Color.RED`, `AggregationPeriod.DAY`) are matched case-sensitively
    on their conventional upper-case spelling.
    """

    name = "ThinkScript"
    aliases = ["thinkscript", "tos"]
    filenames = ["*.thinkscript"]
    flags = re.IGNORECASE | re.MULTILINE

    tokens = {
        "root": [
            (r"\s+", Whitespace),
            (r"#.*?$", Comment.Single),
            (r'"[^"\n]*"', String.Double),
            (r"(\d+\.\d*|\.\d+|\d+)", Number),
            (r"\b(def|rec|plot|input|declare|script)\b", Keyword.Declaration),
            (r"\b(if|then|else|fold|to|with|do)\b", Keyword),
            (r"\b(and|or)\b", Operator.Word),
            (r"(?-i:([A-Z][A-Za-z0-9]*)(\.)([A-Z][A-Z0-9_]*))\b",
             bygroups(Name.Class, Punctuation, Name.Constant)),
            (r"([A-Za-z_][A-Za-z0-9_]*)(\s*)(\()",
             bygroups(Name.Function, Whitespace, Punctuation)),
            (r"[A-Za-z_][A-Za-z0-9_]*", Name),
            (r"==|!=|<>|<=|>=|&&|\|\||[-+*/=<>!]", Operator),
            (r"[()\[\]{},;.:]", Punctuation),
            (r".", Text),
        ]
    }


def lexer_for(lang: str):
    if lang in ThinkScriptLexer.aliases:
        return ThinkScriptLexer()
    try:
        return get_lexer_by_name(lang or "text")
    except ClassNotFound:
        return get_lexer_by_name("text")


FORMATTER = HtmlFormatter(nowrap=True)


def highlight_block(code: str, lang: str) -> str:
    body = highlight(code, lexer_for(lang), FORMATTER).rstrip("\n")
    label = html.escape(lang or "text")
    return (
        f'<div class="code" data-lang="{label}">'
        f'<span class="code-lang" aria-hidden="true">{label}</span>'
        f'<pre tabindex="0"><code>{body}</code></pre></div>'
    )


def highlight_lines(code: str, marks: dict[int, tuple[str, str]] | None = None) -> str:
    """Highlight ThinkScript into one `<span class="ln">` per line.

    `marks` maps a 1-based line number to (identifier, css class); the first
    Name token with that exact text on the line is wrapped in a `<mark>`.
    Used by the home-page figure, where each line animates separately.
    """
    marks = marks or {}
    out = []
    for number, line in enumerate(code.split("\n"), start=1):
        body = highlight(line, ThinkScriptLexer(), FORMATTER).rstrip("\n") if line else ""
        if number in marks:
            ident, cls = marks[number]
            needle = f'<span class="n">{ident}</span>'
            if needle not in body:
                raise SystemExit(f"hero mark {ident!r} not found on line {number}")
            body = body.replace(needle, f'<mark class="{cls}">{needle}</mark>', 1)
        out.append(f'<span class="ln" style="--i:{number}">{body or " "}</span>')
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Markdown extensions
# --------------------------------------------------------------------------- #

FENCE = re.compile(r"^```[ \t]*([\w+-]*)[ \t]*\n(.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)


class FencePreprocessor(Preprocessor):
    """Replace fenced code blocks with stashed, highlighted HTML."""

    def run(self, lines: list[str]) -> list[str]:
        text = "\n".join(lines)

        def replace(match: re.Match) -> str:
            stashed = self.md.htmlStash.store(highlight_block(match.group(2), match.group(1)))
            return f"\n\n{stashed}\n\n"

        return FENCE.sub(replace, text).split("\n")


class DocTreeprocessor(Treeprocessor):
    """Rewrite `.md` links to site URLs and decorate diagnostic tables."""

    def __init__(self, md, page: "Page", pages: dict[str, "Page"]):
        super().__init__(md)
        self.page = page
        self.pages = pages

    def run(self, root: etree.Element) -> None:
        for a in root.iter("a"):
            self.rewrite_link(a)
        seen: set[str] = set()
        for index, el in enumerate(list(root)):
            if el.tag != "table":
                continue
            self.decorate_table(el, seen)
            # Wide tables scroll inside a focusable, labelled region.
            wrap = etree.Element("div", {"class": "table-wrap", "tabindex": "0",
                                         "role": "region",
                                         "aria-label": self.table_label(root, index)})
            root.remove(el)
            wrap.append(el)
            root.insert(index, wrap)

    @staticmethod
    def table_label(root: etree.Element, index: int) -> str:
        for el in reversed(list(root)[:index]):
            if el.tag in {"h2", "h3", "h4"}:
                return "".join(el.itertext()).strip() + " (table)"
        return "Table"

    def rewrite_link(self, a: etree.Element) -> None:
        href = a.get("href", "")
        if href.startswith(("http://", "https://")):
            a.set("rel", "external noopener")
            return
        if not href or href.startswith("#") or re.match(r"^[a-z]+:", href):
            return
        path, _, frag = href.partition("#")
        if not path.endswith(".md"):
            return
        target = posixpath.normpath(posixpath.join(posixpath.dirname(self.page.src), path))
        if target not in self.pages:
            raise SystemExit(f"{self.page.src}: broken link {href!r} (no page {target!r})")
        url = self.page.rel_url(self.pages[target])
        a.set("href", url + (f"#{frag}" if frag else ""))

    def decorate_table(self, table: etree.Element, seen: set[str]) -> None:
        body = table.find("tbody")
        if body is None:
            return

        # A definitions table is one whose header starts with "Code". Other tables
        # on the same page (the Range overview) merely mention codes and must not
        # create anchors, or #E031 resolves to the wrong row.
        head = table.find("thead")
        header_text = "".join(head.itertext()).strip().lower() if head is not None else ""
        is_definition_table = header_text.startswith("code")

        rule_rows = 0
        for tr in body.findall("tr"):
            cells = tr.findall("td")
            if not cells:
                continue

            # Severity comes from the data, not from the code prefix: E031 and
            # E072 are warnings, so colouring by "E" would contradict the table.
            severity = None
            for td in cells:
                value = "".join(td.itertext()).strip()
                if value in {"error", "warn"} and len(td) == 0:
                    td.set("class", f"sev sev-{value}")
                    severity = severity or value

            if not is_definition_table:
                continue

            first = cells[0]
            code_el = first.find("code")
            if not (
                code_el is not None
                and len(first) == 1
                and not (first.text or "").strip()
                and RULE_CODE.match(code_el.text or "")
            ):
                continue

            code = code_el.text
            rule_rows += 1
            tone = {"error": "e", "warn": "w"}.get(severity, code[0].lower())
            tr.set("class", f"rule rule-{tone}")
            # The overview "Range" table also mentions codes; only the row that
            # actually defines one may claim the anchor, or #E031 lands on the
            # wrong row and the chip shows the wrong text.
            if code not in seen:
                seen.add(code)
                tr.set("id", code)
                first.remove(code_el)
                link = etree.SubElement(first, "a", {"href": f"#{code}", "class": "code-tag"})
                link.append(code_el)
                detail = "".join(cells[-1].itertext()).strip()
                self.page.rules.append((code, detail))
        if rule_rows:
            table.set("class", "rules-table")


class DocExtension(Extension):
    def __init__(self, page: "Page", pages: dict[str, "Page"]):
        super().__init__()
        self.page = page
        self.pages = pages

    def extendMarkdown(self, md) -> None:
        md.preprocessors.register(FencePreprocessor(md), "tos_fence", 26)
        # After inline (20) so <a>/<code> exist; before toc (5).
        md.treeprocessors.register(DocTreeprocessor(md, self.page, self.pages), "tos_doc", 15)


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #


@dataclass
class Page:
    src: str  # posix path relative to docs/
    nav_title: str
    section: str
    title_html: str = ""
    title_text: str = ""
    body: str = ""
    toc: list[dict] = field(default_factory=list)
    rules: list[tuple[str, str]] = field(default_factory=list)

    @property
    def slug(self) -> str:
        stem = self.src[:-3]
        if stem == "index":
            return ""
        if stem.endswith("/README"):
            return stem[: -len("/README")]
        return stem

    @property
    def out_path(self) -> Path:
        return OUT / self.slug / "index.html" if self.slug else OUT / "index.html"

    @property
    def root(self) -> str:
        return "../" * len(self.slug.split("/")) if self.slug else "./"

    def rel_url(self, other: "Page") -> str:
        return self.root + (other.slug + "/" if other.slug else "")

    @property
    def source_url(self) -> str:
        if self.src.startswith("knowledge-base/"):
            return f"{REPO_URL}/blob/main/src/tos_toolkit/docs/{self.src}"
        return f"{REPO_URL}/blob/main/docs/{self.src}"


H1 = re.compile(r"^# (.+?)\s*$", re.MULTILINE)
TAG = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", text))).strip()


def render(page: Page, pages: dict[str, Page]) -> None:
    source = (DOCS / page.src).read_text(encoding="utf-8")
    # The first `# ` heading becomes the page <h1> in the template, so it is
    # lifted out of the body. Skip fenced blocks: `# comment` lines are code.
    unfenced = FENCE.sub(lambda m: " " * len(m.group(0)), source)
    match = H1.search(unfenced)
    if not match:
        raise SystemExit(f"{page.src}: no '# ' title")
    source = source[: match.start()] + source[match.end():]
    page.title_html = markdown.markdown(match.group(1))[3:-4]  # strip <p>…</p>
    page.title_text = strip_tags(page.title_html)

    md = markdown.Markdown(
        extensions=[
            "tables", "attr_list", "def_list", "footnotes", "sane_lists",
            "toc", DocExtension(page, pages),
        ],
        extension_configs={
            "toc": {"permalink": "#", "permalink_title": "Link to this section",
                    "toc_depth": "2-3"},
        },
    )
    page.body = md.convert(source)
    page.toc = md.toc_tokens  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Chrome: nav, toc, pager, hero
# --------------------------------------------------------------------------- #


def nav_html(current: Page, ordered: list[Page], rules_page: Page) -> str:
    parts = []
    for section, entries in NAV:
        items = []
        for src, _ in entries:
            p = next(x for x in ordered if x.src == src)
            here = p is current
            attrs = ' aria-current="page"' if here else ""
            item = f'<li><a href="{current.rel_url(p)}"{attrs}>{html.escape(p.nav_title)}</a>'
            if p is rules_page and rules_page.rules:
                base = "" if here else current.rel_url(p)
                chips = "".join(
                    f'<li><a href="{base}#{c}" class="chip chip-{c[0].lower()}" '
                    f'title="{html.escape(d, quote=True)}">{c}</a></li>'
                    for c, d in rules_page.rules
                )
                item += f'<ul class="chips" aria-label="Rule codes">{chips}</ul>'
            items.append(item + "</li>")
        heading_id = "nav-" + re.sub(r"[^a-z]+", "-", section.lower()).strip("-")
        parts.append(
            f'<section aria-labelledby="{heading_id}"><h2 id="{heading_id}" class="nav-h">'
            f'{html.escape(section)}</h2><ul class="nav-list">{"".join(items)}</ul></section>'
        )
    return "".join(parts)


def toc_html(page: Page) -> str:
    def walk(tokens: list[dict]) -> str:
        if not tokens:
            return ""
        lis = "".join(
            f'<li><a href="#{t["id"]}">{html.escape(strip_tags(t["name"]))}</a>'
            f'{walk(t["children"])}</li>'
            for t in tokens
        )
        return f"<ul>{lis}</ul>"

    if not page.toc:
        return ""
    return (
        '<nav class="toc" aria-labelledby="toc-h"><h2 id="toc-h" class="nav-h">'
        f"On this page</h2>{walk(page.toc)}</nav>"
    )


def pager_html(page: Page, ordered: list[Page]) -> str:
    i = ordered.index(page)
    links = []
    if i > 0:
        p = ordered[i - 1]
        links.append(f'<a class="prev" rel="prev" href="{page.rel_url(p)}">'
                     f'<span>Previous</span>{html.escape(p.nav_title)}</a>')
    if i < len(ordered) - 1:
        p = ordered[i + 1]
        links.append(f'<a class="next" rel="next" href="{page.rel_url(p)}">'
                     f'<span>Next</span>{html.escape(p.nav_title)}</a>')
    return f'<nav class="pager" aria-label="Previous and next page">{"".join(links)}</nav>'


HERO_BEFORE = """declare upper;

def pdHigh = high(period = AggregationPeriod.DAY)[1];
plot PdHigh = pdHigh;"""

HERO_AFTER = """declare upper;

def priorDayHigh = high(period = AggregationPeriod.DAY)[1];
plot PdHigh = priorDayHigh;"""


def hero_html(page: Page, pages: dict[str, Page]) -> str:
    before = highlight_lines(HERO_BEFORE, {3: ("pdHigh", "hit"), 4: ("PdHigh", "hit")})
    after = highlight_lines(HERO_AFTER, {3: ("priorDayHigh", "fix")})
    rules = page.rel_url(pages["rules.md"])
    commands = page.rel_url(pages["commands.md"])
    # Both transcripts are verbatim `tos --profile loose lint <file>` output for
    # prior_day_high.thinkscript. `loose` is required because the sample has no
    # header block; re-run this if the diagnostic wording changes.
    return f"""
<header class="hero">
  <p class="kicker"><span class="kicker-no">Fig. 1</span> A paste that fails in thinkorswim</p>
  <h1 class="hero-title"><span class="hero-product">tos-toolkit</span>
    <span class="hero-err">Identifier Already Used:&nbsp;PdHigh</span>
    <span class="hero-sub">Caught before you paste, not after.</span></h1>
  <p class="hero-lede">ThinkScript names are case-insensitive, so <code>def pdHigh</code> and
    <code>plot PdHigh</code> are one identifier. The platform tells you only after the paste.
    <strong>tos-toolkit</strong> tells you in your terminal, your pre-commit hook, and CI.</p>
  <p class="hero-cta"><a class="btn btn-primary" href="{rules}">Read the rules</a>
    <a class="btn" href="{commands}">Commands</a></p>
</header>
<div class="plates" role="group" aria-label="Before and after: the E071 identifier collision">
  <figure class="plate plate-before">
    <figcaption><span class="plate-tag">A</span> Before
      <span class="plate-file">prior_day_high.thinkscript</span></figcaption>
    <div class="code code-figure" data-lang="thinkscript"><pre tabindex="0" role="group"
      aria-label="Before: colliding identifiers"><code>{before}</code></pre><span
      class="proof" aria-hidden="true">E071</span></div>
    <pre class="term" tabindex="0" role="group" aria-label="tos lint output, exit code 1"><span class="prompt">$</span> tos --profile loose lint prior_day_high.thinkscript
<span class="t-err">prior_day_high.thinkscript:3: [E071]</span> 'pdHigh' and 'PdHigh' are the same identifier (ThinkScript is case-insensitive)
    hint: Rename one; this fails to compile as 'Identifier Already Used'.

1 file(s) checked · <span class="t-err">1 error(s)</span> · 0 warning(s)  <span class="exit exit-1">exit 1</span></pre>
  </figure>
  <figure class="plate plate-after">
    <figcaption><span class="plate-tag">B</span> After
      <span class="plate-file">rename the rec</span></figcaption>
    <div class="code code-figure" data-lang="thinkscript"><pre tabindex="0" role="group"
      aria-label="After: renamed identifier"><code>{after}</code></pre></div>
    <pre class="term" tabindex="0" role="group" aria-label="tos lint output, exit code 0"><span class="prompt">$</span> tos --profile loose lint prior_day_high.thinkscript
1 file(s) checked · <span class="t-ok">0 error(s)</span> · 0 warning(s)  <span class="exit exit-0">exit 0</span></pre>
  </figure>
</div>
"""


# --------------------------------------------------------------------------- #
# Search index
# --------------------------------------------------------------------------- #

HEADING = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.DOTALL)
PERMALINK = re.compile(r'<a class="headerlink".*?</a>', re.DOTALL)


def search_entries(page: Page) -> list[dict]:
    # The root page has no slug; on a project page its URL is still the base, not
    # the empty string, or the search index points at the domain root.
    url = page.slug + "/" if page.slug else SITE_URL
    chunks = HEADING.split(page.body)
    # Index the full section text: truncating here makes legitimate terms
    # unsearchable. The UI truncates what it displays.
    entries = [{"p": page.title_text, "h": "", "u": url, "x": strip_tags(chunks[0])}]
    for i in range(1, len(chunks), 4):
        _level, anchor, heading, text = chunks[i:i + 4]
        entries.append({"p": page.title_text, "h": strip_tags(PERMALINK.sub("", heading)),
                        "u": f"{url}#{anchor}", "x": strip_tags(text)})
    for code, detail in page.rules:
        entries.append({"p": page.title_text, "h": code, "u": f"{url}#{code}",
                        "x": detail, "c": 1})
    return entries


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #


def collect() -> list[Page]:
    if not (DOCS / "knowledge-base").is_dir():
        raise SystemExit("docs/knowledge-base/ missing: run scripts/sync_kb_docs.py first")
    ordered = [Page(src, title, section) for section, entries in NAV for src, title in entries]
    declared = {p.src for p in ordered}
    found = {p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md")}
    if missing := sorted(found - declared):
        raise SystemExit(f"Markdown not in NAV (add it to scripts/build_site.py): {missing}")
    if absent := sorted(declared - found):
        raise SystemExit(f"NAV lists files that do not exist: {absent}")
    return ordered


def version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stage_knowledge_base() -> None:
    """Copy the packaged knowledge base into docs/ before rendering.

    The builder owns this so that every caller — CI, Pages, the justfile, a human
    with a fresh clone — gets the same tree. docs/knowledge-base/ is gitignored.
    """
    import subprocess

    script = Path(__file__).resolve().parent / "sync_kb_docs.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"staging the knowledge base failed:\n{result.stderr}")


def main() -> int:
    stage_knowledge_base()
    ordered = collect()
    pages = {p.src: p for p in ordered}
    for page in ordered:
        render(page, pages)

    rules_page = pages["rules.md"]
    template = string.Template((SRC / "templates" / "page.html").read_text(encoding="utf-8"))
    common = {"description": html.escape(DESCRIPTION), "version": version(), "repo": REPO_URL}

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC / "assets", OUT / "assets")

    for page in ordered:
        if page.slug == "":
            title = f"{SITE_NAME} — {DESCRIPTION}"
            head = ""
            content = hero_html(page, pages) + f'<div class="prose">{page.body}</div>'
        else:
            title = f"{page.title_text} — {SITE_NAME}"
            head = (f'<header class="page-head"><p class="kicker">{html.escape(page.section)}'
                    f'</p><h1>{page.title_html}</h1></header>')
            content = f'<div class="prose">{page.body}</div>'
        write(page.out_path, template.substitute(
            common,
            title=html.escape(title),
            canonical=SITE_URL + (page.slug + "/" if page.slug else ""),
        canonical_link=f'<link rel="canonical" href="{SITE_URL + (page.slug + "/" if page.slug else "")}">',
            root=page.root,
            body_class="home" if page.slug == "" else "doc",
            nav=nav_html(page, ordered, rules_page),
            head=head,
            content=content,
            toc="" if page.slug == "" else toc_html(page),
            pager=pager_html(page, ordered),
            source=page.source_url,
        ))

    # 404: GitHub Pages serves it at whatever depth was requested, so every
    # link on it is absolute to the project base path rather than relative.
    base = "/" + SITE_URL.split("://", 1)[1].split("/", 1)[1]
    nav_404 = (nav_html(pages["index.md"], ordered, rules_page)
               .replace('href="./', f'href="{base}').replace(' aria-current="page"', ""))
    write(OUT / "404.html", template.substitute(
        common,
        title=f"Not found — {SITE_NAME}",
        canonical=SITE_URL,
        canonical_link='<meta name="robots" content="noindex">',
        root=base,
        body_class="doc notfound",
        nav=nav_404,
        head='<header class="page-head"><p class="kicker">Error 404</p>'
             "<h1>No such page</h1></header>",
        content=(f'<div class="prose"><p>Nothing is published at this address. Try the '
                 f'<a href="{base}">overview</a>, the <a href="{base}rules/">rule index</a>, '
                 "or press <kbd>/</kbd> to search.</p></div>"),
        toc="",
        pager="",
        source=REPO_URL,
    ))

    index = [e for p in ordered for e in search_entries(p)]
    write(OUT / "search.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    write(OUT / ".nojekyll", "")

    print(f"built {len(ordered)} page(s) + 404 into {OUT.relative_to(ROOT)}/ "
          f"({len(index)} search entries, {len(rules_page.rules)} rule codes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
