from __future__ import annotations

import math
import sys
import pandas as pd
import yfinance as yf

UUU = "UUU"; UUD = "UUD"; UDU = "UDU"; UDD = "UDD"
DUU = "DUU"; DUD = "DUD"; DDU = "DDU"; DDD = "DDD"

BUY_ONLY = 0; SELL_ONLY = 1; BUY_AND_SELL = 2

BUY_STOP  = "BUY_STOP"
SELL_STOP = "SELL_STOP"
BUY_LIMIT = "BUY_LIMIT"

WIN = "WIN"; LOSS = "LOSS"; EXPIRED = "EXPIRED"; OPEN = "OPEN"

def classifyCandle(o, c):
    return c > o

def detectPattern(df, bar):
    c = [classifyCandle(df["Open"].iloc[bar - 1 - i], df["Close"].iloc[bar - 1 - i]) for i in range(3)]
    c2, c1, c0 = c[2], c[1], c[0]
    lookup = {
        (True,  True,  True ): UUU, (True,  True,  False): UUD,
        (True,  False, True ): UDU, (True,  False, False): UDD,
        (False, True,  True ): DUU, (False, True,  False): DUD,
        (False, False, True ): DDU, (False, False, False): DDD,
    }
    return lookup[(c2, c1, c0)]

def barsToExpiry(expirationHours, timeframeHours=24):
    return max(1, round(expirationHours / timeframeHours))

def makeOrder(orderType, entry, sl, tp, openBar, expiryBar, lots=1.0):
    return [orderType, entry, sl, tp, openBar, expiryBar, lots, OPEN, None, None, 0.0]

I_TYPE=0; I_ENTRY=1; I_SL=2; I_TP=3; I_OPEN=4; I_EXPIRY=5
I_LOTS=6; I_RESULT=7; I_CLOSE_PRICE=8; I_CLOSE_BAR=9; I_PNL=10

def processPending(o, df, bar):
    if o is None or o[I_RESULT] != OPEN:
        return

    hi = df["High"].iloc[bar]
    lo = df["Low"].iloc[bar]

    if bar >= o[I_EXPIRY]:
        o[I_RESULT]    = EXPIRED
        o[I_CLOSE_BAR] = bar
        o[I_PNL]       = 0.0
        return

    if o[I_TYPE] == BUY_STOP:
        if hi >= o[I_ENTRY]:
            if lo <= o[I_SL]:
                o[I_RESULT] = LOSS;  o[I_CLOSE_PRICE] = o[I_SL];  o[I_PNL] = -(o[I_ENTRY] - o[I_SL])
            elif hi >= o[I_TP]:
                o[I_RESULT] = WIN;   o[I_CLOSE_PRICE] = o[I_TP];  o[I_PNL] = o[I_TP] - o[I_ENTRY]
            else:
                return
            o[I_CLOSE_BAR] = bar

    elif o[I_TYPE] == SELL_STOP:
        if lo <= o[I_ENTRY]:
            if hi >= o[I_SL]:
                o[I_RESULT] = LOSS;  o[I_CLOSE_PRICE] = o[I_SL];  o[I_PNL] = -(o[I_SL] - o[I_ENTRY])
            elif lo <= o[I_TP]:
                o[I_RESULT] = WIN;   o[I_CLOSE_PRICE] = o[I_TP];  o[I_PNL] = o[I_ENTRY] - o[I_TP]
            else:
                return
            o[I_CLOSE_BAR] = bar

    elif o[I_TYPE] == BUY_LIMIT:
        if lo <= o[I_ENTRY]:
            if lo <= o[I_SL]:
                o[I_RESULT] = LOSS;  o[I_CLOSE_PRICE] = o[I_SL];  o[I_PNL] = -(o[I_ENTRY] - o[I_SL])
            elif hi >= o[I_TP]:
                o[I_RESULT] = WIN;   o[I_CLOSE_PRICE] = o[I_TP];  o[I_PNL] = o[I_TP] - o[I_ENTRY]
            else:
                return
            o[I_CLOSE_BAR] = bar

def buyStop(df, bar, pending, log, pattern, dist, sl, tp, expiryBars):
    processPending(pending[0], df, bar)
    if pending[0] is not None and pending[0][I_RESULT] == OPEN:
        return

    if detectPattern(df, bar) == pattern:
        high  = float(df["High"].iloc[bar - 1])
        entry = high + dist
        o = makeOrder(BUY_STOP, entry, entry - sl, entry + tp, bar, bar + expiryBars)
        pending[0] = o
        log.append(o)

