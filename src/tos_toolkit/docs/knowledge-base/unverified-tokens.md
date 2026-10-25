# Unverified language tokens

Keywords and operators that exist in the platform's own parser token set but are
**not documented** in the official reference we have, and not covered elsewhere in
this knowledge base.

Provenance: token and rule names were read from the tokenizer constants of a
locally installed `thinkscript-parser` jar (see
[ADR 0004](../adr/0004-no-jar-redistribution.md)). A token existing means the
*lexer* accepts it. It says nothing about semantics, arity, or whether it is
reachable from user scripts.

**Confidence: UNVERIFIED — do not use in a script without a paste-test.**

## Keywords not yet documented here

| Token | Guess only — do not trust | Status |
| --- | --- | --- |
| `switch` | Multi-branch selection, with `case` and `default` | UNVERIFIED |
| `case` | Branch label inside `switch` | UNVERIFIED |
| `default` | Fallback branch in `switch` | UNVERIFIED |
| `profile` | Possibly performance/data profiling, not a trading construct | UNVERIFIED |
| `reference` | Unclear; may relate to referencing another study | UNVERIFIED |
| `within` | Likely the "within N bars" test, e.g. `close crosses above ... within 5 bars` | UNVERIFIED |
| `ago` | Likely offset syntax, e.g. `5 bars ago` | UNVERIFIED |
| `is` | Likely `is true` / `is false` comparison | UNVERIFIED |
| `at` | Likely `at price` or `at time` anchor | UNVERIFIED |
| `between` | Likely `between a and b` range test | UNVERIFIED |
| `bar` / `bars` | Likely units for `ago` / `within` | UNVERIFIED |
| `from` / `to` | Bound markers, already seen in `fold` | partial |
| `crosses` | With `above` / `below`, a cross operator | UNVERIFIED |

## Operators not documented here

`CrossesAbove`, `CrossesBelow`, `CrossesAny` appear as named operators in the
parser's operator enum. The `crosses above` / `crosses below` syntax is widely
used in thinkorswim examples, but this repository has never tested it and
`docs/thinkscript-language.md` does not cover it.

## Why this file exists

Our own three scripts implement crosses manually:

```thinkscript
def crossedUp = isReady and wasReady and isBull and !priorIsBull;
```

If `crosses above` is real and does not evaluate both sides eagerly in a way that
breaks on `NaN`, it would be shorter and less error-prone. It is worth one
paste-test to find out — and if it works, it belongs in
`docs/snippets/` as the canonical cross.

## How to promote an entry

1. Paste a one-line study that uses the token. Record the exact error or result.
2. If it works, document the real syntax and semantics in
   `docs/thinkscript-language.md`.
3. Add a row to the Limits Ledger with the date and the proving script.
4. Delete the entry from this file.
