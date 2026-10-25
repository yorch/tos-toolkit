# ThinkScript Knowledge Base

Local reference material for ThinkScript (thinkorswim). Future agent sessions
should read these files before writing or reviewing ThinkScript code, to avoid
hallucinating functions, constants, or platform behaviours.

## Files

| File | Contents |
| --- | --- |
| [`language-reference.md`](language-reference.md) | Reserved words, declarations, data types, operators, execution model |
| [`functions.md`](functions.md) | Built-in functions by category with signatures and verification status |
| [`constants.md`](constants.md) | Enum members: Color, PriceType, AggregationPeriod, OrderType, AverageType, Curve, etc. |
| [`gotchas.md`](gotchas.md) | NaN propagation, rec rules, if evaluation, fold, multi-TF, platform limits |
| [`asset-classes.md`](asset-classes.md) | Stock, option, future, crypto, index specifics |
| [`artifact-rules.md`](artifact-rules.md) | Scan, column, and strategy restrictions |
| [`unverified-tokens.md`](unverified-tokens.md) | Keywords/operators known to the lexer but undocumented — UNVERIFIED |

## Confidence markers

- **✓ confident** — stable, widely used, unlikely to be wrong.
- **~ verify** — believed correct but unconfirmed. Test in the platform before depending on it.
- **UNVERIFIED** — not confirmed at all. Do not use without a paste-test.

## Source

Primary reference: https://toslc.thinkorswim.com/center/reference/thinkScript/

All entries that are not marked ✓ carry a TODO(verify) or are listed in the
Unverified section of the relevant file. When you confirm something in ToS,
add a row to the Limits Ledger in `docs/thinkscript-language.md`.
