# Rules

Every diagnostic has a stable code. **Codes are API**: `E071` means one thing
forever. New behaviour gets a new code.

Prefixes group by concern:

| Range | Concern | Gated by `[header] mode`? |
| --- | --- | --- |
| `E001`–`E006` | file and lexical hygiene | no |
| `E031` | declaration placement | no, but needs a declared `@kind` |
| `E050` | asset-class declarations | no, but needs a non-empty `@assets` |
| `E070`–`E073` | identifiers | no |
| `E101`–`W104` | header block | **yes** |
| `E120`, `W080`, `W081` | artifact kind vs location, naming | **yes** |
| `E401`–`W402` | artifact-specific platform restrictions | no, but needs a declared `@kind` |
| `W001`, `W002` | style | no |
| `W050` | repaint honesty | no, but needs `@repaints` present |
| `W090`, `W091` | unverified `rec` behaviour | no |

The header block is always *parsed*, even when `mode = "off"`. The mode gates
header validation and layout rules. Rules that describe **platform behaviour**
(`E401`, `E031`, `W050`) still apply whenever a file declares the header keys they
read, because they are about what thinkorswim will do, not about your repo layout.

---

## File and lexical (always on)

| Code | Default | Detects |
| --- | --- | --- |
| `E001` | error | tab character (ThinkScript sources use 4 spaces) |
| `E002` | error | missing trailing newline |
| `E003` | error | `//` used as a comment — it parses as two division operators |
| `E004` | error | unbalanced `(` `)` `[` `]` `{` `}` |
| `E005` | error | `.ts` extension, which collides with TypeScript |
| `E006` | error | file is not valid UTF-8 |

`E003` is the most valuable of these. `//` is not a comment in ThinkScript, and a
file full of `//` notes fails to apply with an error that points at arithmetic.

---

## Identifiers (always on)

| Code | Default | Detects |
| --- | --- | --- |
| `E070` | error | identifier declared twice (case-insensitive, within a namespace) |
| `E071` | error | `def`/`rec`/`input` collides with a `plot` by case |
| `E072` | warn | call to a function not in the registry |
| `E073` | warn | assignment without `def`/`rec`/`plot`/`input` |

### E071 — the one that actually breaks pastes

```thinkscript
rec pdHigh = if BarNumber() == 1 then high else pdHigh[1];
plot PdHigh = pdHigh;      # E071: same identifier as `pdHigh`
```

ThinkScript identifiers are case-insensitive, so this fails to apply with
`Identifier Already Used: PdHigh` and `Too early to access`. The fix is to rename
one — `pdHigh` becomes `priorDayHigh`.

`E070` covers same-namespace duplicates (`def a` twice, `input Length` plus
`def length`); `E071` owns the cross-namespace `def`↔`plot` pair, so one bug
produces one finding.

### E073 and E031 are warnings, deliberately

Two rules describe platform behaviour we have not confirmed in the editor:

- `E073` — the form `def x;` followed by a top-level `x = close;` may be legal.
- `E031` — a study with no `declare` at all may default to the upper panel.

Both ship as **warnings**. They become errors only after a paste-test proves them,
and `docs/knowledge-base/unverified-tokens.md` records the experiment to run.

---

## Asset classes (profile-gated)

| Code | Default | Detects |
| --- | --- | --- |
| `E050` | error | an option/future function used without the matching `@assets` entry |

Driven by the registry's category, not a hard-coded list, so it stays in sync as
the registry grows. A file that calls `GetATMOption()` must declare
`@assets: ..., option`.

---

## Header block (profile-gated)

| Code | Default | Detects |
| --- | --- | --- |
| `E031` | warn | a study or strategy that does not open with a `declare` (unverified) |
| `E101` | error | missing header block |
| `E102` | error | missing required key |
| `E103` | error | invalid `@status` / `@kind` / `@panel` / `@assets` / `@timeframes` |
| `E104` | error | `@inputs` omits a declared input |
| `W050` | warn | `AggregationPeriod` used while `@repaints: no` |
| `W101` | warn | unknown header key |
| `W102` | warn | `@version` is not semver |
| `W103` | warn | `@inputs` documents an input that does not exist |
| `W104` | warn | `@inputs` order differs from declaration order |

`E031` only runs when the artifact kind is known — without a header there is
nothing to say the file is a study.

`W050` exists because a higher-timeframe read updates through the session. A file
that claims `@repaints: no` while reading daily data is lying to anyone
backtesting it.

---

## Artifact kind vs location (profile-gated)

| Code | Default | Detects |
| --- | --- | --- |
| `E120` | error | `@kind` disagrees with the directory (`scan` outside `scans/`) |
| `W080` | warn | file name is not `lower_snake_case` |
| `W081` | warn | missing `_scan` / `_strat` / `_col` suffix |

These fire only when the file sits inside a **configured** kind directory, and
only when header validation is enabled. There is no rule enforcing a
`studies/<category>/` subdirectory structure — the category is your business.

---

## Artifact restrictions (always on)

These are the platform's rules, not ours.

| Code | Default | Detects |
| --- | --- | --- |
| `E401` | error | chart-only function inside a scan |
| `E402` | error | function unavailable in a watchlist column |
| `E403` | error | a scan whose last statement is not a `plot` |
| `E404` | error | a column without exactly one `plot` |
| `E405` | error | `declare upper/lower` in a scan or column |
| `W401` | warn | strategy with no `AddOrder` |
| `W402` | warn | scan plot is a constant, so every symbol matches |

`AddLabel` and `AssignBackgroundColor` **are** legal in columns; the other drawing
functions are not. Function names are matched case-insensitively, because
ThinkScript identifiers are.

`E403` checks that the last statement is a `plot`; it does not attempt to prove
the expression is boolean-comparison shaped.

**These do not require a header.** If a file has no `@kind`, the kind is inferred
from the configured directory, so a headerless `scans/foo.thinkscript` that calls
`AddLabel` still gets `E401`. Platform restrictions are not house style, and the
`loose` profile does not weaken them.

---

## Style and unverified behaviour (always on)

| Code | Default | Detects |
| --- | --- | --- |
| `W001` | warn | trailing whitespace |
| `W002` | warn | line over 100 columns (header `# @key:` lines exempt) |
| `W090` | warn | a `rec` referencing itself 3+ times |
| `W091` | warn | a `rec` self-referencing at an offset greater than `[1]` |

`W091` flags offsets **greater than** 1. `[0]` (the current bar) is not flagged.

`W090`/`W091` encode **unverified** platform behaviour. One self-reference per
branch — `rec x = if c then x[1] + 1 else x[1];` — is the ordinary form and is not
flagged. Three or more has no known precedent, so it warns and asks for a
paste-test rather than pretending to be certain.

---

## Silencing a rule

```toml
[checks]
W090 = "off"                # one code
unknown_functions = "off"   # one setting
```

Prefer silencing a *specific code* over switching to the `loose` profile: the
former is a decision you can see, the latter hides everything in Layer 2 at once.
