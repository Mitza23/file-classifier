"""Configuration for injection test runs."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class InjectionTestConfig(BaseModel):
    """Parameters for a prompt injection test run.

    Loaded from a YAML file (e.g. testing_config.yaml) that centralises
    all experiment settings: LLM, dataset, strategies, probes, and output.
    """

    # LLM settings
    model_name: str = Field(default="llama3.1:8b", description="Ollama model name")
    temperature: float = Field(default=0.1, description="LLM temperature for classification")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")

    # Dataset settings
    dataset_name: str = Field(default="sh0416/ag_news", description="HuggingFace dataset identifier")
    dataset_split: str = Field(default="test", description="Dataset split to use")
    samples_per_class: int = Field(default=5, description="Number of dataset samples per class for probes")
    label_mapping: dict[int, str] = Field(
        default_factory=dict,
        description="Maps integer dataset labels to class name strings",
    )

    # Injection testing settings
    strategies: list[str] = Field(
        default_factory=lambda: ["direct", "cot", "defensive"],
        description="Prompt strategies to test",
    )
    probe_set: str = Field(default="custom", description="Probe set: 'custom', 'builtin', or 'all'")
    generations_per_prompt: int = Field(default=1, description="Number of LLM generations per prompt")

    # Output settings
    output_dir: Path = Field(default=Path("injection_results"), description="Output directory for results")

    @classmethod
    def from_yaml(cls, path: Path) -> "TestingConfig":
        """Load testing configuration from YAML."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data) if data else cls()