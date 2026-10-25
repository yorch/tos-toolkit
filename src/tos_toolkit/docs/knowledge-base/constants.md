# ThinkScript Constants and Enum Members

## Color

Named colors only. Never raw integer codes.

Bull/bear palette repo-wide: green for bullish, red for bearish, gray for neutral,
yellow for attention.

| Constant | Notes |
| --- | --- |
| `Color.GREEN` / `Color.RED` / `Color.GRAY` / `Color.YELLOW` | ✓ |
| `Color.CYAN` / `Color.ORANGE` / `Color.WHITE` | ✓ |
| `Color.UPTICK` / `Color.DOWNTICK` | ✓ |
| `Color.LIGHT_RED` / `Color.LIGHT_GREEN` / `Color.LIGHT_GRAY` | ~ verify (untested) |
| `Color.DARK_RED` / `Color.DARK_GREEN` | ~ verify |
| `Color.PLUM` / `Color.PINK` / `Color.MAGENTA` | ~ verify |

## PriceType

| Constant | Notes |
| --- | --- |
| `PriceType.BID` | ✓ |
| `PriceType.ASK` | ✓ |
| `PriceType.LAST` | ✓ |
| `PriceType.MARK` | ✓ |

Restriction: bid/ask/mark reads require intraday charts spanning at most 15 days
(non-forex).

## AggregationPeriod

| Constant | Notes |
| --- | --- |
| `AggregationPeriod.MIN` | ✓ |
| `AggregationPeriod.FIVE_MIN` | ✓ |
| `AggregationPeriod.FIFTEEN_MIN` | ✓ |
| `AggregationPeriod.THIRTY_MIN` | ✓ |
| `AggregationPeriod.HOUR` | ✓ |
| `AggregationPeriod.FOUR_HOURS` | ✓ |
| `AggregationPeriod.DAY` | ✓ |
| `AggregationPeriod.WEEK` | ✓ |
| `AggregationPeriod.MONTH` | ✓ |
| `AggregationPeriod.OPT_EXP` | ✓ |

## OrderType

| Constant | Notes |
| --- | --- |
| `OrderType.BUY_TO_OPEN` | ✓ |
| `OrderType.SELL_TO_CLOSE` | ✓ |
| `OrderType.BUY_TO_CLOSE` | ~ verify |
| `OrderType.SELL_TO_OPEN` | ~ verify |

## Curve (plot styles)

| Constant | Notes |
| --- | --- |
| `Curve.FIRM` | ✓ (solid) |
| `Curve.SHORT_DASH` | ~ verify |
| `Curve.LONG_DASH` | ~ verify |
| `Curve.POINTS` | ~ verify |

## AverageType

| Constant | Notes |
| --- | --- |
| `AverageType.SIMPLE` | ~ verify |
| `AverageType.EXPONENTIAL` | ~ verify |
| `AverageType.WEIGHTED` | ~ verify |
| `AverageType.WILDERS` | ~ verify |

## PaintingStrategy

| Constant | Notes |
| --- | --- |
| `PaintingStrategy.LINE` | ✓ |
| `PaintingStrategy.HISTOGRAM` | ✓ |
| `PaintingStrategy.BOOLEAN_WEDGE` | ~ verify |
| `PaintingStrategy.VALUES_ABOVE` | ~ verify |

## Other

| Constant | Notes |
| --- | --- |
| `Double.NaN` | The undefined value. ✓ |
| `Double.POSITIVE_INFINITY` | ✓ |
| `Double.NEGATIVE_INFINITY` | ✓ |
| `yes` / `no` | Boolean literals (1 / 0). ✓ |
