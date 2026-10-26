# Commands

```console
tos [--config PATH] [--profile NAME] <command> [options]
```

Global flags must come **before** the subcommand: `tos --profile loose lint`, not
`tos lint --profile loose`.

---

## `tos lint`

Static analysis. No thinkorswim required.

```console
$ tos lint                    # configured targets
$ tos lint studies/ --strict  # warnings become failures
$ tos lint --json             # machine-readable
$ tos lint --quiet            # suppress the summary line
$ tos lint --allow-empty      # succeed even if no files were checked
```

| Exit | Meaning |
| --- | --- |
| 0 | clean (or warnings only, without `--strict`) |
| 1 | findings at error level |
| 2 | usage or configuration problem |

A path that does not exist exits 2 rather than silently checking zero files — a
typo in a pre-commit hook must not pass.

**An empty run is also a failure.** If the run checked zero files — no configured
targets, or a directory with no `.thinkscript` files — the exit code is 2 and the
JSON says `"ok": false`. A gate that silently checks nothing is indistinguishable
from a passing one. Pass `--allow-empty` when an empty tree is genuinely expected,
such as a freshly scaffolded project before its first script.

`--json` emits:

```json
{
  "ok": false,
  "targets_found": true,
  "error_count": 1,
  "warning_count": 0,
  "files_checked": 1,
  "findings": [
    {
      "path": "studies/trend/x.thinkscript",
      "line": 14,
      "code": "E071",
      "severity": "error",
      "message": "'pdHigh' and 'PdHigh' are the same identifier (ThinkScript is case-insensitive)",
      "hint": "Rename one; this fails to compile as 'Identifier Already Used'."
    }
  ],
  "summary": "1 file(s) checked · 1 error(s) · 0 warning(s)"
}
```

`ok` is `false` when there is an error, when `--strict` promotes a warning, or when
nothing was checked. `targets_found` distinguishes "clean" from "nothing matched".

`severity` is `"error"` or `"warning"` (not `"warn"`).

---

## `tos status`

Validation debt: which scripts are still unvalidated.

```console
$ tos status
STATUS       KIND      VER      PATH
draft        study     0.1.0    studies/trend/ema_cloud_flip.thinkscript

Summary
  draft        3

Validation debt: 3 script(s) not validated (draft or missing/unknown @status).
```

Any `@status` that is missing or misspelled is counted as debt, not ignored.

Exit codes: `0` always — `status` is a report, not a gate. Use `tos lint` in CI.

---

## `tos syntax-check`

Grammar validation using the **real** thinkorswim parser from your own
installation.

```console
$ tos syntax-check
  OK (grammar only): studies/trend/ema_cloud_flip.thinkscript

7 file(s) checked, 0 with grammar errors.
NOTE: grammar only — function names, types, and semantics are not verified.
```

| Exit | Meaning |
| --- | --- |
| 0 | every file parsed |
| 1 | at least one grammar error |
| 2 | the check could not run (no thinkorswim, no JDK, disabled) |

Exit 2 is deliberate: a gate that cannot run must never report success. Use
`--keep-going` to report all files instead of stopping at the first failure, and
`--allow-empty` to accept a tree with no `.thinkscript` files (otherwise a run
that checked zero files also exits 2).

Under the hood: a 59-line reflection shim compiles against the jars already on
your machine and asks their parser. Nothing is bundled.

If the parser itself cannot run — missing JDK, renamed classes after a ToS
update, a timeout — the exit code is 2 and the files are **not** reported as
passing.

---

## `tos new`

Scaffold a file from a template.

```console
$ tos new study trend/ema_cloud_flip
$ tos new scan ema_flip_scan
$ tos new columns/momentum/rsi_col --name "RSI Distance"
```

Kind can be inferred from the path (`columns/...` → column). Names must be
`lower_snake_case`. A project's own `templates/<kind>.thinkscript` wins over the
packaged starter, so local customisations apply.

Exit codes: `0` created, `2` on a bad kind, a non-snake_case name, an existing
target (never overwrites), or a path outside the project.

---

## `tos init`

Scaffold a project into the current directory.

```console
$ tos init                 # strict profile
$ tos init --profile loose # language rules only
$ tos init --force         # overwrite
```

Writes `tos.toml`, artifact directories, templates, `docs/validation.md`, a
`justfile`, `.gitignore`, and appends a conventions section to `AGENTS.md`.

`--force` **replaces** `justfile` and `.gitignore` outright rather than merging —
if you have customised either, check them afterwards. An unknown `--profile` is
rejected before anything is written.

`tos init` still runs when `tos.toml` is broken, because it is the command you
reach for to repair a project.

Exit codes: `0` written, `2` on an unknown profile or an unwritable path.

