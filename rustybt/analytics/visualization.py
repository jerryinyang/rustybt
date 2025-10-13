#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied,
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Interactive visualization functions for Jupyter notebooks using Plotly.

All visualization functions support:
- Interactive hover tooltips with detailed information
- Zoom and pan capabilities
- Light and dark theme support
- Both pandas and polars DataFrames as input
"""

import pandas as pd
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots


def _ensure_pandas(data: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    """Convert Polars DataFrame to pandas if needed.

    Args:
        data: Input DataFrame (pandas or polars)

    Returns:
        Pandas DataFrame
    """
    if isinstance(data, pl.DataFrame):
        return data.to_pandas()
    return data


def _get_theme_colors(theme: str = "light") -> dict:
    """Get color scheme for charts based on theme.

    Args:
        theme: Either 'light' or 'dark'

    Returns:
        Dictionary of color values
    """
    if theme == "dark":
        return {
            "background": "#1e1e1e",
            "paper": "#2d2d2d",
            "text": "#e0e0e0",
            "grid": "#3a3a3a",
            "positive": "#00ff88",
            "negative": "#ff5252",
            "primary": "#4fc3f7",
        }
    else:  # light theme
        return {
            "background": "#ffffff",
            "paper": "#ffffff",
            "text": "#2e2e2e",
            "grid": "#e0e0e0",
            "positive": "#00c853",
            "negative": "#d32f2f",
            "primary": "#1976d2",
        }


def plot_equity_curve(
    backtest_result: pd.DataFrame | pl.DataFrame,
    title: str = "Portfolio Equity Curve",
    theme: str = "light",
    show_drawdown: bool = True,
) -> go.Figure:
    """Plot interactive portfolio equity curve.

    Args:
        backtest_result: DataFrame with 'portfolio_value' column and datetime index
        title: Chart title
        theme: Color theme ('light' or 'dark')
        show_drawdown: Whether to show drawdown subplot

    Returns:
        Plotly Figure object

    Example:
        >>> from rustybt.analytics import plot_equity_curve
        >>> results = algo.run()
        >>> fig = plot_equity_curve(results)
        >>> fig.show()
    """
    df = _ensure_pandas(backtest_result)
    colors = _get_theme_colors(theme)

    # Handle both index and column named datetime/date
    if df.index.name in ["date", "period_close"] or isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    elif "date" in df.columns:
        dates = df["date"]
    elif "timestamp" in df.columns:
        dates = df["timestamp"]
    else:
        dates = df.index

    # Get portfolio value column
    if "portfolio_value" in df.columns:
        values = df["portfolio_value"]
    elif "ending_value" in df.columns:
        values = df["ending_value"]
    else:
        raise ValueError("DataFrame must have 'portfolio_value' or 'ending_value' column")

    # Create figure with optional drawdown subplot
    if show_drawdown:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(title, "Drawdown"),
        )
        row_equity = 1
    else:
        fig = go.Figure()
        row_equity = None

    # Add equity curve
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines",
            name="Portfolio Value",
            line={"color": colors["primary"], "width": 2},
            hovertemplate="Date: %{x}<br>Value: $%{y:,.2f}<extra></extra>",
        ),
        row=row_equity,
        col=1 if show_drawdown else None,
    )

    # Calculate and plot drawdown if requested
    if show_drawdown:
        cummax = values.expanding().max()
        drawdown = (values - cummax) / cummax

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=drawdown * 100,
                mode="lines",
                name="Drawdown",
                line={"color": colors["negative"], "width": 1.5},
                fill="tozeroy",
                fillcolor="rgba(211, 47, 47, 0.2)",
                hovertemplate="Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>",
            ),
            row=2,
            col=1,
        )

    # Update layout
    fig.update_layout(
        template="plotly_dark" if theme == "dark" else "plotly_white",
        hovermode="x unified",
        showlegend=True,
        height=600 if show_drawdown else 400,
        plot_bgcolor=colors["background"],
        paper_bgcolor=colors["paper"],
        font={"color": colors["text"]},
    )

    # Update axes
    if show_drawdown:
        fig.update_xaxes(title_text="Date", gridcolor=colors["grid"], row=2, col=1)
        fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=colors["grid"], row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", gridcolor=colors["grid"], row=2, col=1)
    else:
        fig.update_xaxes(title_text="Date", gridcolor=colors["grid"])
        fig.update_yaxes(title_text="Portfolio Value ($)", gridcolor=colors["grid"])

    return fig


def plot_drawdown(
    backtest_result: pd.DataFrame | pl.DataFrame,
    title: str = "Portfolio Drawdown",
    theme: str = "light",
) -> go.Figure:
    """Plot portfolio drawdown over time.

    Args:
        backtest_result: DataFrame with 'portfolio_value' column and datetime index
        title: Chart title
        theme: Color theme ('light' or 'dark')

    Returns:
        Plotly Figure object

    Example:
        >>> fig = plot_drawdown(results)
        >>> fig.show()
    """
    df = _ensure_pandas(backtest_result)
    colors = _get_theme_colors(theme)

    # Get dates and values
    if df.index.name in ["date", "period_close"] or isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    elif "date" in df.columns:
        dates = df["date"]
    elif "timestamp" in df.columns:
        dates = df["timestamp"]
    else:
        dates = df.index

    if "portfolio_value" in df.columns:
        values = df["portfolio_value"]
    elif "ending_value" in df.columns:
        values = df["ending_value"]
    else:
        raise ValueError("DataFrame must have 'portfolio_value' or 'ending_value' column")

    # Calculate drawdown
    cummax = values.expanding().max()
    drawdown = (values - cummax) / cummax
    max_drawdown = drawdown.min()

    # Create figure
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdown * 100,
            mode="lines",
            name="Drawdown",
            line={"color": colors["negative"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(211, 47, 47, 0.2)",
            hovertemplate="Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>",
        )
    )

    # Add max drawdown line
    fig.add_hline(
        y=max_drawdown * 100,
        line_dash="dash",
        line_color=colors["text"],
        annotation_text=f"Max Drawdown: {max_drawdown * 100:.2f}%",
        annotation_position="right",
    )

    # Update layout
    fig.update_layout(
        title=title,
        template="plotly_dark" if theme == "dark" else "plotly_white",
        hovermode="x unified",
        showlegend=False,
        height=400,
        plot_bgcolor=colors["background"],
        paper_bgcolor=colors["paper"],
        font={"color": colors["text"]},
    )

    fig.update_xaxes(title_text="Date", gridcolor=colors["grid"])
    fig.update_yaxes(title_text="Drawdown (%)", gridcolor=colors["grid"])

    return fig


def plot_returns_distribution(
    backtest_result: pd.DataFrame | pl.DataFrame,
    title: str = "Returns Distribution",
    theme: str = "light",
    bins: int = 50,
) -> go.Figure:
    """Plot distribution of returns with statistics.

    Args:
        backtest_result: DataFrame with 'returns' or can calculate from 'portfolio_value'
        title: Chart title
        theme: Color theme ('light' or 'dark')
        bins: Number of histogram bins

    Returns:
        Plotly Figure object

    Example:
        >>> fig = plot_returns_distribution(results)
        >>> fig.show()
    """
    df = _ensure_pandas(backtest_result)
    colors = _get_theme_colors(theme)

    # Get or calculate returns
    if "returns" in df.columns:
        returns = df["returns"].dropna()
    elif "portfolio_value" in df.columns:
        returns = df["portfolio_value"].pct_change().dropna()
    elif "ending_value" in df.columns:
        returns = df["ending_value"].pct_change().dropna()
    else:
        raise ValueError("DataFrame must have 'returns' or 'portfolio_value' column")

    # Calculate statistics
    mean_return = returns.mean()
    std_return = returns.std()
    skew = returns.skew() if len(returns) > 0 else 0
    kurtosis = returns.kurtosis() if len(returns) > 0 else 0

    # Create figure
    fig = go.Figure()

    # Add histogram
    fig.add_trace(
        go.Histogram(
            x=returns * 100,  # Convert to percentage
            nbinsx=bins,
            name="Returns",
            marker_color=colors["primary"],
            opacity=0.7,
            hovertemplate="Return: %{x:.2f}%<br>Count: %{y}<extra></extra>",
        )
    )

    # Add mean line
    fig.add_vline(
        x=mean_return * 100,
        line_dash="dash",
        line_color=colors["positive"],
        annotation_text=f"Mean: {mean_return * 100:.3f}%",
        annotation_position="top",
    )

    # Add statistics annotation
    stats_text = (
        f"<b>Statistics:</b><br>"
        f"Mean: {mean_return * 100:.3f}%<br>"
        f"Std Dev: {std_return * 100:.3f}%<br>"
        f"Skewness: {skew:.3f}<br>"
        f"Kurtosis: {kurtosis:.3f}"
    )

    fig.add_annotation(
        x=0.98,
        y=0.98,
        xref="paper",
        yref="paper",
        text=stats_text,
        showarrow=False,
        align="left",
        bgcolor=colors["paper"],
        bordercolor=colors["grid"],
        borderwidth=1,
        font={"size": 10, "color": colors["text"]},
    )

    # Update layout
    fig.update_layout(
        title=title,
        template="plotly_dark" if theme == "dark" else "plotly_white",
        hovermode="closest",
        showlegend=False,
        height=400,
        plot_bgcolor=colors["background"],
        paper_bgcolor=colors["paper"],
        font={"color": colors["text"]},
    )

    fig.update_xaxes(title_text="Returns (%)", gridcolor=colors["grid"])
    fig.update_yaxes(title_text="Frequency", gridcolor=colors["grid"])

    return fig


def plot_rolling_metrics(
    backtest_result: pd.DataFrame | pl.DataFrame,
    window: int = 30,
    title: str = "Rolling Performance Metrics",
    theme: str = "light",
) -> go.Figure:
    """Plot rolling Sharpe ratio and volatility.

    Args:
        backtest_result: DataFrame with returns data
        window: Rolling window size in days
        title: Chart title
        theme: Color theme ('light' or 'dark')

    Returns:
        Plotly Figure object

    Example:
        >>> fig = plot_rolling_metrics(results, window=60)
        >>> fig.show()
    """
    df = _ensure_pandas(backtest_result)
    colors = _get_theme_colors(theme)

    # Get dates
    if df.index.name in ["date", "period_close"] or isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    elif "date" in df.columns:
        dates = df["date"]
    elif "timestamp" in df.columns:
        dates = df["timestamp"]
    else:
        dates = df.index

    # Get or calculate returns
    if "returns" in df.columns:
        returns = df["returns"]
    elif "portfolio_value" in df.columns:
        returns = df["portfolio_value"].pct_change()
    elif "ending_value" in df.columns:
        returns = df["ending_value"].pct_change()
    else:
        raise ValueError("DataFrame must have 'returns' or 'portfolio_value' column")

    # Calculate rolling metrics (annualized)
    rolling_mean = returns.rolling(window=window).mean() * 252  # Annualized return
    rolling_std = returns.rolling(window=window).std() * (252**0.5)  # Annualized volatility
    rolling_sharpe = rolling_mean / rolling_std

    # Create subplots
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(f"Rolling Sharpe Ratio ({window}d)", f"Rolling Volatility ({window}d)"),
    )

    # Add Sharpe ratio
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=rolling_sharpe,
            mode="lines",
            name="Sharpe Ratio",
            line={"color": colors["primary"], "width": 2},
            hovertemplate="Date: %{x}<br>Sharpe: %{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Add zero line for Sharpe
    fig.add_hline(y=0, line_dash="dot", line_color=colors["text"], row=1, col=1)

    # Add volatility
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=rolling_std * 100,  # Convert to percentage
            mode="lines",
            name="Volatility",
            line={"color": colors["negative"], "width": 2},
            hovertemplate="Date: %{x}<br>Vol: %{y:.2f}%<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # Update layout
    fig.update_layout(
        title=title,
        template="plotly_dark" if theme == "dark" else "plotly_white",
        hovermode="x unified",
        showlegend=False,
        height=600,
        plot_bgcolor=colors["background"],
        paper_bgcolor=colors["paper"],
        font={"color": colors["text"]},
    )

    # Update axes
    fig.update_xaxes(title_text="Date", gridcolor=colors["grid"], row=2, col=1)
    fig.update_yaxes(title_text="Sharpe Ratio", gridcolor=colors["grid"], row=1, col=1)
    fig.update_yaxes(title_text="Annualized Volatility (%)", gridcolor=colors["grid"], row=2, col=1)

    return fig
