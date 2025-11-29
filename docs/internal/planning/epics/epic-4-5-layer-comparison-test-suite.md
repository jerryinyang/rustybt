# Epic 4: 5-Layer Comparison Test Suite

**Goal:** Implement comprehensive comparison logic for all 5 validation layers with configurable tolerances.

**Architecture References:**
- Log-Based Validation Architecture (Architecture pg 149-248)
- Tolerance Configuration (Architecture pg 243)
- Comparison Engine (Architecture pg 195-204)

**Value:** Automated detection of discrepancies at each layer with precise diagnostics.

**FRs Covered:** FR1-FR22 (Test Suite Development - 22 FRs)

---

## Story 4.1: Implement Log Parser with Parquet Caching

As a developer,
I want efficient log parsing with caching,
So that comparison operations run quickly on large log files.

**Acceptance Criteria:**

**Given** the `rustybt/validation/log_parser.py` module
**When** the log parser is implemented
**Then** it provides:

**parse_log() function:**
```python
def parse_log(log_path: Path, use_cache: bool = True) -> pl.DataFrame:
    """Parse JSONL log file to Polars DataFrame with optional caching."""
    cache_path = log_path.with_suffix('.parquet')

    # Check cache validity
    if use_cache and cache_path.exists():
        if cache_path.stat().st_mtime > log_path.stat().st_mtime:
            return pl.read_parquet(cache_path)

    # Parse JSONL
    records = []
    with open(log_path, 'r') as f:
        for line in f:
            records.append(json.loads(line))

    df = pl.DataFrame(records)

    # Flatten nested 'data' column
    df = flatten_data_column(df)

    # Cache to Parquet
    if use_cache:
        df.write_parquet(cache_path)

    return df
```

**And** cache invalidation works correctly:
- Cache regenerated if JSONL newer than Parquet
- Cache skipped if use_cache=False
- Cache path is predictable (.jsonl → .parquet)

**And** flatten_data_column() expands nested data:
```python
# Before: {"timestamp": "...", "layer": "data", "data": {"close": 100.5, "volume": 1000}}
# After: columns: timestamp, layer, data_close, data_volume
```

**And** performance: Parse 100MB JSONL in <5 seconds

**And** unit tests verify:
- Basic parsing
- Cache creation and invalidation
- Nested data flattening

**Prerequisites:** Story 2.6 (schema validation)

**Technical Notes:**
- Use Polars for DataFrame operations
- Stream JSONL parsing for memory efficiency
- Prefix flattened columns with "data_" for clarity
- Handle missing fields gracefully (null values)

---

## Story 4.2: Implement Tolerance Configuration System

As a developer,
I want configurable tolerances per layer,
So that comparison accounts for acceptable differences.

**Acceptance Criteria:**

**Given** tolerance configuration needs
**When** the tolerance system is implemented
**Then** YAML configuration files exist:

**tests/validation/config/layer_1_tolerances.yaml:**
```yaml
layer_1_data:
  timestamp_window_ms: 1  # 1ms tolerance for timestamp alignment
  price_decimal_places: 4  # Compare prices to 4 decimal places
  volume_tolerance_pct: 0.001  # 0.1% volume tolerance
  bar_count_tolerance: 0  # Exact bar count match required
```

**tests/validation/config/layer_2_tolerances.yaml:**
```yaml
layer_2_signals:
  indicator_decimal_places: 6  # Compare indicators to 6 decimal places
  signal_timing_tolerance_bars: 0  # Signals must match same bar
  signal_count_tolerance: 0  # Exact signal count required
```

**And similar for layers 3, 4, 5**

**And** tolerance loading:
```python
def load_tolerances(layer: str) -> dict:
    """Load tolerance configuration for specified layer."""
    config_path = Path(f"tests/validation/config/{layer}_tolerances.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)
```

**And** tolerance override in tests:
```python
@pytest.mark.layer_1_data
def test_data_handling(tolerances):
    # Override specific tolerance
    tolerances["price_decimal_places"] = 2

    discrepancies = compare_layer("data", rustybt_logs, backtrader_logs, tolerances)
```

