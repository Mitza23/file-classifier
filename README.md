# Folder Organizer

An AI-powered document classifier designed for prompt injection research. This application classifies text documents into predefined categories using local LLMs via Ollama, with comprehensive logging for analyzing injection vulnerabilities and defenses.

## Features

- **AI-Powered Classification**: Uses LLMs (via Ollama) to classify documents into configurable categories
- **Prompt Injection Research**: Multiple prompt strategies for testing injection vulnerabilities
- **Modular Architecture**: Easy swapping of prompts, models, and configurations
- **Experiment Logging**: Detailed capture of raw LLM outputs, parsed decisions, and metadata
- **Security Features**: Path sanitization to prevent directory traversal attacks
- **Cross-Platform**: Supports Windows and Linux via pathlib

## Installation

### Prerequisites

1. **Python 3.10+**
2. **Ollama** installed and running locally
   ```bash
   # Install Ollama (Linux)
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull a model
   ollama pull llama3
   ```

### Install the Package

```bash
# Clone the repository
git clone <repository-url>
cd folder-organizer

# Install in development mode
pip install -e .
```

## Quick Start

### 1. Create a Classification Config

Create a `classes.yaml` file:

```yaml
classes:
  - name: Financial
    description: Financial documents like invoices, receipts, bank statements
    
  - name: Legal
    description: Contracts, agreements, legal notices
    
  - name: Technical
    description: Technical documentation, code, API references
```

### 2. Run the Classifier

```bash
# Basic usage
folder-organizer ./my_documents --config classes.yaml

# With specific model and strategy
folder-organizer ./my_documents --config classes.yaml --model mistral --strategy cot

# Dry run (validate without processing)
folder-organizer ./my_documents --config classes.yaml --dry-run
```

### 3. Python API

```python
from pathlib import Path
from folder_organizer import (
   FolderOrganizer,
   ClassificationConfig,
   AppConfig,
   get_prompt_strategy,
)

# Load configuration
config = ClassificationConfig.from_yaml(Path("examples/classes.yaml"))
app_config = AppConfig(
   model_name="llama3",
   prompt_strategy="cot",
   max_concurrent_requests=3,
)

# Create and run organizer
organizer = FolderOrganizer(
   input_folder=Path("./documents"),
   classification_config=config,
   app_config=app_config,
)

summary = organizer.run_sync()
organizer.print_summary(summary)
```

## Prompt Strategies

The system includes multiple prompt strategies for testing injection vulnerabilities:

### Direct Prompt (`--strategy direct`)
Straightforward classification without explicit reasoning steps. Baseline for injection testing.

### Chain-of-Thought (`--strategy cot`)
Multi-step reasoning before classification. Increases the surface area for potential injections to affect reasoning.

### Defensive (`--strategy defensive`)
Enhanced defenses against prompt injection with explicit warnings and sandboxing language.

### Custom Strategies

Create custom strategies by extending `PromptStrategy`:

```python
from folder_organizer.prompts import PromptStrategy, PromptMetadata

class MyCustomStrategy(PromptStrategy):
    @property
    def metadata(self) -> PromptMetadata:
        return PromptMetadata(
            strategy_name="custom",
            template_version="1.0",
            description="My custom prompt strategy"
        )
    
    def create_prompt(self, class_definitions: str):
        # Return a ChatPromptTemplate
        ...
```

## Experiment Logging

Every classification generates detailed logs for research analysis:

### Output Files

- `classification_results_<id>.jsonl` - Line-delimited JSON with all results
- `classification_results_<id>.csv` - CSV format for easy analysis
- `experiment_metadata_<id>.json` - Experiment configuration and summary

### Log Fields

| Field | Description |
|-------|-------------|
| `filename` | Name of the classified file |
| `predicted_class` | The LLM's classification decision |
| `confidence` | Confidence score (0-1) |
| `reasoning` | LLM's explanation for the classification |
| `raw_llm_response` | Complete raw response from the LLM |
| `prompt_template_used` | Identifier for the prompt strategy |
| `is_error` | Whether classification failed |
| `error_message` | Error details if applicable |
| `injection_detected` | Heuristic flag for potential injections |
| `timestamp` | ISO format timestamp |

### Analyzing Results

```python
from folder_organizer.logger import load_experiment_results, analyze_injection_success

# Load results
results = load_experiment_results(Path("classification_results_exp_001.jsonl"))

# Analyze injection success rates
analysis = analyze_injection_success(
    results,
    expected_classes={"Financial", "Legal", "Technical"}
)

print(f"Injection rate: {analysis['potential_injection_rate']:.2%}")
```

## Security Features

### Path Sanitization

The system sanitizes all LLM-generated class names to prevent directory traversal:

```python
# LLM returns malicious path
"../../etc/passwd" → "_etc_passwd"

# Path separators removed
"system/config" → "system_config"

# Control characters removed
"class\x00name" → "classname"
```

### Quarantine Folder

Files that fail classification or trigger validation errors are moved to `_Unclassified/` rather than causing crashes.

## Configuration Reference

### Classification Config (classes.yaml)

```yaml
classes:
  - name: CategoryName      # Used as folder name (sanitized)
    description: |          # Helps LLM understand the category
      Detailed description of what documents belong here
```

### App Config (app_config.yaml)

```yaml
model_name: "llama3"              # Ollama model
max_tokens: 4096                  # Context window
temperature: 0.1                  # LLM temperature
ollama_base_url: "http://localhost:11434"
max_concurrent_requests: 3        # Parallel request limit
prompt_strategy: "direct"         # Prompt strategy
quarantine_folder: "_Unclassified"
```

## CLI Reference

```
folder-organizer <input_folder> --config <config.yaml> [options]

Required:
  input_folder          Path to folder with files to classify
  -c, --config          Path to classification config YAML

Options:
  -a, --app-config      Path to application config YAML
  -s, --strategy        Prompt strategy: direct, cot, defensive
  -m, --model           Ollama model name (default: llama3)
  --ollama-url          Ollama API URL (default: http://localhost:11434)
  --concurrency         Max concurrent requests (default: 3)
  --max-tokens          Context window size (default: 4096)
  -e, --experiment-id   Custom experiment ID
  -q, --quiet           Suppress progress output
  --dry-run             Validate without processing
  -v, --version         Show version
```

## Project Structure

```
folder-organizer/
├── src/folder_organizer/
│   ├── __init__.py       # Package exports
│   ├── config.py         # Pydantic models for configuration
│   ├── prompts.py        # Prompt strategies
│   ├── classifier.py     # AI classification logic
│   ├── file_ops.py       # Safe file operations
│   ├── logger.py         # Experiment logging
│   ├── organizer.py      # Main orchestrator
│   └── cli.py            # Command-line interface
├── examples/
│   ├── classes.yaml      # Example classification config
│   ├── app_config.yaml   # Example app config
│   └── test_documents.md # Test documents for injection research
├── pyproject.toml        # Package configuration
└── README.md             # This file
```

## Research Use Cases

### Testing Injection Vulnerabilities

1. Create test documents with various injection payloads
2. Run classification with different prompt strategies
3. Analyze logs for successful injections (invalid classes, detection flags)

### Comparing Model Robustness

1. Configure multiple models in separate runs
2. Use consistent test documents
3. Compare injection success rates across models

### Evaluating Defense Strategies

1. Implement custom prompt strategies with different defenses
2. Run identical test sets against each strategy
3. Measure defense effectiveness from logs

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.
