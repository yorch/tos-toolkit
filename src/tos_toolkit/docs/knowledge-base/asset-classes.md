# ThinkScript Asset Class Specifics

## Stock

- Regular session vs extended hours matters.
- Cash-settled index symbols (SPX, NDX, RUT) behave like stocks for price math
  but have no shares and no volume.
- Use SecondsFromTime/SecondsTillTime for session gating.
- Extended-hours data appears on intraday charts.

## Option

- The charted symbol is the contract; `GetUnderlyingSymbol()` gives the stock.
- Chain selection: `GetATMOption`, `GetNextOTMOption` (UNVERIFIED spelling).
- `IsOptionable()` guards against symbols with no chain (documented).
- Quotes: `close(priceType = PriceType.BID)` / `.ASK` / `.LAST` / `.MARK`.
- Bid/ask reads require intraday charts ≤ 15 days (non-forex).
- Greeks and IV functions exist but names are hallucination-prone. Verify each.
- Most option studies should be lower panels.

## Future

- Symbols: `/ES`, `/NQ`, `/CL`, `/GC` with contract months (e.g., `/ESZ5`).
- `Root()` returns the root for rollover handling (UNVERIFIED).
- Near-24h sessions; rollovers create synthetic gaps.
- Day high/low vs session high/low differ.
- Gap detection must ignore rollover bars.

## Crypto

- 24/7: no cash session, weekend bars exist.
- "Daily" is usually UTC. No session logic reuse.
- Volatility and volume scale differently from equities.
- Absolute thresholds meaningless; use relative measures.

## Index (SPX, NDX, RUT, VIX)

- Cash-settled, no tradable shares.
- No pre-market prints on SPX cash index.
- Volume may be 0 or NaN (not reliable).
- SPX cash index calculates to 16:00 ET; options trade to 16:15.
- VWAP on index may not be meaningful (volume is synthetic).
- Use SPY or /ES for reliable volume-based indicators.
- VIX is a volatility index, not a price index.
