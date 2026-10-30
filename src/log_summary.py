"""Summarise the service's JSON request logs (item 16).

The API writes one JSON line per request (query, k, filter, latency_ms,
n_results, cache_hit). This reads a log file (or stdin), ignores non-JSON
lines, and prints the operational picture: request count, zero-result rate,
cache hit rate, latency p50/p99, and the 10 slowest distinct queries.

Usage:
    python src/log_summary.py /tmp/wands_api.log
    docker logs wands-api 2>&1 | python src/log_summary.py -
"""
import json
import statistics
import sys


def read_entries(stream):
    for line in stream:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "latency_ms" in entry and "query" in entry:
            yield entry


def quantile(values, q):
    values = sorted(values)
    return values[min(int(q * len(values)), len(values) - 1)]


def summarise(entries):
    entries = list(entries)
    if not entries:
        return "no request log lines found"
    lat = [e["latency_ms"] for e in entries]
    zero = sum(e["n_results"] == 0 for e in entries)
    hits = sum(bool(e.get("cache_hit")) for e in entries)
    slowest = {}
    for e in entries:
        q = e["query"]
        if e["latency_ms"] >= slowest.get(q, (0, None))[0]:
            slowest[q] = (e["latency_ms"], e["n_results"])
    top = sorted(slowest.items(), key=lambda kv: -kv[1][0])[:10]

    lines = [
        f"requests          {len(entries)}",
        f"zero-result rate  {zero / len(entries):.4f} ({zero} requests)",
        f"cache hit rate    {hits / len(entries):.4f}",
        f"latency p50       {quantile(lat, 0.50):.1f} ms",
        f"latency p99       {quantile(lat, 0.99):.1f} ms",
        f"latency mean      {statistics.mean(lat):.1f} ms",
        "slowest queries (worst case per query):",
    ]
    lines += [f"  {ms:8.1f} ms  n={n:<3} {q!r}" for q, (ms, n) in top]
    return "\n".join(lines)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "-"
    stream = sys.stdin if path == "-" else open(path)
    print(summarise(read_entries(stream)))


if __name__ == "__main__":
    main()
