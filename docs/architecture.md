# Architecture

## Shape

```text
src/tos_toolkit/
├── cli.py            argparse surface; one handler per subcommand
├── config.py         tos.toml discovery, profile resolution, rule levels
├── diagnostics.py    Finding / Report / Level / exit codes
├── lexer.py          clean-room tokenizer + statement splitter
├── registry.py       function & constant lookup over data/*.json
├── knowledge.py      access to the bundled docs
├── checks/
│   ├── __init__.py   Context + rule dispatch + DEFAULT_LEVELS
│   ├── language.py   LAYER 1: true of ThinkScript anywhere
│   ├── artifacts.py  LAYER 1: platform rules for scans/columns/strategies
│   ├── header.py     LAYER 2: the # @key: block (profile-gated)
│   └── layout.py     LAYER 2: kind-vs-directory, naming (profile-gated)
├── parser/bridge.py  optional reflection bridge to a local ToS install
├── parser/java/      Checker.java — a shim, contains no Schwab code
├── review.py         adversarial review harness (claude | codex)
├── scaffold.py       `tos new` and `tos init`
├── data/             functions.json, constants.json, profiles/*.toml
├── docs/             knowledge base, shipped as package data
└── prompts/          the adversarial review prompt
```

## The layering rule

**A rule belongs in Layer 1 if it is true of ThinkScript anywhere. Otherwise it
belongs in Layer 2.**

This is the single most important design constraint, because getting it wrong is
what makes a linter unusable outside its author's repository:

- *"A scan cannot call `AddLabel`"* — Schwab's rule. Layer 1.
- *"Every file must carry `# @status:`"* — our rule. Layer 2.
- *"`def Foo` and `plot foo` are the same identifier"* — the language is
  case-insensitive. Layer 1. (This one caused a real failed paste.)
- *"Studies live in `studies/<category>/`"* — our rule. Layer 2.

Layer 2 modules read `config.header_mode` and bail out when it is `off`, and
`layout.py` additionally requires the file to sit inside a configured kind
directory — so pointing the tool at a foreign corpus triggers neither.

## Data flow

```text
text → Config
     → Context (tokens, statements, masked code, header, rel path)
     → checks/{language,header,artifacts,layout}.check(ctx)
     → [Finding]  (filtered by per-rule level)
     → Report → exit code
```

`Context` is cheap to build and has no I/O after construction, which keeps the
rules pure and the tests fast.

## Rules and levels

Every diagnostic code has a default severity in `checks/__init__.DEFAULT_LEVELS`.
`tos.toml` can override any code — or any *setting* such as
`unknown_functions` — to `off` / `warn` / `error`.

Codes are stable API. `E071` means "case-insensitive identifier collision"
forever; new behaviour gets a new code.

Ranges:

| Range | Meaning |
| --- | --- |
| `E001`–`E006` | lexical and file hygiene |
| `E101`–`W104` | header block (gated) |
| `E120` | artifact kind vs location (gated) |
| `E031` | declaration placement |
| `E401`–`W402` | artifact-specific restrictions |
| `E050` | asset class |
| `W103`, `W104` | input documentation |
| `E070`–`E073` | identifiers |
| `W001`, `W002` | style |
| `W050`, `W090`, `W091` | honesty, unverified behaviour |
| `W080`, `W081` | naming (gated) |

## Why the lexer is hand-written

The parser in thinkorswim is JavaCC-generated and its grammar is recoverable, but
reconstructing it would be both a derivative work and a maintenance trap (three
ToS versions were present on one machine at the time of writing). The hand-written
lexer only needs to be *faithful*, not equivalent: it splits statements, tracks
bracket depth, drops comments, and preserves line numbers. Real grammar
validation is delegated to the optional bridge, which cannot drift because it *is*
the platform.

See [`adr/0004-no-jar-redistribution.md`](adr/0004-no-jar-redistribution.md).

## Testing

```console
$ just test
```

`tests/test_lexer.py` covers tokenizing edge cases (`//` vs `#`, strings with
escapes, multi-line statements). `tests/test_checks.py` pairs a fixture with each
diagnostic so a rule change that breaks a code is caught immediately.