def sellStop(df, bar, pending, log, pattern, dist, sl, tp, expiryBars):
    processPending(pending[0], df, bar)
    if pending[0] is not None and pending[0][I_RESULT] == OPEN:
        return

    if detectPattern(df, bar) == pattern:
        low   = float(df["Low"].iloc[bar - 1])
        entry = low - dist
        o = makeOrder(SELL_STOP, entry, entry + sl, entry - tp, bar, bar + expiryBars)
        pending[0] = o
        log.append(o)

def buyLimit(df, bar, pending, log, pattern, dist, sl, tp, expiryBars):
    processPending(pending[0], df, bar)
    if pending[0] is not None and pending[0][I_RESULT] == OPEN:
        return

    if detectPattern(df, bar) == pattern:
        low   = float(df["Low"].iloc[bar - 1])
        entry = low - dist
        o = makeOrder(BUY_LIMIT, entry, entry - sl, entry + tp, bar, bar + expiryBars)
        pending[0] = o
        log.append(o)

def summarize(log, name):
    closed  = [o for o in log if o[I_RESULT] != OPEN]
    wins    = [o for o in closed if o[I_RESULT] == WIN]
    losses  = [o for o in closed if o[I_RESULT] == LOSS]
    expired = [o for o in closed if o[I_RESULT] == EXPIRED]
    wr      = len(wins) / len(closed) if closed else 0.0
    pnl     = sum(o[I_PNL] for o in closed)

    print(f"\n  {name.upper()}")
    print(f"  {'─'*40}")
    print(f"  {'total_trades':<20} {len(closed)}")
    print(f"  {'wins':<20} {len(wins)}")
    print(f"  {'losses':<20} {len(losses)}")
    print(f"  {'expired':<20} {len(expired)}")
    print(f"  {'win_rate':<20} {wr:.1%}")
    print(f"  {'total_pnl_pts':<20} {round(pnl, 1)}")
    return pnl

def run(df, pair, expirationHours, buyDist, buyPattern, buyRR, buySL, sellDist, sellPattern, sellRR, sellSL, limitDist, limitPattern, limitRR, limitSL, useReversal=True, lots=1.0):

    df = df.copy()
    df.columns = [c.capitalize() for c in df.columns]

    expiryBars = barsToExpiry(expirationHours)

    bsLog = []; ssLog = []; blLog = []
    bsPending = [None]; ssPending = [None]; blPending = [None]

    buyTP   = buySL  * buyRR
    sellTP  = sellSL * sellRR
    limitTP = limitSL * limitRR

    for bar in range(3, len(df)):
        buyStop( df, bar, bsPending, bsLog, buyPattern,   buyDist,   buySL,   buyTP,   expiryBars)
        sellStop(df, bar, ssPending, ssLog, sellPattern,  sellDist,  sellSL,  sellTP,  expiryBars)
        if useReversal:
            buyLimit(df, bar, blPending, blLog, limitPattern, limitDist, limitSL, limitTP, expiryBars)

    print(f"\n{'='*55}")
    print(f"  Backtest Summary — {pair}")
    print(f"{'='*55}")

    totalPnl  = summarize(bsLog, "buy stop")
    totalPnl += summarize(ssLog, "sell stop")
    if useReversal:
        totalPnl += summarize(blLog, "buy limit")

    print(f"\n  {'─'*40}")
    print(f"  {'COMBINED PNL (pts)':<20} {round(totalPnl, 2)}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    pair  = "AAPL"
    start = "2015-01-01"
    end   = "2024-12-31"

    print(f"Downloading {pair} daily data ({start} → {end}) …")
    raw = yf.download(pair, start=start, end=end, auto_adjust=True, progress=False)

    if raw.empty:
        print("No data downloaded. Check your internet connection or ticker symbol.")
        sys.exit(1)

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close"]].dropna()
    print(f"Loaded {len(df)} daily bars.\n")

    run(df, pair,
        expirationHours = 60,
        buyDist         = 1.50,
        buyPattern      = UUU,
        buyRR           = 1.4,
        buySL           = 5.00,
        sellDist        = 1.50,
        sellPattern     = UUU,
        sellRR          = 0.8,
        sellSL          = 3.00,
        limitDist       = 4.00,
        limitPattern    = UUU,
        limitRR         = 0.8,
        limitSL         = 5.00,
        useReversal     = True,
    )
