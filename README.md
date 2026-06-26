# SystemWeaver SubServer DLQ Monitor

Tail SystemWeaver `TcpSubServer` `.dlq` call logs, ship them to Loki with Grafana
Alloy, and alert in Grafana when a call's timing crosses a threshold — surfacing
slow or lock-blocked SubServer calls as they happen.

## Why

The `TcpSubServer` writes one timing record per call to rotating `.dlq` files,
each timestamped in its filename
(e.g. `Systemite.SystemWeaver.TcpSubServer_2026-05-14_000356.dlq`). On their own
these files just pile up; this stack turns them into a live, queryable signal so a
spike in lock wait or total time triggers an alert instead of being discovered
after the fact.

- **Alloy** runs as a native Windows service on the monitored host. It tails
  every `*.dlq` in the log directory (picking up each new rotation file) **and**
  reads true Windows host metrics — CPU, RAM, disk, page file — via its built-in
  `prometheus.exporter.windows`.
- **Loki** stores the raw log rows (no high-cardinality labels).
- **Prometheus** stores the host metrics (pushed in by Alloy via remote_write).
- **Grafana** runs a query-time alert that extracts a timing column and fires
  when it exceeds the configured threshold, and serves two dashboards:
  **SubServer DLQ Live** (logs) and **System Metrics (Windows Host)**
  (disk/CPU/RAM/swap).

## Architecture

Loki, Prometheus, and Grafana run in Docker (`docker compose`). Alloy runs
**natively on Windows** so it can see the real host's files and performance
counters — a containerized Alloy would only see the Linux VM. Native Alloy reaches
the Dockerized services over published `localhost` ports (`:3100` Loki,
`:9090` Prometheus).

```
Native Alloy ──logs──▶ Loki (:3100) ─┐
            └─metrics─▶ Prometheus (:9090) ─┴─▶ Grafana (:3000)
```

> **Disk watch:** Loki's `loki-data` volume can fill the disk before its 31-day
> retention reclaims anything. The **System Metrics** dashboard's "Disk free"
> panels are the early warning for that — watch the lowest volume.

## Log format

CSV with a header row, one call per line:

```
ThreadId,SeqId,SessionId,BeforeTime,QueueWaitTime,LockWaitTimeSubServer,LockWaitTimeServer,ExecutionTime,TotalTime,ResultLength,CallId,User,AppName
```

The columns to alert on are the timings: `QueueWaitTime`, `LockWaitTimeSubServer`,
`LockWaitTimeServer`, `ExecutionTime`, `TotalTime`. They are .NET `TimeSpan`
values in `HH:MM:SS.fffffff` format and must be converted to seconds before
numeric comparison — a plain LogQL `unwrap` will not parse them.

## Quick start

1. **Start the backends:** `docker compose up -d` — brings up Loki, Prometheus,
   and Grafana (datasources + dashboards pre-provisioned).
2. **Install Alloy natively on Windows**:
   - Install Grafana Alloy via its Windows installer; it registers as a Windows
     service and reads `config.alloy` (default
     `C:\Program Files\GrafanaLabs\Alloy\config.alloy` — point it at the
     `alloy/config.alloy` in this repo, or copy the file there).
   - Edit `__path__` in `alloy/config.alloy` to your real `.dlq` directory.
   - Start/restart the **Alloy** Windows service.
3. **Verify:**
   - Alloy UI `http://localhost:12345` — both the DLQ source and the windows
     exporter components show healthy.
   - Prometheus `http://localhost:9090` — query `windows_cpu_time_total` or
     `windows_logical_disk_free_bytes` and confirm data arrives.
   - Grafana `http://localhost:3000` — open **System Metrics (Windows Host)** and
     **SubServer DLQ Live**.
4. Add the alert rule on the timing column you care about.

Ports: Grafana `3000`, Loki `3100`, Prometheus `9090`, Alloy UI `12345`.