**And** CLI shows active tolerances:
```bash
rustybt-validate config show layer_1_data
# layer_1_data tolerances:
#   timestamp_window_ms: 1
#   price_decimal_places: 4
#   ...
```

**Prerequisites:** Story 1.2 (PyYAML dependency)

**Technical Notes:**
- Reference Architecture Tolerance Configuration (pg 243)
- Use pytest fixtures to inject tolerances
- Document each tolerance meaning in config file comments
- Default tolerances should be conservative (strict)

---

## Story 4.3: Implement Layer 1 Data Handling Comparator

As a developer,
I want Layer 1 comparison for data handling,
So that lookahead bias and bar alignment issues are detected.

**Acceptance Criteria:**

**Given** the `rustybt/validation/comparators.py` module
**When** Layer1DataComparator is implemented
**Then** it detects:

**Lookahead bias detection:**
```python
def detect_lookahead_bias(logs: pl.DataFrame) -> list[Discrepancy]:
    """Detect if strategy accessed future data."""
    discrepancies = []

    # Check that data access timestamps <= current bar timestamp
    data_events = logs.filter(pl.col("layer") == "data")

    for row in data_events.iter_rows(named=True):
        accessed_time = row.get("data_accessed_timestamp")
        current_bar = row.get("data_current_bar_timestamp")

        if accessed_time and current_bar:
            if accessed_time > current_bar:
                discrepancies.append(Discrepancy(
                    layer="data",
                    event="lookahead_bias",
                    timestamp=current_bar,
                    field="data_access",
                    rustybt_value=accessed_time,
                    backtrader_value=current_bar,
                    tolerance="none",
                    exceeded_by=f"{accessed_time - current_bar} ahead"
                ))

    return discrepancies
```

**Bar alignment comparison:**
```python
def compare_bar_alignment(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare bar timestamps and OHLCV values."""
    discrepancies = []

    rb_bars = rustybt_logs.filter(pl.col("event") == "bar_received")
    bt_bars = backtrader_logs.filter(pl.col("event") == "bar_received")

    # Compare bar counts
    if len(rb_bars) != len(bt_bars):
        discrepancies.append(Discrepancy(
            layer="data",
            event="bar_count_mismatch",
            timestamp=None,
            field="bar_count",
            rustybt_value=len(rb_bars),
            backtrader_value=len(bt_bars),
            tolerance=tolerances.get("bar_count_tolerance", 0),
            exceeded_by=abs(len(rb_bars) - len(bt_bars))
        ))

    # Compare individual bars
    # ... timestamp alignment, OHLCV value comparison ...

    return discrepancies
```

**And** pytest test function:
```python
@pytest.mark.layer_1_data
def test_layer_1_data_handling(sma_crossover_logs, layer_1_tolerances):
    """Validate data handling layer for SMA crossover strategy."""
    comparator = Layer1DataComparator(layer_1_tolerances)
    discrepancies = comparator.compare(
        sma_crossover_logs["rustybt"],
        sma_crossover_logs["backtrader"]
    )

    # Filter known DESIGN differences
    unexpected = [d for d in discrepancies if not is_known_design(d)]

    assert len(unexpected) == 0, format_discrepancies(unexpected)
```

**And** test file exists: `tests/validation/test_layer_1_data.py`

**Prerequisites:** Story 4.1 (log parser), Story 4.2 (tolerances)

**Technical Notes:**
- Reference Architecture Layer 1 specification
- Lookahead bias is CRITICAL - zero tolerance
- Bar alignment uses timestamp_window_ms tolerance
- OHLCV comparison uses price_decimal_places tolerance

---

## Story 4.4: Implement Layer 2 Signal Computation Comparator

As a developer,
I want Layer 2 comparison for signal computation,
So that indicator calculation and signal timing differences are detected.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer2SignalsComparator is implemented
**Then** it compares:

