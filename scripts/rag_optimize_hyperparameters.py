#!/usr/bin/env python3
"""Grid-search RAG retrieval hyperparameters against deterministic benchmark scenarios."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp_server.application.agents.rag_validation.fixture import (
    OPTIMIZATION_REPORT_PATH,
    OPTIMIZED_HYPERPARAMETERS_PATH,
    save_optimized_hyperparameters,
)
from mcp_server.application.agents.rag_validation.optimization_report import (
    build_report_from_optimization,
    default_baseline_hyperparameters,
    save_optimization_report,
)
from mcp_server.application.agents.rag_validation.optimizer import (
    RagHyperparameterOptimizer,
    default_rag_hyperparameter_search_space,
)
from mcp_server.application.agents.rag_validation.scenarios import load_search_scenarios
from mcp_server.application.agents.rag_validation.test_dataset_loader import (
    DEFAULT_MAX_SCENARIOS,
    TestDatasetNotFoundError,
    load_test_dataset_scenarios,
)
from mcp_server.domain.rag_hyperparameters import RagHyperparameterSearchSpace
from mcp_server.main import bootstrap_application_runtime, bootstrap_environment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Grid-search RAG retrieval hyperparameters using deterministic phrase benchmarks."
        ),
    )
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=None,
        help="Path to search_scenarios.json (default: bundled fixture)",
    )
    parser.add_argument(
        "--test-dataset",
        action="store_true",
        help="Load scenarios from bundled test-dataset/ CSV files",
    )
    parser.add_argument(
        "--max-scenarios",
        type=int,
        default=DEFAULT_MAX_SCENARIOS,
        help="Cap scenarios when using --test-dataset (default: 12)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OPTIMIZED_HYPERPARAMETERS_PATH,
        help="Path for optimized_hyperparameters.json output",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=None,
        help=(
            "Path for optimization_report.json (default: alongside --output, "
            "or fixtures/rag_validation/optimization_report.json)"
        ),
    )
    parser.add_argument(
        "--max-combinations",
        type=int,
        default=None,
        help="Cap the number of hyperparameter combinations evaluated",
    )
    parser.add_argument(
        "--search-space",
        type=Path,
        default=None,
        help="Optional JSON file overriding the default retrieval search space",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned combinations without running the validation graph",
    )
    return parser.parse_args()


def _default_search_space() -> RagHyperparameterSearchSpace:
    return default_rag_hyperparameter_search_space()


def _load_search_space(path: Path | None) -> RagHyperparameterSearchSpace:
    if path is None:
        return _default_search_space()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Search space file must contain a JSON object: {path}"
        raise ValueError(msg)
    return RagHyperparameterSearchSpace.from_dict(payload)


def _resolve_report_output(args: argparse.Namespace) -> Path:
    if args.report_output is not None:
        return args.report_output
    if args.output == OPTIMIZED_HYPERPARAMETERS_PATH:
        return OPTIMIZATION_REPORT_PATH
    return args.output.parent / "optimization_report.json"


async def _run(args: argparse.Namespace) -> int:
    if args.test_dataset:
        scenarios = load_test_dataset_scenarios(max_scenarios=args.max_scenarios)
    else:
        scenarios = load_search_scenarios(args.scenarios)
    search_space = _load_search_space(args.search_space)
    optimizer = RagHyperparameterOptimizer(
        search_space=search_space,
        scenarios=scenarios,
    )
    combinations = optimizer.plan_combinations(max_combinations=args.max_combinations)

    if args.dry_run:
        print(f"Planned {len(combinations)} combination(s) across {len(scenarios)} scenario(s):")
        for index, combo in enumerate(combinations, start=1):
            print(f"{index}. {json.dumps(combo.as_dict(), sort_keys=True)}")
        return 0

    scenario_lookup = {scenario.name: scenario.query for scenario in scenarios}
    baseline = default_baseline_hyperparameters()
    before_score = await optimizer.evaluate_hyperparameters(baseline)
    result = await optimizer.optimize(max_combinations=args.max_combinations)
    after_score = await optimizer.evaluate_hyperparameters(result.hyperparameters)
    report = build_report_from_optimization(
        before_score=before_score,
        optimized=result,
        after_score=after_score,
        scenario_lookup=scenario_lookup,
    )
    output_path = save_optimized_hyperparameters(result, args.output)
    report_path = save_optimization_report(report, _resolve_report_output(args))
    print(
        f"Best score={result.best_score} "
        f"hyperparameters={json.dumps(result.hyperparameters.as_dict(), sort_keys=True)} "
        f"written to {output_path}\n"
        f"Before/after report written to {report_path}",
    )
    return 0


def main() -> None:
    bootstrap_environment()
    bootstrap_application_runtime()
    args = _parse_args()
    try:
        exit_code = asyncio.run(_run(args))
    except (OSError, ValueError, RuntimeError, TestDatasetNotFoundError) as exc:
        print(f"Optimization failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
