# Agents and CI

Three ways to put this in front of an assistant or a pipeline, cheapest first.

All of them assume the toolkit is installed:

```console
$ pipx install tos-toolkit     # or: uv tool install tos-toolkit
```

---

## 1. `AGENTS.md` — conventions an assistant reads

`tos init` appends a section to the project's `AGENTS.md` covering the commands,
the "never invent a function" rule, the `@status` lifecycle, and the NaN
discipline. Any assistant that reads `AGENTS.md` inherits the conventions without
being told.

That is the whole integration for chat-style assistants: no protocol, no install
step for the assistant itself.

---

## 2. MCP — the toolkit as native tools

`tos mcp` serves four tools over the Model Context Protocol on stdio. The
assistant calls them directly instead of shelling out and parsing output.

```console
$ tos mcp
```

| Tool | Arguments | Purpose |
| --- | --- | --- |
| `tos_lint` | `paths`, `profile`, `strict` | Static analysis. Returns structured findings with `file`, `line`, `code`, `severity`, `hint`. |
| `tos_explain` | `name` | Is this function real? Returns the category and a confidence level. |
| `tos_docs` | `topic`, `grep` | The bundled reference: list topics, read one, or search. |
| `tos_syntax_check` | `paths` | Grammar check via a local thinkorswim install. When ToS or a JDK is absent it returns `isError: true` explaining that the check could not run — not a pass. |

`paths` accepts files or directories and defaults to the configured targets.
`profile` is `strict` or `loose`. `topic` must name a bundled topic (an arbitrary
path is rejected), and `grep` searches the whole reference instead.

### Registering it

Claude Code, Codex, and other MCP clients take a command plus arguments:

```json
{
  "mcpServers": {
    "tos-toolkit": {
      "command": "tos",
      "args": ["mcp"]
    }
  }
}
```

Because the server is invoked from your project directory, `tos_lint` picks up
that project's `tos.toml` automatically.

### Design notes

- **No dependencies.** MCP's stdio transport is JSON-RPC over stdin/stdout, so no
  SDK is required and the package stays dependency-free.
- **Stdout is sacred.** Only JSON-RPC reaches stdout; every diagnostic goes to
  stderr. One stray `print` would corrupt the stream.
- **`isError` means the call failed, not that your code is wrong.** A lint run
  that finds errors returns normally with the findings in the payload — an agent
  should read them. `isError: true` is reserved for operational failures: a bad
  path, a missing config, an unavailable parser.
- **A bad argument cannot kill the server.** Every failure is contained per
  request; the loop keeps serving.

The `initialize` response also carries `instructions`, so a client that surfaces
server instructions gets the "verify functions, never claim it works" guidance for
free.

---

## 3. GitHub Action — enforcement in CI

The Action installs the pinned version, lints, and turns findings into inline
`file:line` annotations:

```yaml
name: ThinkScript
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: yorch/tos-toolkit/.github/actions/lint@v0.2.1   # Action ships from 0.2.0
        with:
          paths: studies scans strategies columns
          profile: strict
          version: "0.2.1"
          strict: "true"
```

| Input | Default | Notes |
| --- | --- | --- |
| `paths` | `.` | Space separated. **Point it at your artifact directories.** The default walks the whole repository; vendor and build directories are skipped, but a repo that also contains TypeScript will still trip `E005` on its own `.ts` files. |
| `profile` | `strict` | `loose` for a corpus without header conventions. Note that a project's own `tos.toml` still applies on top, so a `tos.toml` written by `tos init` keeps requiring headers even under `loose`. |
| `version` | `latest` | **Pin it.** A new rule can fail a green build. |
| `strict` | `false` | Treat warnings as failures. |
| `annotations` | `true` | Inline markers. Set `false` for a plain log. |
| `python-version` | `3.12` | Version used to run the linter. |
| `artifact-name` | `tos-lint-findings` | Artifact name for the findings file. Two invocations in one run need distinct names. |

Outputs: `errors`, `warnings`, and `json` (path to the findings file, also
uploaded as an artifact).

No thinkorswim and no JDK are needed — the grammar check is deliberately not part
of CI, because requiring a licensed desktop platform on a runner is how a gate
becomes theatre.

### Consuming only the Python package

Nothing forces you to use the Action:

```yaml
- run: pip install "tos-toolkit==0.2.1"
- run: tos lint --strict --json > findings.json
```

---

## Which to use

| Situation | Use |
| --- | --- |
| Assistant writing scripts interactively | MCP — it stops guessing function names |
| Assistant in CI or a headless agent loop | MCP over stdio, or plain `tos lint --json` |
| Repository hygiene on every PR | the GitHub Action |
| Human at a terminal | the CLI |

The honest limit applies to all of them: **none of this can tell you a script
works.** `tos lint` catches structure, `syntax-check` catches grammar, and only
pasting into thinkorswim proves the thing renders. An assistant should never be
allowed to mark a script `validated` on its own — that is why `@status` is
documented as a human-only transition.
