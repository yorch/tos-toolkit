# ThinkScript Artifact Rules

## Studies (studies/)

- Chart overlay (`declare upper`) or lower panel (`declare lower`).
- Indicators, signals, labels, clouds.
- Every plot should be styled (default styling = bug).
- Offer `showX` booleans for every drawing element.
- @assets and @timeframes must match actual usage.

## Scans (scans/)

- Filter for the ToS Scanner. Exposes a boolean `plot` (position does not matter).
- No chart-only functions: AddLabel, AddChartBubble, AddCloud, AddArrow,
  AddVerticalLine, AssignPriceColor, AssignBackgroundColor.
- No `declare upper` or `declare lower`.
- Must expose exactly one `plot`; its position in the file does not matter.
  `plot Scan;` followed by `Scan = …;` is a documented form. Secondary
  aggregation (`AggregationPeriod`) is not supported in a scan (E407).
- Keep cheap: no fold, no multi-TF reads, no long lookbacks.
- Scanner evaluates for every symbol on every bar.
- Name files `*_scan.thinkscript`.

## Columns (columns/)

- Custom watchlist column. One value per symbol.
- One output: a value `plot`, or an `AddLabel` for formatted text. Custom
  quotes sort alphanumerically when the output is text.
- `AssignBackgroundColor` and `AddLabel` are the only drawing calls.
- No AddChartBubble, AddCloud, AddArrow, AddVerticalLine, AssignPriceColor.
- Columns render as text; format precision yourself.
- Keep fast: evaluated for every row of the watchlist.
- Name files `*_col.thinkscript`.

## Strategies (strategies/)

- Study that also emits orders via `AddOrder`.
- Produces a backtest report in the platform.
- `AddOrder(type, condition, price, tradeSize, tickColor, arrowColor, name)`.
- Entry and exit conditions must be mutually exclusive.
- Must have an exit (SELL_TO_CLOSE).
- Order price must be knowable at signal time.
- `open[-1]` is the documented next-bar fill price.
- @repaints must be honest (backtest depends on it).
- Name files `*_strat.thinkscript`.

## Templates (templates/)

- Copy-paste starters for each artifact kind.
- Exempt from directory/@kind cross-check in lint.
- All other lint rules apply.
- Carry @status: draft permanently.
- Never mark a template as validated.
