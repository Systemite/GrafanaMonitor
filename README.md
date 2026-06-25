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

- **Alloy** tails every `*.dlq` in the log directory and picks up each new
  rotation file as it appears.
- **Loki** stores the raw rows (no high-cardinality labels).
- **Grafana** runs a query-time alert that extracts a timing column and fires
  when it exceeds the configured threshold.

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

1. Point the log volume in `docker-compose.yml` at your `.dlq` directory.
2. `docker compose up -d`
3. Open Grafana at `http://localhost:3000` (Loki datasource pre-provisioned) and
   add the alert rule on the timing column you care about.
