"""Orchestrator for injection testing.

Runs all probes against the classifier for each prompt strategy,
using Garak's harness/evaluator infrastructure, then generates
a cross-strategy comparison report.
"""

import datetime
import logging
import sys
from pathlib import Path

from folder_organizer.config import ClassesDefinition, AppConfig

from injection_testing.config import InjectionTestConfig
from injection_testing.dataset import load_dataset_samples
from injection_testing.generator import ClassifierGenerator
from injection_testing.report import generate_report

# Probes
from injection_testing.probes.misclassification import (
    DirectMisclassification,
    ContextOverrideMisclassification,
    FewShotMisclassification,
    PayloadSandwichMisclassification,
)
from injection_testing.probes.prompt_leakage import SystemPromptExtraction
from injection_testing.probes.confidence_manipulation import (
    ConfidenceInflation,
    ConfidenceDeflation,
)
from injection_testing.probes.output_hijack import JSONFormatHijack, ReasoningHijack

# Detectors
from injection_testing.detectors.classification import (
    MisclassificationDetector,
    PromptLeakageDetector,
    ConfidenceManipulationDetector,
    OutputFormatDetector,
    ClassValidityDetector,
)


def _init_garak(config: InjectionTestConfig):
    """Initialize Garak's global configuration and start a run."""
    from garak import _config

    _config.load_base_config()

    # Set run parameters
    _config.run.generations = config.generations_per_prompt
    _config.system.verbose = 1
    _config.system.parallel_requests = 0
    _config.system.parallel_attempts = 0

    # Set reporting directory
    config.output_dir.mkdir(parents=True, exist_ok=True)
    _config.reporting.report_dir = str(config.output_dir)
    _config.reporting.report_prefix = ""

    # Set transient timing
    _config.transient.starttime = datetime.datetime.now()
    _config.transient.starttime_iso = _config.transient.starttime.isoformat()

    # Start run (creates report file, sets run_id)
    from garak import command
    # Provide a minimal cli_args object to avoid AttributeError in start_run
    _config.transient.cli_args = type("Args", (), {"list_probes": False, "list_detectors": False, "list_generators": False, "list_buffs": False, "list_config": False, "plugin_info": False})()
    _config.system.lite = False
    _config.system.show_z = False
    _config.plugins.target_type = "file-classifier"
    _config.plugins.target_name = "AIFileClassifier"
    _config.plugins.buffs_include_original_prompt = False
    _config.plugins.buff_max = None
    command.start_run()

    return _config.transient.report_filename


def _build_probe_detector_pairs(
    valid_classes: list[str], samples: dict[str, list[str]]
) -> list[tuple[object, list]]:
    """Build (probe, detectors) pairs matching each probe to its relevant detectors."""
    misclass_detectors = [
        MisclassificationDetector(),
        ClassValidityDetector(valid_classes),
    ]
    return [
        # Misclassification probes -> misclassification + class validity detectors
        (DirectMisclassification(valid_classes, samples), misclass_detectors),
        (ContextOverrideMisclassification(valid_classes, samples), misclass_detectors),
        (FewShotMisclassification(valid_classes, samples), misclass_detectors),
        (PayloadSandwichMisclassification(valid_classes, samples), misclass_detectors),
        # Prompt leakage probe -> prompt leakage detector
        (SystemPromptExtraction(valid_classes, samples), [PromptLeakageDetector()]),
        # Confidence manipulation probes -> confidence manipulation detector
        (ConfidenceInflation(valid_classes, samples), [ConfidenceManipulationDetector()]),
        (ConfidenceDeflation(valid_classes, samples), [ConfidenceManipulationDetector()]),
        # Output hijack probes -> output format + class validity detectors
        (JSONFormatHijack(valid_classes, samples), [
            OutputFormatDetector(),
            ClassValidityDetector(valid_classes),
        ]),
        (ReasoningHijack(valid_classes, samples), [
            OutputFormatDetector(),
            ClassValidityDetector(valid_classes),
        ]),
    ]


