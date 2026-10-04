"""Measure API response latency without recording request or response content."""

import argparse
import asyncio
import json
import os
import statistics
import time

import httpx


async def benchmark(
    base_url: str, token: str, patient_id: str, question: str, runs: int
) -> dict[str, float | int]:
    """Call one authorized history route repeatedly and return timing aggregates."""
    timings: list[float] = []
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"question": question, "admission_id": None}
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        for _ in range(runs):
            started = time.perf_counter()
            response = await client.post(
                f"/v1/patients/{patient_id}/history-query",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            timings.append((time.perf_counter() - started) * 1000)
    ordered = sorted(timings)
    percentile_index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return {
        "runs": runs,
        "mean_ms": round(statistics.fmean(timings), 2),
        "median_ms": round(statistics.median(timings), 2),
        "p95_ms": round(ordered[percentile_index], 2),
    }


def main() -> None:
    """Read the token from the environment so it never appears in shell history."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patient_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--question", default="Summarize the recorded history.")
    parser.add_argument("--runs", type=int, default=5, choices=range(1, 101))
    args = parser.parse_args()
    token = os.environ.get("DOC_AGENT_BENCHMARK_TOKEN", "")
    if not token:
        parser.error("Set DOC_AGENT_BENCHMARK_TOKEN in the process environment.")
    result = asyncio.run(
        benchmark(args.base_url, token, args.patient_id, args.question, args.runs)
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
