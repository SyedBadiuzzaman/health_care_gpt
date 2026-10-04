"""Evaluate deterministic medical-direction filters without sending clinical data."""

import json
from pathlib import Path

from doc_agent_core.guardrails import (
    deterministic_input_allowed,
    deterministic_output_allowed,
)


def run(project: Path | None = None) -> dict[str, int | float]:
    """Run the labeled adversarial cases and save aggregate, non-sensitive results."""
    root = (project or Path.cwd()).resolve()
    dataset = json.loads(
        (root / "evals/datasets/adversarial_safety.json").read_text(encoding="utf-8")
    )
    inputs = dataset["blocked_inputs"]
    outputs = dataset["blocked_outputs"]
    missed_inputs = sum(deterministic_input_allowed(item) for item in inputs)
    missed_outputs = sum(deterministic_output_allowed(item) for item in outputs)
    total = len(inputs) + len(outputs)
    result: dict[str, int | float] = {
        "case_count": total,
        "missed_input_blocks": missed_inputs,
        "missed_output_blocks": missed_outputs,
        "directive_output_rate": missed_outputs / len(outputs) if outputs else 0.0,
    }
    report_path = root / "evals/reports/safety_evaluation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    """Print aggregate results and fail when a labeled directive escapes."""
    result = run()
    print(json.dumps(result, sort_keys=True))
    if result["missed_input_blocks"] or result["missed_output_blocks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