def run(config: InjectionTestConfig):
    """Main entry point: run injection tests across all strategies."""
    # Load class definitions and app config
    classes_def = ClassesDefinition.from_yaml(config.classes_yaml_path)
    app_config = AppConfig.from_yaml(config.app_config_yaml_path)
    valid_classes = classes_def.get_class_names()

    # Load dataset samples for probes
    print(f"Loading dataset samples from {config.dataset_name} ({config.dataset_split})...")
    samples = load_dataset_samples(
        dataset_name=config.dataset_name,
        split=config.dataset_split,
        samples_per_class=config.samples_per_class,
    )
    print(f"Loaded samples per class: {{{', '.join(f'{k}: {len(v)}' for k, v in samples.items())}}}")

    print(f"Loaded {len(valid_classes)} classes: {valid_classes}")
    print(f"Strategies to test: {config.strategies}")
    print(f"Probe set: {config.probe_set}")
    print()

    # Initialize Garak
    report_filename = _init_garak(config)
    print(f"Report file: {report_filename}")
    print()

    from garak.harnesses.base import Harness
    from garak.evaluators.base import ThresholdEvaluator

    harness = Harness()
    evaluator = ThresholdEvaluator(threshold=0.5)

    for strategy in config.strategies:
        print(f"\n{'='*60}")
        print(f"  Testing strategy: {strategy}")
        print(f"{'='*60}\n")

        # Create generator for this strategy
        generator = ClassifierGenerator(
            classes_definition=classes_def,
            app_config=app_config,
            strategy_name=strategy,
        )

        # Build probe-detector pairs and run each with matched detectors
        if config.probe_set in ("custom", "all"):
            for probe, detectors in _build_probe_detector_pairs(valid_classes, samples):
                harness.run(generator, [probe], detectors, evaluator)

        if config.probe_set in ("builtin", "all"):
            from garak import _plugins
            builtin_probe_names = [
                "probes.promptinject.HijackHateHumansMini",
                "probes.promptinject.HijackKillHumansMini",
                "probes.promptinject.HijackLongPromptMini",
            ]
            # Builtin probes get all detectors since we don't know their intent
            all_detectors = [
                MisclassificationDetector(),
                PromptLeakageDetector(),
                ConfidenceManipulationDetector(),
                OutputFormatDetector(),
                ClassValidityDetector(valid_classes),
            ]
            for name in builtin_probe_names:
                try:
                    p = _plugins.load_plugin(name)
                    if p:
                        harness.run(generator, [p], all_detectors, evaluator)
                except Exception as e:
                    logging.warning("Could not load builtin probe %s: %s", name, e)

    # End run
    from garak import command
    command.end_run()

    # Generate comparison report
    print(f"\n{'='*60}")
    print("  Generating cross-strategy comparison report")
    print(f"{'='*60}\n")
    generate_report(report_filename)


def main():
    """CLI entry point with default AG News config."""
    import argparse

    parser = argparse.ArgumentParser(description="Run prompt injection tests")
    parser.add_argument(
        "--classes", type=Path,
        default=Path("src/ag_news_test/classes.yaml"),
        help="Path to classes YAML",
    )
    parser.add_argument(
        "--config", type=Path,
        default=Path("src/ag_news_test/app_config.yaml"),
        help="Path to app config YAML",
    )
    parser.add_argument(
        "--strategies", nargs="+",
        default=["direct", "cot", "defensive"],
        help="Prompt strategies to test",
    )
    parser.add_argument(
        "--probe-set", choices=["custom", "builtin", "all"],
        default="custom",
        help="Which probes to run",
    )
    parser.add_argument(
        "--generations", type=int, default=1,
        help="Generations per prompt",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("injection_results"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--dataset", type=str,
        default="sh0416/ag_news",
        help="HuggingFace dataset name",
    )
    parser.add_argument(
        "--dataset-split", type=str,
        default="test",
        help="Dataset split to use",
    )
    parser.add_argument(
        "--samples-per-class", type=int,
        default=5,
        help="Number of sample articles per class for probes",
    )

    args = parser.parse_args()

    test_config = InjectionTestConfig(
        classes_yaml_path=args.classes,
        app_config_yaml_path=args.config,
        strategies=args.strategies,
        probe_set=args.probe_set,
        generations_per_prompt=args.generations,
        output_dir=args.output_dir,
        dataset_name=args.dataset,
        dataset_split=args.dataset_split,
        samples_per_class=args.samples_per_class,
    )

    run(test_config)


if __name__ == "__main__":
    main()
