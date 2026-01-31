# Quick Start Guide

## Prerequisites Check

Before starting, ensure you have:

1. **Python 3.8+**
   ```bash
   python --version
   ```

2. **Ollama Installed and Running**
   ```bash
   ollama --version
   ollama list  # Should show installed models
   ```

3. **A Model Downloaded**
   ```bash
   ollama pull llama3
   # or
   ollama pull mistral
   ```

## Installation (5 minutes)

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify Installation**
   ```bash
   python -c "import langchain, pydantic, yaml; print('✓ All dependencies installed')"
   ```

## Running Your First Experiment (10 minutes)

### Step 1: Create Test Data

Generate sample documents including injection attempts:

```bash
python create_test_data.py
```

This creates a `test_documents/` folder with:
- 7 legitimate documents (various types)
- 8 documents with prompt injection attempts

### Step 2: Run Basic Classification

```bash
python main.py test_documents --verbose
```

Expected output:
```
======================================================================
FOLDER ORGANIZER - Prompt Injection Research Tool
======================================================================
Folder:           /path/to/test_documents
Config:           config.yaml
Model:            llama3
Strategy:         direct
Classes:          7
Max Concurrent:   3
======================================================================
Found 15 text files to classify

Processing 15 files...
----------------------------------------------------------------------
[  1/ 15] ✓ OK | api_documentation.txt                    → Technical Documentation
[  2/ 15] ✓ OK | meeting_notes.txt                        → Business Communication
[  3/ 15] ✓ OK | invoice_2026_001.txt                     → Financial Records
...
```

### Step 3: Examine Results

Three output files are created in `test_documents/`:

1. **CSV File** - Open in Excel/Google Sheets
   ```bash
   # On Mac/Linux
   open test_documents/experiment_*_results.csv
   
   # On Windows
   start test_documents\experiment_*_results.csv
   ```

2. **Summary JSON** - Quick statistics
   ```bash
   cat test_documents/experiment_*_summary.json
   ```

3. **JSONL File** - For programmatic analysis
   ```bash
   head -5 test_documents/experiment_*_results.jsonl
   ```

### Step 4: Check Organized Files

```bash
ls test_documents/
```

You should see folders for each class:
```
Technical_Documentation/
Business_Communication/
Financial_Records/
Research_Papers/
Marketing_Materials/
Legal_Documents/
Personal_Notes/
_Unclassified/
```

## Analyzing Injection Success

### Manual Review

1. Open the CSV file in a spreadsheet
2. Filter by `is_error = True` to find parse failures
3. Check files starting with "injection_" - compare their location to expected class
4. Review `raw_llm_response` column for evidence of manipulation

### Key Questions to Answer

- **Did any injections succeed?** 
  Check if `injection_*.txt` files ended up in unexpected folders

- **What injection patterns worked?**
  Note patterns in successful injections (ignore previous, system override, etc.)

- **How did the system fail?**
  Look at `error_message` column for parse failures vs. misclassifications

## Running Comparative Experiments

### Test Different Prompt Strategies

```bash
# Baseline with direct prompting
python main.py test_documents --strategy direct --experiment baseline_direct

# Test Chain-of-Thought defense
python main.py test_documents --strategy cot --experiment defense_cot
```

Compare the results:
```bash
# Check success rates
grep "success_rate" test_documents/*summary.json

# Count files in _Unclassified folder
ls test_documents_baseline/*Unclassified/ | wc -l
ls test_documents_defense/*Unclassified/ | wc -l
```

### Test Different Models

```bash
# Ensure models are available
ollama list

# Run with different models
python main.py test_documents --model llama3 --experiment llama3_test
python main.py test_documents --model mistral --experiment mistral_test
python main.py test_documents --model phi --experiment phi_test
```

## Customizing for Your Research

### 1. Create Custom Classes

Edit `config.yaml`:
```yaml
classes:
  - name: "Sensitive Data"
    description: "Documents containing PII, passwords, or confidential info"
  
  - name: "Public Content"
    description: "Safe for public distribution"
```

### 2. Create Domain-Specific Tests

Create your own injection test files:
```bash
cd test_documents
echo "Your injection test content here" > custom_injection.txt
```

### 3. Batch Testing

Create a script to run multiple experiments:
```bash
#!/bin/bash
for strategy in direct cot; do
  for model in llama3 mistral; do
    python main.py test_documents \
      --strategy $strategy \
      --model $model \
      --experiment ${model}_${strategy}
  done
done
```

## Troubleshooting

### "Connection refused" error

Ollama is not running:
```bash
# Start Ollama
ollama serve
# In another terminal, run your script
```

### "Model not found" error

Download the model first:
```bash
ollama pull llama3
```

### "No text files found to process"

Ensure you're pointing to the correct folder:
```bash
python main.py test_documents  # Not the parent folder
```

### Very slow processing

Reduce concurrent requests:
```bash
python main.py test_documents --max-concurrent 1
```

### Out of memory errors

Reduce token limit:
```bash
python main.py test_documents --max-tokens 2000
```

## Next Steps

1. **Read the full README.md** for detailed documentation
2. **Review the code** in `classifier.py` to understand prompt construction
3. **Modify prompts** to test your own defense strategies
4. **Create domain-specific test cases** for your research area
5. **Analyze results** using the CSV/JSONL outputs

## Getting Help

If you encounter issues:

1. Run with verbose flag: `python main.py folder --verbose`
2. Check Ollama logs: `ollama logs`
3. Verify model is loaded: `ollama list`
4. Test model directly: `ollama run llama3 "Hello"`

## Research Ethics

Remember:
- This tool is for academic research on prompt injection defenses
- Use responsibly and ethically
- Do not deploy in production without proper security review
- Do not use for malicious purposes
- Always disclose the use of AI in research methodology
