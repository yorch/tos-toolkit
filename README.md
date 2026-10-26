# tos-toolkit

Static analysis, scaffolding, and adversarial review for **ThinkScript**
(thinkorswim) code.

ThinkScript has no compiler you can run in CI, no package manager, and no module
system. This toolkit gives you the parts that *can* be automated, and is explicit
about the part that cannot:

```console
$ tos lint                  # structural checks — no thinkorswim needed
$ tos syntax-check          # real grammar check — needs a local thinkorswim
$ tos review --mode diff    # adversarial AI review of your changes
$ tos mcp                   # serve the toolkit to a coding assistant (MCP, stdio)
```

Everything except `syntax-check` runs on a bare Python install with no
thinkorswim anywhere in sight.

**Reference:** [Commands](docs/commands.md) · [Configuration](docs/configuration.md) ·
[Rules](docs/rules.md) · [Installing and publishing](docs/publishing.md) ·
[Adopting it](docs/consuming.md) · [Agents and CI](docs/agents.md) ·
[Architecture](docs/architecture.md)

---

## Install

```console
$ pipx install tos-toolkit        # isolated CLI install (recommended)
$ uv tool install tos-toolkit     # or with uv
$ pip install tos-toolkit         # into the current environment
```

[On PyPI](https://pypi.org/project/tos-toolkit/). Requires Python 3.11+; the core
has **zero** Python dependencies.

The optional grammar check needs a local thinkorswim install and a JDK. The
`[parser]` extra adds no dependencies — it exists so the requirement is visible:

```console
$ pipx install "tos-toolkit[parser]"
```

Pin it in CI — `tos-toolkit==0.2.2` — because a new lint rule can turn a previously
green build red.

`tos syntax-check` additionally requires a locally installed thinkorswim and a
JDK. Nothing from thinkorswim is bundled or redistributed — see
[ADR 0004](docs/adr/0004-no-jar-redistribution.md).

---

## Quickstart

```console
$ mkdir my-tos-scripts && cd my-tos-scripts
$ tos init
$ tos new study trend/ema_cloud_flip
$ tos lint
$ tos status
```

`tos init` writes `tos.toml`, the artifact directories (`studies/`, `scans/`,
`strategies/`, `columns/`), copy-ready templates, a `justfile`, and appends a
conventions section to `AGENTS.md`.

---

## Commands

| Command | Needs ToS? | Purpose |
| --- | --- | --- |
| `tos lint [paths]` | no | Structure: headers, delimiters, identifier collisions, artifact rules, unknown functions |
| `tos status` | no | Validation debt — which scripts are still `draft` |
| `tos new <kind> <path>` | no | Scaffold a file from the bundled templates |
| `tos init` | no | Scaffold a project |
| `tos docs [topic]` | no | The bundled ThinkScript knowledge base |
| `tos explain <name>` | no | Is this function real? What's its confidence? |
| `tos review` | * | Adversarial review of a diff, files, or the whole repo |
| `tos syntax-check` | **yes** | Grammar validation using the real parser |

`tos review` needs the `codex` CLI on PATH (pinned model `gpt-6.1-sol`).
`harness = "claude"` is available as a substitute when Codex is unavailable.

### `tos lint`

```console
$ tos lint --strict          # warnings become failures
$ tos lint --json            # machine-readable
$ tos lint studies/          # one subtree
$ tos --profile loose lint   # language rules only, ignore our conventions
```

Exit codes: `0` clean, `1` findings at error level, `2` usage or config problem.

### `tos explain`

The registry exists because inventing a ThinkScript function is the single most
common mistake — and the platform will reject the whole study for it.

```console
$ tos explain TrueRange
TrueRange  [volatility]  confidence=verified
  TrueRange(high, close, low) - three required arguments

$ tos explain HasOption
HasOption  [option]  confidence=unverified
  internal API only; prefer IsOptionable
  WARNING: unverified. Paste-test before relying on it.
```

### `tos docs`

```console
$ tos docs --list
$ tos docs gotchas
$ tos docs --grep "crosses above"
```

The knowledge base ships inside the package, so it is available from any project
without locating this repo.

---

## Two layers, and why

The rules are deliberately split. Mixing them is what makes a linter unusable
outside its author's repo.

**Layer 1 — language-generic (always on).** True of ThinkScript anywhere:
unbalanced delimiters, `//` is not a comment, tabs, case-insensitive identifier
collisions, `rec` self-reference depth, unknown function names, and the
platform's own artifact restrictions (a scan genuinely cannot call `AddLabel`).

**Layer 2 — house conventions (profile-gated).** The `# @key:` header block, the
`@status: draft → validated` lifecycle, `studies/<category>/` layout. Opinionated
on purpose, and fully removable.

Pick a profile in `tos.toml`:

| Profile | Header block | Layout rules | Use when |
| --- | --- | --- | --- |
| `strict` (default) | required | enforced | you want the full workflow |
| `loose` | off | off | pointing at a corpus you didn't write |

Any individual rule can be overridden:

```toml
[checks]
unknown_functions = "warn"   # off | warn | error
W090 = "off"                 # silence one code
```

---

## Configuration

```toml
[profile]
name = "strict"

[project]
targets = ["studies", "scans", "strategies", "columns", "templates"]
templates_dir = "templates"

[header]
mode = "required"            # required | optional | off

[parser]
enabled = true
tos_path = "/Applications/thinkorswim"

[review]
harness = "codex"            # codex | claude
model = "gpt-6.1-sol"
effort = "high"

[checks]
unknown_functions = "warn"
```

Resolution order: built-in profile, then your `tos.toml` on top.

---

## What this cannot do

Being explicit is the point:

- **It cannot tell you a script works.** Only pasting it into thinkorswim and
  watching it render does that.
- **`syntax-check` only checks grammar.** It will happily accept
  `FooBarNotAFunction(close)`. Function names, arity, types, and semantics are not
  validated by it — that is what `lint`'s registry and `review` are for.
- **It cannot see the future.** A study that looks into the future with a
  negative offset still parses.
- **The registry is curated, not exhaustive.** An unknown name is a prompt to
  verify, not a verdict.

The intended loop is:

```text
tos lint  →  tos syntax-check  →  tos review  →  paste into ToS  →  @status: validated
```

Only the last step earns the right to call a script validated, and only a human
can do it.

---

## Documentation

- [`docs/consuming.md`](docs/consuming.md) — adopting this from a new or existing project
- [`docs/architecture.md`](docs/architecture.md) — module layout and the layering rule
- [`docs/adr/`](docs/adr/) — decisions that are expensive to reverse
- [`src/tos_toolkit/docs/knowledge-base/`](src/tos_toolkit/docs/knowledge-base/) — the ThinkScript reference (`tos docs`)
- [`AGENTS.md`](AGENTS.md) — guidance for AI agents working on this repo

## License

MIT. This project bundles no thinkorswim code.
