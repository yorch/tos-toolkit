# ThinkScript Gotchas and Platform Limits

## NaN propagation — the #1 killer

Most ThinkScript bugs are not syntax errors. They are **NaN propagation**.

- A value is `NaN` when undefined: insufficient history, division by zero, or
  a reference to a study that has not produced a value.
- `IsNaN(x)` tests it. ✓
- `NaN` is contagious: any arithmetic involving it yields `NaN`.
- Comparisons against `NaN` are `false`, so `x > 0` silently fails to fire.
- `0/0` and `1/0` do not throw; they produce `NaN`/`Infinity` quietly.

House rule: any value from division, window stats, or higher-timeframe reads
must be explicitly handled with `IsNaN`.

## The `if` trap

ThinkScript `if` is an expression and both branches are evaluated (eagerly).
`if denom == 0 then 0 else num / denom` still performs the division.

Whether the resulting NaN from the *untaken* branch contaminates the selected
finite result is **UNVERIFIED**. Do not assert either way.

House rule: guard the inputs, not the output:
```thinkscript
def dSafe = if IsNaN(denom) or denom == 0 then 1 else denom;
def ratio = num / dSafe;
```

## `rec` variable rules (UNVERIFIED)

- `rec x = x[1] + 1;` — believed fine.
- `rec x = x[2] + 1;` — believed not allowed (only [1]).
- `rec x = x[1] + x[1];` — believed not allowed (at most once per definition).
- `rec x = if cond then x[1] + 1 else x[1];` — believed allowed (once per branch).

These rules are **not confirmed**. Lint flags them as warnings, not errors.
Test in the platform before relying on them.

Common pattern:
```thinkscript
rec x = if condition then value else x[1];
```

## `fold` iteration

```thinkscript
def sum = fold i = 0 to length with s = 0 do s + GetValue(close, i);
```

- Upper bound is believed **exclusive** (`to length` = `length` iterations).
- `fold` is slow, has an iteration cap, and cannot mutate outside its accumulator.
- Never use in scans over large universes.

## Multi-timeframe reads

```thinkscript
def dailyClose = close(period = AggregationPeriod.DAY);
```

- First bars are NaN until history exists.
- On intraday charts, daily values update through the session (repainting).
- Must declare `@repaints: yes`.

## Platform limits

- **Study complexity budget**: finite computed values per study. Large folds and
  multi-TF reads hit this first.
- **Scanner throughput**: scan runs for every symbol on every bar. Keep scans cheap.
- **History depth**: `close[N]` for large N on short charts yields NaN.
- **Computed value budget**: exact number unknown. Simplify if study fails to load.

## Asset-class gotchas

### Stocks
- Extended hours data on intraday charts; open/close semantics differ.
- Use SecondsFromTime/SecondsTillTime for session gating.

### Options
- Option functions are the #1 hallucination site. Verify every name.
- Bid/ask reads require intraday charts ≤ 15 days (non-forex).
- `IsOptionable()` is documented; `HasOption()` is not confirmed.

### Futures
- Symbols: /ES, /NQ, /CL with contract months.
- `Root()` returns the root for rollover handling.
- Near-24h sessions; rollovers create synthetic gaps.

### Crypto
- 24/7: no cash session, weekend bars exist.
- "Daily" is usually UTC. No session logic reuse.
- Absolute thresholds meaningless; use relative measures.

### Index (SPX, NDX, RUT, VIX)
- Cash-settled, no tradable shares.
- No pre-market prints on SPX cash index.
- Volume may be 0 or NaN.

## Scan restrictions

- No chart-only functions: AddLabel, AddChartBubble, AddCloud, AddArrow,
  AddVerticalLine, AssignPriceColor, AssignBackgroundColor.
- No `declare upper` or `declare lower`.
- Must end with a boolean `plot`.
- Keep cheap: no fold, no multi-TF, no long lookbacks.

## Column restrictions

- One value `plot`.
- `AssignBackgroundColor` and `AddLabel` are the only drawing calls.
- No AddChartBubble, AddCloud, AddArrow, AddVerticalLine, AssignPriceColor.

## Strategy rules

- `AddOrder(type, condition, price, tradeSize, tickColor, arrowColor, name)`.
- Entry and exit conditions must be mutually exclusive.
- Must have an exit (SELL_TO_CLOSE).
- `open[-1]` is the documented next-bar fill price.

## Case sensitivity

ThinkScript identifiers are **case-insensitive**. `rec pdHigh` and `plot PdHigh`
are the same identifier. This causes "Identifier Already Used" errors.

Always use completely different names for rec variables and plot names.
