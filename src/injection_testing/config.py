"""Configuration for injection test runs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class InjectionTestConfig:
    """Parameters for a prompt injection test run."""

    classes_yaml_path: Path
    app_config_yaml_path: Path
    strategies: list[str] = field(default_factory=lambda: ["direct", "cot", "defensive"])
    probe_set: str = "custom"  # "custom" | "builtin" | "all"
    generations_per_prompt: int = 1
    output_dir: Path = Path("injection_results")