---

## `tos docs`

The bundled ThinkScript knowledge base, available from any project.

```console
$ tos docs --list
$ tos docs gotchas
$ tos docs --grep "crosses above"
```

Exit codes: `0` on success, `1` when `--grep` finds nothing, `2` for an unknown
topic or usage error.

---

## `tos explain`

Look a function or constant member up in the registry.

```console
$ tos explain TrueRange
TrueRange  [volatility]  confidence=verified
  TrueRange(high, close, low) - three required arguments

$ tos explain HasOption
HasOption  [option]  confidence=unverified
  internal API only; prefer IsOptionable
  WARNING: unverified. Paste-test before relying on it.

$ tos explain Color.LIGHT_RED
Color.LIGHT_RED: valid Color member
```

Exit 1 when the name is unknown — but an unknown name means "not in the curated
registry", not "invalid".

---

## `tos mcp`

Serve the toolkit to a coding assistant over the
[Model Context Protocol](https://modelcontextprotocol.io) on stdio. It is a
long-running process, not a one-shot command.

```console
$ tos mcp
```

There is no transport flag: stdio is the only transport.

Nothing but JSON-RPC is written to stdout — a single stray `print` would corrupt
the stream, so every diagnostic goes to stderr. The process exits 0 when stdin
closes.

Tools exposed:

| Tool | Arguments | Returns |
| --- | --- | --- |
| `tos_lint` | `paths`, `profile`, `strict` | JSON: `ok`, `files_checked`, `error_count`, `warning_count`, and `findings[]` where each finding has `path`, `line`, `code`, `severity`, `message`, `hint` |
| `tos_explain` | `name` | category and confidence for a function, or membership for a constant |
| `tos_docs` | `topic`, `grep` | list topics, read one, or search the reference. `topic` must name a bundled topic; an arbitrary path is rejected |
| `tos_syntax_check` | `paths` | per-file grammar result. When no thinkorswim install is available this returns `isError: true` with an explanation |

Protocol details that matter when writing a client:

- **`isError` means the call failed, not that your code is wrong.** A lint run that
  finds `E071` returns normally with the findings in the payload. `isError: true`
  is reserved for operational failures: a bad path, an unknown `tos.toml` topic, an
  unavailable parser.
- **Notifications never receive a response** — including malformed ones, since a
  message with no `id` is a notification.
- **A malformed request cannot kill the server**, but the error code tells you what
  happened rather than everything collapsing to one value:

| Situation | JSON-RPC error |
| --- | --- |
| body is not valid JSON | `-32700` parse error |
| method is missing | `-32600` invalid request |
| unknown method | `-32601` method not found |
| `tools/call` with a bad or missing `name`, or non-object `arguments` | `-32602` invalid parameters |
| a tool fails operationally | a normal result with `isError: true`, not an error object |

**A broken `tos.toml` stops the server at startup** (exit 2) rather than surfacing
per request, so fix the config before wiring the server into a client.

Registering it, and why an assistant should call `tos_explain` before writing a
function call: [Agents and CI](agents.md).

## `tos review`

Adversarial review. The prompt assumes the author is wrong; the model is pinned.

```console
$ tos review --mode diff            # uncommitted changes (the commit gate)
$ tos review --mode files a b       # specific files or directories
$ tos review --mode audit           # every .thinkscript in the repo
$ tos review --harness claude --model claude-opus-5-5   # substitute
```

| Exit | Meaning |
| --- | --- |
| 0 | PASS or WARN from the pinned gate |
| 1 | BLOCK — do not commit |
| 2 | could not run, or no parseable verdict (treat as untrustworthy) |
| 3 | substitute run told you PASS/WARN — **not** the gate |

Behaviour worth knowing:

- **It refuses to run when lint already reports errors.** Reviewing code that
  does not parse wastes the call and can produce a false PASS.
- **The verdict must be the first line** of the reply. Anything else exits 2.
- **It lints every configured target first**, not just the files under review, and
  exits 1 if any static error exists — the same code BLOCK uses.
- **A clean tree exits 0** with "nothing in scope".
- **`paths` is only honoured with `--mode files`.** `--mode diff` and `--mode audit`
  take their scope from git and from the configured targets, so passing a path
  alongside them is silently ignored.
- **Too-large input fails closed.** `--mode files` exits 2 rather than reviewing a
  subset when the selection exceeds the size budget; `--mode diff` names the files
  it could not inline and warns that the verdict is incomplete.
- Any harness other than `codex` is treated as a substitute and needs its model
  named explicitly; a typo in `--harness` falls through to the `claude` path.
- **A substitute harness exits 3**, so a hook cannot mistake it for a gate pass.
- The report is saved to `.review/last.md`.
