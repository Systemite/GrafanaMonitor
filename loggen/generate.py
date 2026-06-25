#!/usr/bin/env python3
"""Synthetic SystemWeaver TcpSubServer .dlq log generator (dev tool).

Appends realistic call-timing rows to rotating .dlq files so the Loki/Alloy/Grafana
stack has something live to ingest without a real SubServer running. Standalone and
dependency-free: run it straight on the host with `python loggen/generate.py`.

The columns and TimeSpan format (HH:MM:SS.fffffff) match the real TcpSubServer output
documented in README.md, so query-time parsing behaves identically.
"""

import argparse
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Default to the repo's ./data directory regardless of the current working directory,
# so `python loggen/generate.py` from anywhere drops files where Alloy tails them.
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data"

HEADER = (
    "ThreadId,SeqId,SessionId,BeforeTime,QueueWaitTime,LockWaitTimeSubServer,"
    "LockWaitTimeServer,ExecutionTime,TotalTime,ResultLength,CallId,User,AppName"
)


def timespan(seconds: float) -> str:
    """Format a duration in seconds as a .NET TimeSpan string: HH:MM:SS.fffffff."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    whole = int(s)
    frac = int(round((s - whole) * 10_000_000))
    # Carry if rounding pushed the fraction to a full second.
    if frac == 10_000_000:
        frac = 0
        whole += 1
    return f"{int(h):02d}:{int(m):02d}:{whole:02d}.{frac:07d}"


def before_time() -> str:
    """Current UTC instant as ISO8601 with a 7-digit fraction and trailing Z."""
    now = datetime.now(timezone.utc)
    frac7 = f"{now.microsecond:06d}0"  # microseconds -> 7 digits (100ns ticks)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + frac7 + "Z"


def make_row(seq: int, spike_every: int, spike_secs: float) -> str:
    """Build one CSV call record. Every spike_every-th row is a slow call."""
    queue = random.uniform(0, 0.02)
    lock_sub = random.uniform(0, 0.0001)
    lock_srv = random.uniform(0, 0.005)
    if spike_every > 0 and seq % spike_every == 0:
        execution = spike_secs + random.uniform(0, 3)
    else:
        execution = random.uniform(0, 0.5)
    total = queue + lock_sub + lock_srv + execution

    return ",".join(
        [
            str(random.randint(60, 99)),     # ThreadId
            str(seq),                         # SeqId
            str(random.randint(1, 9)),        # SessionId
            before_time(),                    # BeforeTime
            timespan(queue),                  # QueueWaitTime
            timespan(lock_sub),               # LockWaitTimeSubServer
            timespan(lock_srv),               # LockWaitTimeServer
            timespan(execution),              # ExecutionTime
            timespan(total),                  # TotalTime
            str(random.randint(1, 50)),       # ResultLength
            str(random.randint(0, 20)),       # CallId
            "x0",                             # User
            "MyExampleApp",                   # AppName
        ]
    )


def new_file(out_dir: Path) -> Path:
    """Create a fresh rotation file with the header, named like the real server."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    path = out_dir / f"Systemite.SystemWeaver.TcpSubServer_{stamp}.dlq"
    path.write_text(HEADER + "\n", encoding="utf-8")
    return path


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    total_to_write = 1 if args.once else args.count  # None means run forever
    print(
        f"loggen: writing to {out_dir} every {args.interval}s "
        f"({'one row' if args.once else (str(total_to_write) + ' rows') if total_to_write else 'forever'})"
        ", Ctrl-C to stop",
        flush=True,
    )

    path = new_file(out_dir)
    rows_in_file = 0
    seq = 1
    written = 0

    while total_to_write is None or written < total_to_write:
        if rows_in_file >= args.rows_per_file:
            path = new_file(out_dir)
            rows_in_file = 0

        row = make_row(seq, args.spike_every, args.spike_secs)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(row + "\n")
            fh.flush()

        seq += 1
        rows_in_file += 1
        written += 1

        if total_to_write is not None and written >= total_to_write:
            break
        time.sleep(args.interval)

    print(f"loggen: wrote {written} row(s) to {out_dir}", flush=True)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dir", default=str(DEFAULT_DIR),
                   help="output directory for .dlq files (default: repo ./data)")
    p.add_argument("--interval", type=float, default=2.0,
                   help="seconds between rows (default: 2)")
    p.add_argument("--rows-per-file", type=int, default=60,
                   help="rotate to a new file after this many rows (default: 60)")
    p.add_argument("--spike-every", type=int, default=15,
                   help="every Nth row is a slow-call spike; 0 disables (default: 15)")
    p.add_argument("--spike-secs", type=float, default=12.0,
                   help="ExecutionTime floor for a spike, seconds (default: 12)")
    p.add_argument("--count", type=int, default=None,
                   help="write N rows then exit (default: run forever)")
    p.add_argument("--once", action="store_true",
                   help="write a single row and exit (smoke test)")
    return p.parse_args(argv)


if __name__ == "__main__":
    try:
        run(parse_args())
    except KeyboardInterrupt:
        print("\nloggen: stopped", flush=True)
        sys.exit(0)
