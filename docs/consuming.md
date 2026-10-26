# Consuming tos-toolkit from another project

Three patterns, in order of how much you want to commit to.

---

## 1. New project

```console
$ mkdir my-tos-scripts && cd my-tos-scripts && git init
$ pipx install tos-toolkit
$ tos init
$ tos new study trend/ema_cloud_flip
$ just lint
```

`tos init` writes:

```text
tos.toml                     configuration
studies/{trend,momentum,volatility,volume,structure}/
scans/  strategies/  columns/
templates/                   copy-ready starters
docs/validation.md           the paste-test protocol
justfile                     lint / status / syntax / new / review / audit
.gitignore
AGENTS.md                    appended conventions section for AI agents
```

Nothing else is needed. The knowledge base ships inside the package, so
`tos docs` works here without locating the toolkit repo.

---

## 2. Existing project

The point of the layered design: you do **not** have to adopt our conventions to
get value.

### Adopt everything

```console
$ cd existing-repo
$ pipx install tos-toolkit
$ tos init                    # skips files that already exist
```

`tos init` never overwrites by default. It will not clobber an existing
`justfile`, `AGENTS.md`, or `.gitignore` — it appends the agent section only if
`tos-toolkit` is not already mentioned.

### Adopt only the language rules

If your files have no `# @key:` header and you do not want one:

```toml
# tos.toml
[profile]
name = "loose"
```

Now you get delimiter balance, `//`-isn't-a-comment, identifier collisions,
`rec` depth, unknown functions (opt-in), and the platform artifact rules — and no
header, layout, or `@status` complaints.

### Halfway: headers optional

```toml
[header]
mode = "optional"
```

Headers are checked **if present** and never demanded. Useful while migrating.

### Silence one noisy rule

```toml
[checks]
W090 = "off"                # rec self-reference depth (unverified platform rule)
unknown_functions = "off"   # registry too incomplete for this corpus
E073 = "off"                # bare-assignment check
```

Every code and every setting accepts `off` / `warn` / `error`.

---

## 3. CI and pre-commit

`tos lint` needs no thinkorswim, no JDK, and no network.

```yaml
# .github/workflows/lint.yml
- name: Install toolkit
  run: pip install git+https://github.com/<you>/tos-toolkit
- name: Lint ThinkScript
  run: tos lint --strict
```

Grammar checking is deliberately excluded from CI — it needs a licensed
thinkorswim install, and pretending otherwise is how a gate becomes theatre.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: tos-lint
        name: tos lint
        entry: tos lint
        language: system
        files: '\.thinkscript$'
```

Missing paths exit 2, so a typo in the hook cannot silently pass.

---

## Repo-to-repo wiring

| Approach | Command | When |
| --- | --- | --- |
| Editable local checkout | `pip install -e /path/to/tos-toolkit` | developing the toolkit and a consumer together (clone the toolkit first) |
| PyPI | `pip install tos-toolkit==0.2.2` | pinned, reproducible — preferred |
| Git | `pip install git+https://github.com/yorch/tos-toolkit@v0.2.2` | testing an unreleased commit |

Prefer a version pin over a floating branch: `tos lint` output is gate input, and
a rule change can flip a green build to red.

---

## What a consumer repo should NOT copy

- The toolkit's own `tools/` directory. That was the pre-package layout and it
  drifts per repo — the reason the package exists.
- The knowledge base. It ships in the package; use `tos docs` so you get updates.
- The adversarial review prompt. Use `tos review`, which pins the prompt and model
  so a project cannot quietly soften its own gate.

## What a consumer repo SHOULD own

- Its `tos.toml` (which profile, which exceptions).
- Its scripts.
- Its validation log (`docs/validation.md`), because only a human can fill it in.
- Its own ADRs for trading decisions. The toolkit has opinions about *code*, not
  about markets.
