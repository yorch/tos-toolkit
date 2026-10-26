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
`--keep-going` to report all files instead of stopping at the first failure.

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
Never overwrites existing files unless `--force`.

---

## `tos docs`

The bundled ThinkScript knowledge base, available from any project.

```console
$ tos docs --list
$ tos docs gotchas
$ tos docs --grep "crosses above"
```

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
- Any harness other than `codex` is treated as a substitute and needs its model
  named explicitly; a typo in `--harness` falls through to the `claude` path.
- **A substitute harness exits 3**, so a hook cannot mistake it for a gate pass.
- The report is saved to `.review/last.md`.
