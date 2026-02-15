"""Orchestrator for injection testing.

Runs all probes against the classifier for each prompt strategy,
using Garak's harness/evaluator infrastructure, then generates
a cross-strategy comparison report.
"""

import datetime
from pathlib import Path

from file_classifier.classifier_config import ClassesDefinition, ClassifierConfig

from injection_testing.experiment_config import InjectionTestConfig
from injection_testing.dataset import load_dataset_samples
from injection_testing.generator import ClassifierGenerator
from injection_testing.report import generate_report_to_console

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


def run(classifier_config: ClassifierConfig, test_config: InjectionTestConfig):
    """Main entry point: run injection tests across all strategies."""
    # Load class definitions and app test_config
    classes_def = classifier_config.classes_definitions
    valid_classes = classes_def.get_class_names()
    # Load dataset samples for probes
    if not test_config.label_mapping:
        raise ValueError(
            "label_mapping must be set in test_config.yaml to map integer dataset labels to class names"
        )

    # Initialize Garak
    report_filename = _init_garak(test_config)
    print(f"Report file: {report_filename}")
    print()

    print(f"Loading dataset samples from {test_config.dataset_name} ({test_config.dataset_split})...")
    samples = load_dataset_samples(
        dataset_name=test_config.dataset_name,
        split=test_config.dataset_split,
        samples_per_class=test_config.samples_per_class,
        label_mapping=test_config.label_mapping,
    )
    print(f"Loaded samples per class: {{{', '.join(f'{k}: {len(v)}' for k, v in samples.items())}}}")

    print(f"Loaded {len(valid_classes)} classes: {valid_classes}")
    print(f"Strategies to test: {test_config.strategies}")
    print(f"Probe set: {test_config.probe_set}")
    print()


    from garak.harnesses.base import Harness
    from garak.evaluators.base import ThresholdEvaluator

    harness = Harness()
    evaluator = ThresholdEvaluator(threshold=0.5)

    for strategy in test_config.strategies:
        print(f"\n{'='*60}")
        print(f"  Testing strategy: {strategy}")
        print(f"{'='*60}\n")

        # Create generator for this strategy
        generator = ClassifierGenerator(
            classifier_config=classifier_config,
            strategy_name=strategy,
        )

        # Build probe-detector pairs and run each with matched detectors
        if test_config.probe_set in ("custom", "all"):
            for probe, detectors in _build_probe_detector_pairs(valid_classes, samples):
                harness.run(generator, [probe], detectors, evaluator)

        if test_config.probe_set in ("builtin", "all"):
            raise ValueError("Builtin probe set not implemented yet")

    # End run
    from garak import command
    command.end_run()

    # Generate comparison report
    print(f"\n{'='*60}")
    print("  Generating cross-strategy comparison report")
    print(f"{'='*60}\n")
    generate_report_to_console(report_filename)


def main():
    """CLI entry point with default AG News test_config."""
    import argparse

    parser = argparse.ArgumentParser(description="Run prompt injection tests")

    parser.add_argument(
        "--test_config", type=Path,
        default=Path("src/ag_news_test/test_config.yaml"),
        help="Path to injection test test_config YAML",
    )
    parser.add_argument(
        "--classifier_config", type=Path,
        default=Path("src/ag_news_test/classifier_config.yaml"),
        help="Path to classifier test_config YAML",
    )

    args = parser.parse_args()
    classifier_config = ClassifierConfig.from_yaml(args.classifier_config)
    test_config = InjectionTestConfig.from_yaml(args.test_config)

    run(classifier_config, test_config)


if __name__ == "__main__":
    main()
