# save as fx_uncorrelated.py and run: python fx_uncorrelated.py
# Requires: pip install yfinance pandas numpy scipy
from itertools import combinations

import numpy as np
import pandas as pd
import yfinance as yf

# 1) Universe of pairs to consider (add/remove as you like)
tickers = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "USDCHF=X",
    "USDCAD=X",
    "AUDUSD=X",
    "NZDUSD=X",
    "EURJPY=X",
    "EURGBP=X",
    "GBPCHF=X",
    "AUDNZD=X",
    "AUDCAD=X",
]

# 2) Parameters
period = "60d"  # last 60 calendar days (change to '120d' or '180d' if you prefer)
interval = "1d"

# 3) Download close prices
data = yf.download(
    tickers, period=period, interval=interval, group_by="ticker", threads=True, progress=False
)
# yfinance returns MultiIndex; extract 'Close' for each symbol
close = pd.DataFrame({t: data[t]["Close"] for t in tickers})

# Drop rows with any NaN (market holidays / missing symbols) — or you can forward/backfill if you prefer
close = close.dropna()

if close.empty:
    raise SystemExit(
        "No usable price rows after dropna(). Try increasing the 'period' or check internet connectivity."
    )

# 4) Compute daily returns (log returns recommended)
returns = np.log(close / close.shift(1)).dropna()

# 5) Correlation matrix (Pearson)
corr = returns.corr()


# 6) Helper: greedy selection to find 5 pairs that minimize average absolute pairwise correlation
def avg_abs_corr_of_set(corr_df, selection):
    if len(selection) <= 1:
        return 0.0
    sub = corr_df.loc[selection, selection].abs()
    # take upper triangle without diagonal
    triu = sub.where(np.triu(np.ones(sub.shape), k=1).astype(bool))
    vals = triu.values[np.triu_indices_from(triu.values, k=1)]
    return float(np.nanmean(vals))


def greedy_min_avg_abs(corr_df, k=5):
    # start with the instrument having lowest avg abs correlation to all others
    avg_abs = corr_df.abs().mean().sort_values()
    selection = [avg_abs.index[0]]
    while len(selection) < k:
        best_candidate = None
        best_score = None
        for cand in corr_df.index.difference(selection):
            cand_set = [*selection, cand]
            score = avg_abs_corr_of_set(corr_df, cand_set)
            if best_score is None or score < best_score:
                best_score = score
                best_candidate = cand
        selection.append(best_candidate)
    return selection, best_score


selected, score = greedy_min_avg_abs(corr, k=5)


# 7) Also compute the 5-pair subset via brute-force (only if universe small)
def brute_min_avg_abs(corr_df, k=5):
    best = None
    best_score = None
    for combo in combinations(corr_df.index, k):
        score = avg_abs_corr_of_set(corr_df, combo)
        if best_score is None or score < best_score:
            best_score = score
            best = combo
    return list(best), best_score


# only run brute force when C(n,k) is reasonably small
brute_selected, brute_score = brute_min_avg_abs(corr, k=5)

# 8) Output results
pd.set_option("display.float_format", "{:.3f}".format)
print(f"\nCorrelation matrix (last {period} of daily returns):\n")
print(corr)

print("\nGreedy-selected 5-pair portfolio (min avg |r|):")
print(selected, "\navg_abs_corr =", round(score, 4))

print("\nBrute-force best 5-pair portfolio (exact, may be slower):")
print(brute_selected, "\navg_abs_corr =", round(brute_score, 4))


# 9) Optional: show pairwise abs correlations within the selected set
def show_submatrix(corr_df, sel):
    sub = corr_df.loc[sel, sel]
    print("\nPairwise correlations for selection:\n")
    print(sub)


show_submatrix(corr, selected)
