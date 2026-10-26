# Configuration

`tos.toml` is discovered by walking up from the current directory. Resolution is
**built-in profile first, then your file on top**, so a project only states what
it changes.

```toml
[profile]
name = "strict"              # strict | loose

[project]
targets = ["studies", "scans", "strategies", "columns", "templates"]
kind_dirs = { study = "studies", scan = "scans" }
templates_dir = "templates"

[header]
mode = "required"            # required | optional | off
required = ["name", "kind", "panel", "assets", "timeframes", "version", "status"]
optional = ["inputs", "repaints", "notes", "superseded-by", "requires"]
statuses = ["draft", "validated", "in-use", "deprecated"]
assets = ["stock", "option", "future", "crypto", "index"]
timeframes = ["intraday", "daily", "weekly", "monthly"]
panels = ["upper", "lower", "none"]

[parser]
enabled = true
tos_path = "/Applications/thinkorswim"

[review]
harness = "codex"            # codex | claude
model = "gpt-6.1-sol"
effort = "high"

[checks]
unknown_functions = "warn"
W090 = "off"
```

---

## Profiles

| Profile | Header validation | Layout / naming | Unknown functions | Use when |
| --- | --- | --- | --- | --- |
| `strict` (default) | required | enforced | `warn` | you want the full workflow |
| `loose` | off | off | `off` | pointing at a corpus you did not write |

`loose` still applies every Layer 1 rule: delimiters, `//`-isn't-a-comment,
identifier collisions, `rec` depth, and the artifact rules for any file that
declares a `@kind`.

`loose` keeps every Layer 1 rule: delimiters, `//`-isn't-a-comment, identifier
collisions, `rec` depth, and the platform artifact rules.

---

## `[header] mode`

| Value | Behaviour |
| --- | --- |
| `required` | missing header is `E101` |
| `optional` | headers are checked **if present**, never demanded |
| `off` | header rules do not run at all |

`optional` is the migration path for an existing repo.

The remaining `[header]` keys replace the built-in vocabulary for an existing
repo:

| Key | Default | Purpose |
| --- | --- | --- |
| `required` | the seven keys above | header keys that must be present (`E102`) |
| `optional` | `inputs`, `repaints`, `notes`, `superseded-by`, `requires` | keys that are checked when present |
| `statuses` | `draft`, `validated`, `in-use`, `deprecated` | allowed `@status` values (`E103`) |
| `assets` | `stock`, `option`, `future`, `crypto`, `index` | allowed `@assets` values |
| `timeframes` | `intraday`, `daily`, `weekly`, `monthly` | allowed `@timeframes` values |
| `panels` | `upper`, `lower`, `none` | allowed `@panel` values |

Lists are **replaced**, not merged, so state the full set when you override one.

`mode` gates **header validation** (`header.py`) and **layout/naming**
(`layout.py`). It does not disable header *parsing*: if a file declares
`@kind`, the artifact rules (`E401`–`E405`) and the header-derived honesty rules
(`E031`, `E050`, `W050`) still apply, because they describe how the platform will
behave rather than how your repo is organised. A file with no header has no
declared kind, so none of those fire either.

---

### `--profile` does not override `tos.toml`

The flag chooses which built-in profile to start from; your `tos.toml` is applied
**on top**. In a project created by `tos init`, the generated file sets
`[header] mode = "required"`, so `tos --profile loose lint` still requires
headers until you change that key. To actually get language-only behaviour, set
the profile *in the file*.

A profile with no `targets` (as `loose` has) checks nothing unless you pass paths
or add targets — `tos --profile loose lint` in an unconfigured directory reports
"no target directories" and exits 0.

## Rule levels

Every diagnostic code, and every named setting, accepts `off` / `warn` / `error`:

```toml
[checks]
E071 = "error"          # a code
unknown_functions = "warn"   # a setting
W090 = "off"            # silence the rec-depth heuristic
```

Escalating `unknown_functions` to `error` is reasonable once your registry
coverage is good; leaving it at `warn` is right while it lags the platform.

An invalid level is a configuration error (exit 2), not a silent fallback.

---

## `[parser]`

```toml
[parser]
enabled = false             # disable grammar checking entirely (e.g. in CI)
tos_path = "/Applications/thinkorswim"
```

The path is the thinkorswim **installation root** (the directory containing
`usergui/` and `suit/`). The newest installed version is detected by numeric
version comparison, so `1994.0.56` beats `1993.3.1`.

A JDK is required — not just a JRE — because the shim has to be compiled. If the
package is installed read-only, the shim compiles into the system temp directory
instead.

---

## `[review]`

```toml
[review]
harness = "codex"
model = "gpt-6.1-sol"
effort = "high"
```

Pinning the harness and model in the repo makes the gate reproducible: changing
the reviewer becomes a visible, reviewable diff rather than an invisible per-run
flag.

Any harness/model other than `codex` + `gpt-6.1-sol` is treated as a **substitute**:
`tos` labels it, and exits 3 rather than 0, so automation cannot read it as a
pass.

---

## Environment variables

None are required. The CLI is entirely configured by `tos.toml`, flags, and the
`PATH` lookup for `codex` / `claude`.
