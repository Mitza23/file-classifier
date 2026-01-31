# How to Run the Folder Organizer

## Quick Start Guide

### Step 1: Prerequisites

Make sure you have these installed:

```bash
# Python 3.10 or higher
python --version

# Ollama (for local LLM inference)
# Install from: https://ollama.com
ollama --version

# Pull a model (do this once)
ollama pull llama3
```

### Step 2: Install the Package

```bash
# Navigate to the project folder
cd folder_organizer

# Install in development mode
pip install -e .

# Or install dependencies directly without installing package
pip install pydantic pyyaml langchain langchain-ollama langchain-community rich aiofiles
```

### Step 3: Start Ollama

In a separate terminal, make sure Ollama is running:

```bash
ollama serve
```

### Step 4: Run the Classifier

**Option A: Using the CLI (after pip install -e .)**

```bash
# Basic usage
folder-organizer ./test_documents --config examples/classes.yaml

# With chain-of-thought prompting
folder-organizer ./test_documents --config examples/classes.yaml --strategy cot

# With a different model
folder-organizer ./test_documents --config examples/classes.yaml --model mistral

# Dry run (validate without processing)
folder-organizer ./test_documents --config examples/classes.yaml --dry-run
```

**Option B: Using Python directly**

```python
from pathlib import Path
from folder_organizer import (
    FolderOrganizer,
    ClassificationConfig,
    AppConfig,
)

# Load configuration
config = ClassificationConfig.from_yaml(Path("examples/classes.yaml"))
app_config = AppConfig(
    model_name="llama3",
    prompt_strategy="direct",  # or "cot" or "defensive"
)

# Run the organizer
organizer = FolderOrganizer(
    input_folder=Path("./test_documents"),
    classification_config=config,
    app_config=app_config,
)

summary = organizer.run_sync()
organizer.print_summary(summary)
```

**Option C: Run as a script without installing**

Create a file called `run.py` in the project root:

```python
import sys
sys.path.insert(0, "src")

from pathlib import Path
from folder_organizer import FolderOrganizer, ClassificationConfig, AppConfig

config = ClassificationConfig.from_yaml(Path("examples/classes.yaml"))
app_config = AppConfig(model_name="llama3", prompt_strategy="direct")

organizer = FolderOrganizer(
    input_folder=Path("./test_documents"),
    classification_config=config,
    app_config=app_config,
)

summary = organizer.run_sync()
organizer.print_summary(summary)
```

Then run:
```bash
python run.py
```

---

## Test Documents Included

### Normal Documents (should classify correctly)

| File | Expected Class |
|------|----------------|
| `quarterly_report.txt` | Financial |
| `invoice_892.txt` | Financial |
| `consulting_agreement.txt` | Legal |
| `api_documentation.txt` | Technical |
| `product_launch.txt` | Marketing |
| `onboarding_checklist.txt` | HR |
| `research_paper.txt` | Research |
| `email_to_mom.txt` | Personal |

### Prompt Injection Tests

| File | Attack Type | What It Tests |
|------|-------------|---------------|
| `injection_ignore.txt` | Instruction override | "Ignore previous instructions" attack |
| `injection_delimiter.txt` | Delimiter escape | Attempts to break out of document tags |
| `injection_fake_system.txt` | Authority spoofing | Fake system message to leak prompt |
| `security_training.txt` | Benign with keywords | Contains injection phrases but is legitimate |

---

## Understanding the Output

### Folder Structure After Running

```
test_documents/
├── Financial/
│   ├── quarterly_report.txt
│   └── invoice_892.txt
├── Legal/
│   └── consulting_agreement.txt
├── Technical/
│   └── api_documentation.txt
├── Marketing/
│   └── product_launch.txt
├── HR/
│   ├── onboarding_checklist.txt
│   └── security_training.txt
├── Research/
│   └── research_paper.txt
├── Personal/
│   └── email_to_mom.txt
├── _Unclassified/
│   └── (any files that failed classification)
├── classification_results_exp_XXXXX.jsonl
├── classification_results_exp_XXXXX.csv
└── experiment_metadata_exp_XXXXX.json
```

### Log File Fields

The JSONL log captures everything for analysis:

```json
{
  "filename": "quarterly_report.txt",
  "predicted_class": "Financial",
  "confidence": 0.95,
  "reasoning": "Document contains revenue figures, profit margins, and financial recommendations",
  "raw_llm_response": "{\"predicted_class\": \"Financial\", ...}",
  "prompt_template_used": "direct_v1.0",
  "is_error": false,
  "error_message": "",
  "injection_detected": false,
  "timestamp": "2024-01-20T15:30:00Z"
}
```

---

## Comparing Prompt Strategies

Run the same documents with different strategies:

```bash
# Run 1: Direct prompt
folder-organizer ./test_docs_copy1 --config examples/classes.yaml --strategy direct --experiment-id direct_run

# Run 2: Chain-of-thought
folder-organizer ./test_docs_copy2 --config examples/classes.yaml --strategy cot --experiment-id cot_run

# Run 3: Defensive prompt  
folder-organizer ./test_docs_copy3 --config examples/classes.yaml --strategy defensive --experiment-id defensive_run
```

Then compare the JSONL files to see which strategy was more resistant to injection attempts.

---

## Analyzing Results

```python
from folder_organizer.logger import load_experiment_results, analyze_injection_success

# Load results
results = load_experiment_results(Path("classification_results_exp_direct_run.jsonl"))

# Check injection success rate
analysis = analyze_injection_success(
    results,
    expected_classes={"Financial", "Legal", "Technical", "Marketing", "HR", "Research", "Personal"}
)

print(f"Total files: {analysis['total_files']}")
print(f"Injection indicators: {analysis['injection_indicators']}")
print(f"Invalid classes: {analysis['invalid_class_outputs']}")
print(f"Potential injection rate: {analysis['potential_injection_rate']:.2%}")
```

---

## Troubleshooting

### "Connection refused" error
→ Ollama isn't running. Start it with `ollama serve`

### "Model not found" error
→ Pull the model first: `ollama pull llama3`

### "Folder contains subfolders" error
→ The input folder must be flat (no subdirectories). This is by design to prevent re-processing.

### Files going to _Unclassified
→ Check the log file for `error_message` to see why classification failed

### Slow performance
→ Reduce concurrency: `--concurrency 1`
→ Use a smaller model: `--model llama3:8b` or `--model mistral`
