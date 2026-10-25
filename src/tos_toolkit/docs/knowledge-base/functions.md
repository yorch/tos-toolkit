# ThinkScript Built-in Functions

Only functions we have evidence for. Confidence: ✓ confident, ~ verify, UNVERIFIED.

## Price sources

`open` `high` `low` `close` `volume` `hl2` `hlc3` `ohlc4` ✓

## Averages

| Function | Signature | Notes |
| --- | --- | --- |
| `Average` | `Average(src, len)` | Simple moving average. ✓ |
| `ExpAverage` | `ExpAverage(src, len)` | Exponential. ✓ |
| `WildersSmoothing` | `WildersSmoothing(src, len)` | ~ verify |
| `WeightedAverage` | `WeightedAverage(src, len)` | ~ verify |

## Window statistics

| Function | Signature | Notes |
| --- | --- | --- |
| `Highest` | `Highest(src, len)` | ✓ |
| `Lowest` | `Lowest(src, len)` | ✓ |
| `Sum` | `Sum(src, len)` | ~ verify |
| `StdDev` | `StdDev(src, len)` | ✓ |
| `Variance` | `Variance(src, len)` | ~ verify |

## Range / volatility

| Function | Signature | Notes |
| --- | --- | --- |
| `TrueRange` | `TrueRange(high, close, low)` | Requires 3 arguments. ✓ |
| `ATR` | `ATR(len)` | Uses Wilder's smoothing by default. ~ verify default |
| `BollingerBands` | varies | ~ verify |

## State / bar info

| Function | Signature | Notes |
| --- | --- | --- |
| `BarNumber` | `BarNumber()` | ✓ |
| `IsNaN` | `IsNaN(x)` | ✓ |
| `CompoundValue` | `CompoundValue(len, visibleData, historicalData)` | ✓ |
| `GetValue` | `GetValue(series, offset)` | Takes a series, not a study name. ✓ |
| `HighestAll` | `HighestAll(src)` | ~ verify |
| `LowestAll` | `LowestAll(src)` | ~ verify |

## Time

| Function | Signature | Notes |
| --- | --- | --- |
| `GetYYYYMMDD` | `GetYYYYMMDD()` | ~ verify |
| `SecondsFromTime` | `SecondsFromTime(hhmm)` | ~ verify. Argument is HHMM integer. |
| `SecondsTillTime` | `SecondsTillTime(hhmm)` | ~ verify. Negative after target time. |
| `GetTime` | `GetTime()` | ✓ |
| `GetDay` | `GetDay()` | ~ verify |
| `GetMonth` | `GetMonth()` | ~ verify |
| `GetYear` | `GetYear()` | ~ verify |
| `GetWeek` | `GetWeek()` | ~ verify |
| `GetQuarter` | `GetQuarter()` | ~ verify |

## Drawing

| Function | Signature | Notes |
| --- | --- | --- |
| `AddLabel` | `AddLabel(visible, text, color)` | ✓ |
| `AddChartBubble` | `AddChartBubble(visible, price, text, color, isUp)` | ✓ |
| `AddCloud` | `AddCloud(a, b, colorA, colorB)` | ✓ |
| `AddVerticalLine` | `AddVerticalLine(visible, text, color)` | ~ verify |
| `AddArrow` | `AddArrow(visible, price, isUp, color)` | ~ verify |
| `AssignPriceColor` | `AssignPriceColor(color)` | ✓ |
| `AssignBackgroundColor` | `AssignBackgroundColor(color)` | ✓ |

## Math

| Function | Signature | Notes |
| --- | --- | --- |
| `AbsValue` | `AbsValue(x)` | ~ verify |
| `Ceil` | `Ceil(x)` | ~ verify |
| `Floor` | `Floor(x)` | ~ verify |
| `Round` | `Round(x, digits)` | Two-arg form ~ verify |
| `Max` | `Max(a, b)` | ✓ |
| `Min` | `Min(a, b)` | ✓ |
| `Power` | `Power(base, exp)` | ~ verify |
| `Sqrt` | `Sqrt(x)` | ~ verify |
| `Log` | `Log(x)` | ~ verify |
| `Exp` | `Exp(x)` | ~ verify |

## Option-related (UNVERIFIED — high hallucination risk)

| Function | Notes |
| --- | --- |
| `IsOptionable` | Documented capability test. ✓ (per docs) |
| `HasOption` | NOT confirmed. Prefer IsOptionable. UNVERIFIED |
| `GetStrike` | Returns charted contract's strike. ✓ (per docs) |
| `GetUnderlyingSymbol` | Returns underlying symbol. ✓ (per docs) |
| `GetATMOption` | Chain selection. UNVERIFIED spelling/arity |
| `GetNextOTMOption` | Chain selection. UNVERIFIED spelling/arity |
| `GetExpirationDate` | UNVERIFIED |
| `IsPut` / `IsCall` | UNVERIFIED |
| `GetDaysToExpiration` | UNVERIFIED |

## Aggregation

| Function | Notes |
| --- | --- |
| `close(period = AggregationPeriod.DAY)` | Higher-timeframe read. Repaints intrabar. ✓ |

## Other

| Function | Notes |
| --- | --- |
| `Root` | Returns futures root symbol. ~ verify |
| `GetATMOption` | Option chain selector. UNVERIFIED |
| `HasOption` | Option availability. UNVERIFIED (use IsOptionable) |

## Common patterns

### NaN-safe division
```thinkscript
def dSafe = if IsNaN(denom) or denom == 0 then 1 else denom;
def ratio = num / dSafe;
```

### Readiness gate
```thinkscript
def isReady = !IsNaN(fast) and !IsNaN(slow);
def wasReady = !IsNaN(fast[1]) and !IsNaN(slow[1]);
```

### Cross detection
```thinkscript
def crossedUp = isReady and wasReady and isBull and !priorBull;
```
