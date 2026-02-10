"""Cross-strategy comparison report from Garak's JSONL output.

Reads the .report.jsonl file and produces a table comparing
Attack Success Rate (ASR) across prompt strategies for each
probe/detector combination.
"""

import json
from collections import defaultdict
from pathlib import Path


def _parse_report(report_path: str) -> list[dict]:
    """Parse eval entries from a Garak report JSONL file."""
    eval_entries = []
    with open(report_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("entry_type") == "eval":
                eval_entries.append(entry)
    return eval_entries


def _infer_strategy(probe_name: str, eval_entries: list[dict]) -> str:
    """Try to infer strategy from surrounding context in the report.

    Since Garak doesn't natively track our strategy concept, we rely
    on the generator name that gets logged. As a fallback, we return
    the probe name itself.
    """
    return probe_name


def generate_report(report_path: str):
    """Generate and print a cross-strategy comparison table.

    The report groups results by (probe, detector) and shows ASR
    for each strategy. Strategy is identified by the generator name
    recorded in attempt entries.
    """
    eval_entries = _parse_report(report_path)

    if not eval_entries:
        print("No evaluation entries found in report.")
        return

    # Also parse attempt entries to map probe runs to strategies
    # by looking at the generator info in start_run
    attempt_entries = []
    with open(report_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("entry_type") == "attempt":
                attempt_entries.append(entry)

    # Group eval entries - they appear in order (strategy by strategy)
    # We need to figure out which eval entries belong to which strategy.
    # Since we run strategies sequentially and each produces eval entries,
    # we can detect strategy boundaries by tracking probe repetition.
    seen_probes = set()
    strategy_idx = 0
    strategy_labels = []
    entry_strategies = []

    for entry in eval_entries:
        probe = entry["probe"]
        key = (probe, entry["detector"])
        if key in seen_probes:
            # Same probe+detector seen again = new strategy
            strategy_idx += 1
            seen_probes.clear()
        seen_probes.add(key)
        entry_strategies.append(strategy_idx)

    # Build results table: (probe, detector) -> {strategy_idx: {passes, fails, total}}
    results = defaultdict(dict)
    for i, entry in enumerate(eval_entries):
        probe = entry["probe"]
        detector = entry["detector"]
        s_idx = entry_strategies[i]
        total = entry.get("total_evaluated", 0)
        fails = entry.get("fails", 0)
        passes = entry.get("passed", 0)
        results[(probe, detector)][s_idx] = {
            "passes": passes,
            "fails": fails,
            "total": total,
        }

    # Determine strategy names from count of unique strategy indices
    num_strategies = strategy_idx + 1

    # Print report
    print()
    print("=" * 100)
    print("  PROMPT INJECTION TEST RESULTS - Cross-Strategy Comparison")
    print("=" * 100)
    print()

    # Header
    header = f"{'Strategy':>10} | {'Probe':<40} | {'Detector':<30} | {'ASR':>7} | {'Hits/Total':>10}"
    print(header)
    print("-" * len(header))

    strategy_names = [f"strat_{i}" for i in range(num_strategies)]

    for (probe, detector), strat_data in sorted(results.items()):
        for s_idx in sorted(strat_data.keys()):
            d = strat_data[s_idx]
            total = d["total"]
            fails = d["fails"]
            asr = (fails / total * 100) if total > 0 else 0.0

            # Shorten names for display
            probe_short = probe.split(".")[-1] if "." in probe else probe
            det_short = detector.split(".")[-1] if "." in detector else detector

            print(
                f"{strategy_names[s_idx]:>10} | "
                f"{probe_short:<40} | "
                f"{det_short:<30} | "
                f"{asr:6.1f}% | "
                f"{fails:>4}/{total:<4}"
            )
        print("-" * len(header))

    # Summary by strategy
    print()
    print("SUMMARY BY STRATEGY")
    print("-" * 60)
    for s_idx in range(num_strategies):
        total_attempts = 0
        total_fails = 0
        for strat_data in results.values():
            if s_idx in strat_data:
                total_attempts += strat_data[s_idx]["total"]
                total_fails += strat_data[s_idx]["fails"]
        overall_asr = (total_fails / total_attempts * 100) if total_attempts > 0 else 0.0
        print(
            f"  {strategy_names[s_idx]:>10}: "
            f"Overall ASR = {overall_asr:.1f}% "
            f"({total_fails}/{total_attempts})"
        )

    print()
    print(f"Full report: {report_path}")
    print()