**Indicator value comparison:**
```python
def compare_indicators(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare indicator calculations."""
    discrepancies = []
    decimal_places = tolerances.get("indicator_decimal_places", 6)

    rb_signals = rustybt_logs.filter(pl.col("layer") == "signals")
    bt_signals = backtrader_logs.filter(pl.col("layer") == "signals")

    # Join on timestamp and signal name
    joined = rb_signals.join(bt_signals, on=["timestamp", "data_signal_name"], suffix="_bt")

    for row in joined.iter_rows(named=True):
        rb_value = row["data_signal_value"]
        bt_value = row["data_signal_value_bt"]

        if not values_match(rb_value, bt_value, decimal_places):
            discrepancies.append(Discrepancy(
                layer="signals",
                event="indicator_mismatch",
                timestamp=row["timestamp"],
                field=row["data_signal_name"],
                rustybt_value=rb_value,
                backtrader_value=bt_value,
                tolerance=f"{decimal_places} decimal places",
                exceeded_by=abs(rb_value - bt_value)
            ))

    return discrepancies
```

**Signal timing comparison:**
```python
def compare_signal_timing(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare when signals fire."""
    # Extract buy/sell signals
    # Compare signal bar numbers
    # Detect timing differences
```

**Signal count comparison:**
```python
def compare_signal_counts(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare total signal counts."""
    # Count signals by type (buy, sell, etc.)
    # Compare counts with tolerance
```

**And** pytest marker: `@pytest.mark.layer_2_signals`

**And** test file exists: `tests/validation/test_layer_2_signals.py`

**Prerequisites:** Story 4.3 (Layer 1 comparator pattern)

**Technical Notes:**
- Some indicator differences are DESIGN (e.g., RSI smoothing method)
- Document known DESIGN differences in config
- Signal timing uses bar index, not timestamp

---

## Story 4.5: Implement Layer 3 Order Lifecycle Comparator

As a developer,
I want Layer 3 comparison for order lifecycle,
So that order creation, execution, and state transition differences are detected.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer3OrdersComparator is implemented
**Then** it compares:

**Order creation comparison:**
```python
def compare_order_creation(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare order creation events."""
    discrepancies = []

    rb_orders = rustybt_logs.filter(pl.col("event") == "order_created")
    bt_orders = backtrader_logs.filter(pl.col("event") == "order_created")

    # Compare order counts
    # Compare order types (market, limit, stop)
    # Compare order quantities
    # Compare order timing (which bar)

    return discrepancies
```

**Order execution comparison:**
```python
def compare_order_execution(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare order fill events."""
    # Compare fill prices
    # Compare fill quantities
    # Compare fill timing
```

**Order state transition comparison:**
```python
def compare_order_states(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare order state transitions."""
    # CREATED → SUBMITTED → FILLED sequence
    # CREATED → CANCELLED handling
    # Partial fill handling
```

**And** pytest marker: `@pytest.mark.layer_3_orders`

**And** test file exists: `tests/validation/test_layer_3_orders.py`

**Prerequisites:** Story 4.4 (Layer 2 pattern)

**Technical Notes:**
- Order IDs may differ - match by timestamp + asset + quantity
- Fill prices may differ due to slippage model differences (DESIGN)
- State transitions should match exactly

---

## Story 4.6: Implement Layer 4 Broker Transaction Comparator

As a developer,
I want Layer 4 comparison for broker transactions,
So that commission, slippage, position, and cash differences are detected.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer4BrokerComparator is implemented
**Then** it compares:

**Commission comparison:**
```python
def compare_commissions(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare commission calculations."""
    # Extract transaction events with commissions
    # Compare commission per trade
    # Compare total commissions
```

**Slippage comparison:**
```python
def compare_slippage(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare slippage modeling."""
    # Compare expected price vs fill price
    # Compare slippage amounts
```

**Position tracking comparison:**
```python
def compare_positions(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare position tracking."""
    # Compare position sizes at each bar
    # Compare long/short positions
    # Compare position value
```

**Cash ledger comparison:**
```python
def compare_cash(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare cash ledger."""
    # Compare cash balance at each bar
    # Compare debits/credits per transaction
```

**And** pytest marker: `@pytest.mark.layer_4_broker`

**And** test file exists: `tests/validation/test_layer_4_broker.py`

**Prerequisites:** Story 4.5 (Layer 3 pattern)

