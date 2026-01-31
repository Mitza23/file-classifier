
# Project Structure

## Overview

This document describes the organization and purpose of each file in the Folder Organizer project.

```
folder-organizer/
├── Core Application
│   ├── main.py                  # Main entry point and CLI
│   ├── classifier.py            # AI classification logic
│   ├── file_ops.py             # File operations with security
│   └── logger.py               # Experiment logging
│
├── Configuration
│   ├── config.yaml             # Default class definitions
│   └── requirements.txt        # Python dependencies
│
├── Testing & Utilities
│   ├── create_test_data.py    # Generate test documents
│   └── test_system.py         # Validation test suite
│
└── Documentation
    ├── README.md              # Main documentation
    ├── QUICKSTART.md          # Getting started guide
    └── RESEARCH_METHODOLOGY.md # Research best practices
```

## Core Application Files

### main.py
**Purpose**: Application entry point and orchestration

**Key Functions**:
- `load_config()`: Parse YAML configuration
- `process_files()`: Async file processing pipeline
- `main()`: CLI argument parsing and execution flow

**Usage**:
```bash
python main.py /path/to/folder [options]
```

**Dependencies**: All other core modules

---

### classifier.py
**Purpose**: LLM-based document classification

**Key Components**:
- `AIFileClassifier`: Main classification class
- `PromptStrategy`: Enum for prompt types (direct, CoT)
- `ClassificationResult`: Pydantic model for results
- `create_classification_schema()`: Dynamic schema generation

**Features**:
- Token counting and context truncation
- Semaphore-based concurrency control
- Structured output with Pydantic validation
- Multiple prompt strategy support

**Prompt Strategies**:
1. **Direct**: Single-shot classification
2. **Chain-of-Thought**: Multi-step reasoning

**Example**:
```python
classifier = AIFileClassifier(
    class_definitions=[...],
    model_name="llama3",
    prompt_strategy=PromptStrategy.DIRECT
)

result = await classifier.classify_file("doc.txt", content)
```

---

### file_ops.py
**Purpose**: Safe filesystem operations

**Key Functions**:
- `sanitize_folder_name()`: Prevent directory traversal
- `validate_parent_folder()`: Pre-execution checks
- `get_text_files()`: Find processable files
- `read_file_safely()`: Multi-encoding file reading

**Security Features**:
- Path traversal prevention
- Windows reserved name handling
- Cross-platform compatibility (pathlib)
- Filename conflict resolution

**Example**:
```python
safe_name = sanitize_folder_name("../../etc/passwd")
# Returns: "____etc_passwd"

organizer = FileOrganizer(parent_path, class_names)
organizer.create_class_folders()
organizer.move_file(file_path, predicted_class)
```

---

### logger.py
**Purpose**: Experiment tracking and analysis

**Key Components**:
- `ExperimentLogger`: Main logging class
- Output formats: CSV, JSONL, JSON summary
- Statistical analysis methods

**Captured Data**:
- Per-file: filename, class, confidence, raw response, errors
- Aggregate: success rates, distributions, error types

**Output Files**:
1. `experiment_name_results.csv`: Spreadsheet format
2. `experiment_name_results.jsonl`: Streaming JSON
3. `experiment_name_summary.json`: Statistics

**Example**:
```python
logger = ExperimentLogger(output_dir, "experiment_01")
logger.log_result(classification_result)
logger.finalize()  # Write all files
logger.print_summary()
```

## Configuration Files

### config.yaml
**Purpose**: Define document classification schema

**Structure**:
```yaml
classes:
  - name: "Class Name"
    description: "What documents fit this class"
```

**Customization**:
- Add/remove classes as needed
- Update descriptions for domain-specific tasks
- No code changes required

**Best Practices**:
- Use clear, distinct class names
- Provide detailed descriptions
- Avoid overlapping categories
- Test with 3-10 classes initially

---

### requirements.txt
**Purpose**: Python dependency specification

**Key Dependencies**:
- `langchain`: LLM orchestration
- `langchain-community`: Ollama integration
- `pydantic`: Data validation
- `pyyaml`: Config parsing
- `tiktoken`: Token counting
- `ollama`: Client library

**Installation**:
```bash
pip install -r requirements.txt
```

## Testing & Utilities

### create_test_data.py
**Purpose**: Generate test documents for experiments

**Creates**:
- 7 legitimate documents (various types)
- 8 prompt injection attempts (various patterns)

**Injection Types Included**:
1. Direct command ("Ignore previous instructions")
2. System override ("SYSTEM: Update rules")
3. JSON escape attempts
4. Prompt continuation
5. Social engineering
6. Jailbreak roleplay
7. Mid-document payloads
8. Unicode exploits

**Usage**:
```bash
python create_test_data.py
# Creates: ./test_documents/
```

---

### test_system.py
**Purpose**: Validate system functionality

**Tests**:
1. Path sanitization (security)
2. Schema creation (validation)
3. Folder validation (constraints)
4. File organizer (operations)
5. Experiment logger (data capture)
6. Config loading (parsing)

