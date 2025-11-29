# Infrastructure and Deployment Integration

## Self-Hosted Deployment Strategy

**Philosophy:** RustyBT is a library for self-hosted deployment with no cloud dependencies. Users maintain full control over infrastructure, data, and execution.

### Deployment Modes

**1. Local Development (Jupyter Notebooks)**
- **Environment:** Laptop/desktop with Python 3.12+ virtual environment
- **Use Case:** Strategy development, backtesting, research
- **Setup:**
  ```bash
  python -m venv rustybt-env
  source rustybt-env/bin/activate
  pip install rustybt
  jupyter lab
  ```
- **Data Storage:** Local Parquet files in `~/.rustybt/data/`
- **Database:** SQLite in `~/.rustybt/assets.db`

**2. Live Trading Server (Single Strategy)**
- **Environment:** Dedicated Linux VPS or bare-metal server
- **Use Case:** Production live trading for single strategy
- **Recommended Specs:**
  - CPU: 4+ cores
  - RAM: 8GB+ (16GB for high-frequency strategies)
  - Disk: 100GB+ SSD (for data caching)
  - Network: Low latency to broker (co-location preferred for HFT)
- **Setup:**
  ```bash
  # Install as systemd service
  sudo systemctl enable rustybt-strategy1
  sudo systemctl start rustybt-strategy1
  ```
- **Monitoring:** Logs to `journalctl`, metrics to local Prometheus instance
- **Data Storage:** Local Parquet files, SQLite database
- **Backup:** Daily backup of `strategy_state` table to S3/local NAS

**3. Multi-Strategy Server (Portfolio)**
- **Environment:** Dedicated server running multiple strategies
- **Use Case:** Production multi-strategy portfolio
- **Recommended Specs:**
  - CPU: 16+ cores
  - RAM: 32GB+
  - Disk: 500GB+ SSD
  - Network: Low latency, high bandwidth
- **Setup:** Multiple RustyBT processes (one per strategy) with shared data cache
- **Monitoring:** Centralized logging via rsyslog, Grafana dashboards
- **Data Storage:** Shared Parquet cache, separate SQLite per strategy
- **Backup:** Hourly state snapshots, daily full backups

**4. Docker Containerized Deployment**
- **Environment:** Docker containers for reproducible deployments
- **Use Case:** Development/production parity, easy deployment
- **Dockerfile:**
  ```dockerfile
  FROM python:3.12-slim

  RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .
  RUN pip install --no-cache-dir .

  CMD ["python", "-m", "rustybt", "live", "--config", "/config/strategy.yaml"]
  ```
- **Docker Compose:**
  ```yaml
  version: '3.8'
  services:
    strategy1:
      build: .
      volumes:
        - ./config:/config
        - ./data:/data
        - ./logs:/logs
      environment:
        - RUSTYBT_DATA_DIR=/data
        - RUSTYBT_LOG_LEVEL=INFO
      restart: unless-stopped
  ```

**5. Kubernetes Deployment (Advanced)**
- **Environment:** Kubernetes cluster for high availability
- **Use Case:** Enterprise multi-strategy deployment
- **Features:**
  - Rolling updates without downtime
  - Auto-restart on crash
  - Resource limits and scaling
  - Centralized logging and monitoring

### Infrastructure Components

**Data Storage:**
- **Parquet Files:** Store historical OHLCV data
  - Location: `/data/bundles/<bundle_name>/`
  - Retention: Unlimited (compressed, ~10GB per year per 1000 assets)
  - Backup: Optional (can re-download from source)
- **SQLite Database:** Asset metadata, live positions, audit logs
  - Location: `/data/assets.db`, `/data/strategy_state.db`
  - Size: 10-100MB typical
  - Backup: Daily full backup, hourly state snapshots

**Logging:**
- **Structured Logs:** JSON format via `structlog`
- **Log Rotation:** 100MB per file, keep 30 days
- **Levels:**
  - INFO: Trade executions, strategy signals
  - WARNING: Failed API calls, reconciliation mismatches
  - ERROR: Order rejections, connection failures
  - DEBUG: Detailed calculations (disabled in production)
- **Storage:** `/logs/rustybt-<strategy>.log`

**Monitoring:**
- **Metrics:** Prometheus-compatible metrics endpoint (Epic 9)
  - Portfolio value, P&L, Sharpe ratio
  - Order fill rate, latency, error rate
  - Data cache hit rate
- **Alerts:** Alert on error rate spike, position mismatch, connectivity loss
- **Dashboards:** Grafana dashboards for live monitoring

**Security:**
- **Credential Storage:** Encrypted at rest using `cryptography` library
  - Encryption key: Environment variable or hardware security module
  - Broker API keys stored in `broker_connections` table (encrypted BLOB)
- **Network Security:**
  - TLS for all broker API calls
  - Firewall rules: Allow only necessary ports
  - VPN for remote server access
- **Access Control:**
  - Restrict file permissions: `chmod 600` for config files
  - Separate user account for RustyBT process
  - No root access required

**Backup Strategy:**
- **Critical Data:**
  - `strategy_state` table: Hourly snapshots
  - `order_audit_log` table: Daily backups
  - Configuration files: Version controlled in git
- **Data Recovery:**
  - Restore state from latest checkpoint
  - Re-download historical data if lost (cached data is reproducible)
- **Backup Locations:**
  - Local NAS
  - Cloud storage (S3, Backblaze) with encryption
  - Offsite backup for disaster recovery

### High Availability Setup

**Multi-Instance Deployment:**
- Primary instance: Active trading
- Secondary instance: Hot standby, monitors primary
- Failover: Secondary takes over if primary fails (requires manual intervention for safety)

**State Synchronization:**
- Primary writes state to shared storage (NFS or S3)
- Secondary reads state every minute
- Broker position reconciliation on failover

**Health Checks:**
- HTTP health endpoint: `/health` returns 200 if alive
- Heartbeat file: Updated every 30 seconds
- External monitor (e.g., UptimeRobot) pings health endpoint

### Performance Considerations

**Latency Optimization:**
- Co-location: Deploy server near broker data center
- Network: 10Gbps+ Ethernet, low-latency provider
- Disable swap: Ensure all data in RAM for predictable latency

**CPU Optimization:**
- Rust modules for hot paths (Epic 7)
- Parallel processing for optimization (Ray)
- CPU affinity: Pin processes to specific cores

**Memory Optimization:**
- Polars lazy evaluation: Process data without loading entirely into memory
- Parquet compression: 50-80% smaller than HDF5
- Cache eviction: LRU cache with configurable max size

**Disk I/O Optimization:**
- SSD for data storage
- Separate disk for logs (avoid I/O contention)
- Parquet partition pruning: Read only required date ranges

---