**Technical Notes:**
- Commission models may differ (DESIGN) - document differences
- Slippage models may differ (DESIGN)
- Cash and position tracking should match closely

---

## Story 4.7: Implement Layer 5 Portfolio Returns Comparator

As a developer,
I want Layer 5 comparison for portfolio returns,
So that return calculations and portfolio valuations are validated.

**Acceptance Criteria:**

**Given** the comparators module
**When** Layer5PortfolioComparator is implemented
**Then** it compares:

**Return calculation comparison:**
```python
def compare_returns(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare return calculations."""
    # Compare daily returns
    # Compare cumulative returns
    # Compare annualized returns
```

**Portfolio valuation comparison:**
```python
def compare_portfolio_value(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare portfolio valuations."""
    # Compare portfolio value at each bar
    # Compare starting value
    # Compare final value
```

**Performance metrics comparison:**
```python
def compare_metrics(
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame,
    tolerances: dict
) -> list[Discrepancy]:
    """Compare performance metrics."""
    # Compare Sharpe ratio
    # Compare max drawdown
    # Compare volatility
```

**And** pytest marker: `@pytest.mark.layer_5_portfolio`

**And** test file exists: `tests/validation/test_layer_5_portfolio.py`

**Prerequisites:** Story 4.6 (Layer 4 pattern)

**Technical Notes:**
- Return calculations may use different conventions (DESIGN)
- Portfolio value is most important metric for validation
- Performance metrics may differ due to calculation methods

---

## Story 4.8: Implement Master Comparison Orchestrator

As a developer,
I want a master orchestrator that runs all layer comparisons,
So that full validation can be performed with a single command.

**Acceptance Criteria:**

**Given** all layer comparators
**When** master orchestrator is implemented
**Then** it provides:

**run_all_comparisons() function:**
```python
def run_all_comparisons(
    session: Session,
    rustybt_logs: pl.DataFrame,
    backtrader_logs: pl.DataFrame
) -> ComparisonResult:
    """Run all 5 layer comparisons."""
    all_discrepancies = []
    layer_results = {}

    comparators = [
        ("data", Layer1DataComparator),
        ("signals", Layer2SignalsComparator),
        ("orders", Layer3OrdersComparator),
        ("broker", Layer4BrokerComparator),
        ("portfolio", Layer5PortfolioComparator),
    ]

    for layer_name, comparator_class in comparators:
        tolerances = load_tolerances(f"layer_{layer_name}")
        comparator = comparator_class(tolerances)

        discrepancies = comparator.compare(rustybt_logs, backtrader_logs)

        all_discrepancies.extend(discrepancies)
        layer_results[layer_name] = LayerResult(
            layer=layer_name,
            discrepancy_count=len(discrepancies),
            passed=len([d for d in discrepancies if not is_known_design(d)]) == 0
        )

        session.layers_completed.append(layer_name)
        SessionManager.save(session)

    return ComparisonResult(
        total_discrepancies=len(all_discrepancies),
        layer_results=layer_results,
        discrepancies=all_discrepancies
    )
```

**And** CLI command:
```bash
rustybt-validate compare <session_id>
# Running 5-layer comparison...
# Layer 1 (Data):      ✓ Passed (0 discrepancies)
# Layer 2 (Signals):   ✓ Passed (2 DESIGN, 0 unexpected)
# Layer 3 (Orders):    ✗ Failed (3 discrepancies)
# Layer 4 (Broker):    ✓ Passed (1 DESIGN, 0 unexpected)
# Layer 5 (Portfolio): ✓ Passed (0 discrepancies)
#
# Total: 6 discrepancies (3 DESIGN, 3 require investigation)
```

**And** selective layer comparison:
```bash
rustybt-validate compare <session_id> --layer data
rustybt-validate compare <session_id> --layer signals,orders
```

**And** comparison results saved to session

**Prerequisites:** Stories 4.3-4.7 (all layer comparators)

**Technical Notes:**
- Run layers sequentially for determinism
- Save progress after each layer (resumability)
- Pass/fail based on unexpected discrepancies (not DESIGN)
- Support partial comparison for debugging

---