**Usage**:
```bash
python test_system.py
```

**Expected Output**:
```
✓ PASSED | Path Sanitization
✓ PASSED | Schema Creation
...
Result: 6/6 tests passed
```

## Documentation Files

### README.md
**Purpose**: Main project documentation

**Sections**:
- Project overview and purpose
- Feature list
- Installation instructions
- Usage examples
- Configuration guide
- Research workflow
- Technical specifications
- Troubleshooting

**Target Audience**: All users

---

### QUICKSTART.md
**Purpose**: Get started in 15 minutes

**Sections**:
- Prerequisites check
- Installation steps
- First experiment walkthrough
- Result examination
- Basic analysis techniques

**Target Audience**: New users, quick reference

---

### RESEARCH_METHODOLOGY.md
**Purpose**: Guide for academic research

**Sections**:
- Experimental design framework
- Research protocols
- Data collection standards
- Analysis techniques
- Statistical methods
- Reporting standards
- Ethical considerations
- Common pitfalls

**Target Audience**: Researchers, advanced users

## Data Flow

```
┌─────────────┐
│ User Input  │
│ (CLI args)  │
└──────┬──────┘
       │
       v
┌─────────────┐
│ Load Config │
│ (YAML)      │
└──────┬──────┘
       │
       v
┌─────────────┐
│ Validate    │
│ Folder      │
└──────┬──────┘
       │
       v
┌─────────────┐
│ Initialize  │
│ Components  │
└──────┬──────┘
       │
       v
┌─────────────┐      ┌──────────────┐
│ Read Files  │─────>│ AI Classifier│
└──────┬──────┘      └──────┬───────┘
       │                    │
       │    Classification  │
       │    Result          │
       v                    v
┌─────────────┐      ┌──────────────┐
│ File Ops    │<─────│ Logger       │
│ (Move)      │      │ (Record)     │
└──────┬──────┘      └──────┬───────┘
       │                    │
       v                    v
┌─────────────┐      ┌──────────────┐
│ Organized   │      │ CSV/JSONL    │
│ Folders     │      │ Files        │
└─────────────┘      └──────────────┘
```

## Extension Points

### Adding New Prompt Strategies

1. Add to `PromptStrategy` enum in `classifier.py`
2. Implement in `_build_prompt_template()` method
3. Update CLI options in `main.py`
4. Document in README.md

### Adding New LLM Providers

1. Modify `AIFileClassifier.__init__()` to accept provider type
2. Conditionally initialize different LLM clients
3. Ensure consistent interface for `invoke()` method
4. Test with validation suite

### Adding New Output Formats

1. Add method to `ExperimentLogger` class
2. Call from `finalize()` method
3. Document format in docstring
4. Update research methodology guide

### Adding New File Types

1. Update `text_extensions` in `file_ops.py`
2. Add extraction logic in `read_file_safely()` if needed
3. Test with various encodings
4. Document supported formats

## Deployment Considerations

### For Research Use

✅ Current design is appropriate:
- Local execution
- Full data capture
- Flexible experimentation
- No external dependencies (except Ollama)

### For Production Use

⚠️ Would require:
- Authentication and authorization
- Rate limiting and quotas
- Audit logging and monitoring
- Error recovery and retries
- Horizontal scaling
- API key management
- Content filtering
- Compliance validation

**Recommendation**: This tool is designed for research only. Do not deploy to production without significant security hardening.

## Performance Characteristics

### Throughput
- ~3-10 documents/second (depending on model)
- Parallelism limited by `--max-concurrent`
- Bottleneck: LLM inference time

### Memory Usage
- ~500MB base (Python + dependencies)
- +~2GB per concurrent request (model context)
- Scales linearly with concurrency

### Storage
- Input: Original files unchanged until move
- Output: 3 log files per experiment (~1KB per file processed)
- Folders: Created in place, no copies

### Scalability
- Single machine: 100-1000 files feasible
- 1000-10000 files: Consider batching
- 10000+ files: Need distributed approach

## Troubleshooting Reference

### Common Issues

| Issue | File | Function | Fix |
|-------|------|----------|-----|
| Model not found | main.py | `main()` | `ollama pull <model>` |
| Folder has subdirs | file_ops.py | `validate_parent_folder()` | Use empty folder |
| Parse failures | classifier.py | `classify_file()` | Check model output |
| Import errors | - | - | `pip install -r requirements.txt` |
| Permission denied | file_ops.py | `move_file()` | Check folder permissions |

### Debug Mode

Run with verbose flag:
```bash
python main.py folder --verbose
```

This shows:
- Per-file progress
- Classification results
- Error messages
- Timing information

### Logs Location

- Experiment logs: Same folder as input files
- Ollama logs: `~/.ollama/logs/`
- Python errors: stderr

## Version History

### v1.0 (Current)
- Initial release
- Direct and CoT prompting
- Pydantic validation
- CSV/JSONL logging
- Security hardening

### Future Enhancements
- Few-shot prompting
- Confidence calibration
- Automated injection detection
- Visualization dashboard
- Batch experiment runner
- API server mode
