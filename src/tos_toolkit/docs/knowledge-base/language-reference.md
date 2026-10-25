# ThinkScript Language Reference

## Execution model

ThinkScript is a **series language**, not an imperative language.

- A script is evaluated **once per bar**, left to right across the chart history.
- Every value is a **series**: one number per bar. `close` is a series, not a scalar.
- `close[1]` is the previous bar's close. `close[-1]` is the **next** bar's close
  (future offset — legal but a lookahead hazard outside `AddOrder`).
- There are **no loops over bars** in the ordinary sense. The platform loops for
  you. Your job is to express each value as a function of the current bar and
  prior bars.
- There is **no `while`**, no `break`, no `continue`, no early return, and no
  mutable assignment (`x = x + 1` is not a statement).

## Reserved words

| Word | Purpose |
| --- | --- |
| `def` | A computed value (series). Not displayed. Readable via `[n]`. |
| `rec` | A recursively defined value. Self-referencing via `[1]`. |
| `plot` | A drawn output. Becomes a visible line/label. In scans, the boolean result. |
| `input` | A user-configurable parameter with a default value. |
| `fold` | The only iteration construct. `fold i = 0 to N with acc = 0 do ...` |
| `script` | Defines a file-local reusable function block. |
| `if … then … else …` | Conditional expression (NOT statement). Both branches evaluated. |
| `declare` | Chart/panel declaration. Must be first executable statement. |

## Declarations

`declare` statements must appear before any other executable statement.

| Declaration | Effect |
| --- | --- |
| `declare upper;` | Overlay on the price chart. |
| `declare lower;` | Separate panel below the chart. |
| `declare once_per_bar;` | Restrict evaluation to once per bar. |
| `declare hide_on_intraday;` | Hide the study on intraday charts. |
| `declare hide_on_daily;` | Hide on daily and above. |
| `declare weak_volume_dependency;` | Places study in volume subgraph / ties scaling to volume. ~ |
| `declare real_size;` | Controls absolute scaling of a superimposed lower study. ~ |

A study that draws on the price axis must declare `upper`. A scan must not
declare either. A watchlist column likewise.

## Data types and constants

ThinkScript is loosely typed. Values are series (one per bar). Key constants:

- `Double.NaN` — the undefined value. Contagious in arithmetic.
- `Double.POSITIVE_INFINITY`, `Double.NEGATIVE_INFINITY` — from division by zero.
- `yes` / `no` — boolean literals (equivalent to 1 / 0).
- `Color.*` — named colors (see constants.md).
- `PriceType.*` — BID, ASK, LAST, MARK.
- `AggregationPeriod.*` — MIN, FIVE_MIN, FIFTEEN_MIN, THIRTY_MIN, HOUR, FOUR_HOURS, DAY, WEEK, MONTH, OPT_EXP.
- `OrderType.*` — BUY_TO_OPEN, SELL_TO_CLOSE, etc.
- `Curve.*` — FIRM, SHORT_DASH, LONG_DASH, etc.

## Operators

| Operator | Meaning |
| --- | --- |
| `+`, `-`, `*`, `/` | Arithmetic |
| `==`, `!=`, `<`, `>`, `<=`, `>=` | Comparison (returns 0/1) |
| `and`, `or`, `!` | Logical |
| `[n]` | Historical offset (n bars back). Negative = forward. |
| `=` | Assignment (in def/rec/plot/input) |

## Indexing

- `close[1]` — previous bar's close.
- `close[-1]` — next bar's close (future offset, legal but dangerous).
- `GetValue(series, offset)` — access a series at an offset.

## Comments

- `#` starts a comment. Everything after `#` on the line is ignored.
- `//` is NOT a comment. Using it is a syntax error.

## String literals

- Double-quoted: `"text"`.
- Concatenation with `+`: `"PDH " + Round(pdHigh, 2)`.
- String-valued `if`: `if cond then "A" else "B"` — believed to work, unverified.

## Multi-timeframe reads

```thinkscript
def dailyClose = close(period = AggregationPeriod.DAY);
```

- First bars are NaN until the higher timeframe has history.
- On an intraday chart, daily values update through the session (repainting).
- Must declare `@repaints: yes` when used.

## Asset class detection

ThinkScript does not have runtime asset-class detection. You declare `@assets`
in the header and branch on capability checks (e.g., `IsOptionable()`).
