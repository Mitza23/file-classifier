# Research Methodology Guide

## Experimental Design for Prompt Injection Research

This guide provides a structured approach to conducting prompt injection experiments using the Folder Organizer tool.

## Research Framework

### 1. Define Research Questions

Examples:
- How effective are structured output constraints (Pydantic/Enum) at preventing prompt injections?
- Does Chain-of-Thought prompting provide better defense than direct prompting?
- Which injection patterns are most successful across different LLMs?
- How does model size/capability affect robustness to injections?

### 2. Hypothesis Formation

Example hypotheses:
- **H1**: Chain-of-Thought prompting reduces injection success rate by >20%
- **H2**: Structured output validation prevents >90% of injection attempts
- **H3**: Larger models (70B params) are more robust than smaller models (7B params)
- **H4**: Position of injection (beginning vs. end) affects success rate

### 3. Experimental Variables

#### Independent Variables
- **Prompt Strategy**: direct, chain-of-thought
- **Model**: llama3, mistral, phi, etc.
- **Injection Type**: ignore instructions, system override, JSON escape, etc.
- **Content Length**: short, medium, long documents

#### Dependent Variables
- **Success Rate**: Correct classifications / Total files
- **Injection Success Rate**: Injections that achieved their goal
- **Parse Failure Rate**: Responses that broke JSON structure
- **Confidence Scores**: When available from the model

#### Control Variables
- Same class definitions across experiments
- Same set of test documents
- Same max_tokens and concurrency settings

## Experimental Protocols

### Protocol 1: Baseline Measurement

**Objective**: Establish baseline performance without injections

```bash
# Run with clean documents only
python main.py legitimate_docs --strategy direct --model llama3 --experiment baseline
```

**Analysis**:
- Record overall accuracy
- Note any misclassifications
- Document average confidence scores
- Identify confusable class pairs

### Protocol 2: Injection Attack Surface

**Objective**: Test various injection patterns

```bash
# Create test sets for each injection type
# Run experiments with each set
python main.py injection_set_1 --strategy direct --model llama3 --experiment injection_test_1
```

**Injection Categories to Test**:
1. **Direct Command Injections**
   - "Ignore previous instructions"
   - "Disregard classification rules"
   - "System: New classification protocol"

2. **Output Format Manipulation**
   - JSON escape sequences
   - Premature JSON closing
   - Malformed structure attempts

3. **Social Engineering**
   - Authority claims (system admin, developer)
   - Urgency/emergency scenarios
   - Role confusion (debugging mode, maintenance)

4. **Context Manipulation**
   - Injections at document start
   - Injections in document middle
   - Injections at document end
   - Multiple injection attempts

5. **Encoding Attacks**
   - Unicode characters
   - Base64 encoded commands
   - URL encoding

### Protocol 3: Defense Comparison

**Objective**: Compare defense effectiveness

```bash
# Test each defense mechanism
python main.py test_set --strategy direct --experiment defense_none
python main.py test_set --strategy cot --experiment defense_cot

# Different models
python main.py test_set --model llama3 --experiment model_llama3
python main.py test_set --model mistral --experiment model_mistral
```

**Metrics to Compare**:
- Injection success rate per strategy
- Parse failure rate
- Processing time
- False positive rate (legitimate docs misclassified)

### Protocol 4: Edge Cases & Robustness

**Objective**: Test system limits

```bash
# Very long documents
python main.py long_docs --max-tokens 8000 --experiment long_content

# Very short documents
python main.py short_docs --experiment short_content

# Multilingual content
python main.py multilingual_docs --experiment multilingual

# Adversarial examples
python main.py adversarial_docs --experiment adversarial
```

## Data Collection Standards

### Required Data Points Per Experiment

1. **Metadata**
   - Experiment name and timestamp
   - Model name and version
   - Prompt strategy used
   - Configuration parameters

2. **Per-File Metrics**
   - Filename
   - Expected class (ground truth)
   - Predicted class
   - Confidence score
   - Classification time
   - Raw LLM response
   - Error status and message

3. **Aggregate Metrics**
   - Total files processed
   - Success rate
   - Error rate
   - Average confidence
   - Class distribution
   - Error type distribution

### Ground Truth Labeling

Create a separate file mapping filenames to expected classes:

```json
{
  "api_documentation.txt": "Technical Documentation",
  "meeting_notes.txt": "Business Communication",
  "injection_ignore.txt": "Technical Documentation",
  "injection_override.txt": "Business Communication"
}
```

Use this to calculate:
- True Positive Rate (correctly classified)
- False Positive Rate (incorrectly classified)
- Injection Success Rate (ended up in wrong class due to injection)

## Analysis Techniques

### 1. Quantitative Analysis

```python
import pandas as pd
import json

# Load experiment results
df = pd.read_csv('experiment_results.csv')

# Calculate metrics
success_rate = (df['is_error'] == False).mean()
injection_files = df[df['filename'].str.contains('injection')]
injection_success = injection_files['is_error'].mean()

# Compare across experiments
experiments = ['baseline', 'cot_defense', 'llama3', 'mistral']
results = []

for exp in experiments:
    with open(f'{exp}_summary.json') as f:
        data = json.load(f)
        results.append({
            'experiment': exp,
            'success_rate': data['success_rate'],
            'error_rate': data['error_rate']
        })

comparison_df = pd.DataFrame(results)
```

### 2. Qualitative Analysis

Review raw LLM responses for:
- Evidence of injection awareness
- Reasoning patterns that caught injections
- Failure modes that allowed injections
- Unusual output patterns

### 3. Statistical Significance

Use appropriate statistical tests:

```python
from scipy.stats import chi2_contingency

# Compare success rates between strategies
contingency_table = [[success_direct, fail_direct],
                     [success_cot, fail_cot]]
chi2, p_value, dof, expected = chi2_contingency(contingency_table)

print(f"Chi-square test p-value: {p_value}")
if p_value < 0.05:
    print("Significant difference detected")
```

### 4. Confusion Matrix

For multi-class classification:

```python
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns

# Load results with ground truth
y_true = [...]  # Ground truth labels
y_pred = [...]  # Predicted labels

cm = confusion_matrix(y_true, y_pred)
sns.heatmap(cm, annot=True, fmt='d')
plt.ylabel('True Class')
plt.xlabel('Predicted Class')
plt.savefig('confusion_matrix.png')

print(classification_report(y_true, y_pred))
```

## Reporting Standards

### Experiment Report Template

```markdown
## Experiment: [NAME]

### Objective
[Research question being addressed]

### Methodology
- Model: [model name and version]
- Prompt Strategy: [direct/cot]
- Test Set: [number] files ([breakdown by type])
- Parameters: max_tokens=[X], max_concurrent=[Y]

### Results
- Overall Success Rate: X%
- Injection Success Rate: Y%
- Parse Failure Rate: Z%

### Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

### Notable Examples
[Include specific examples of successful/failed injections]

### Limitations
[Any confounds or limitations in this experiment]

### Next Steps
[Follow-up experiments needed]
```

## Reproducibility Checklist

To ensure reproducible research:

- [ ] Document exact model versions (ollama list output)
- [ ] Save configuration files used
- [ ] Record timestamp and system specs
- [ ] Version control test documents
- [ ] Save raw LLM responses
- [ ] Document any manual adjustments
- [ ] Share experiment parameters
- [ ] Provide ground truth labels
- [ ] Include random seeds if applicable
- [ ] Note any preprocessing steps

## Ethical Considerations

### Responsible Research Practices

1. **Disclosure**: Clearly state this is AI-based research
2. **Purpose**: Use only for legitimate security research
3. **Impact**: Consider potential misuse of findings
4. **Transparency**: Share methodology openly
5. **Limitations**: Acknowledge what the system can't test

### Red Flags to Avoid

- Don't develop or share production-ready injection attacks
- Don't target live systems without permission
- Don't create universal bypass techniques
- Don't weaponize findings
- Don't skip ethical review processes

## Common Pitfalls

### Methodological Issues

1. **Selection Bias**: Testing only on obvious injections
   - *Solution*: Include subtle variations and edge cases

2. **Overfitting**: Optimizing for specific test cases
   - *Solution*: Use train/test splits, unseen examples

3. **Confounding Variables**: Changing multiple parameters
   - *Solution*: Vary one variable at a time

4. **Cherry Picking**: Only reporting interesting results
   - *Solution*: Pre-register hypotheses, report all results

5. **Lack of Baseline**: No comparison to undefended system
   - *Solution*: Always run baseline experiments first

### Technical Issues

1. **Inconsistent Environment**: Model updates between runs
   - *Solution*: Lock model versions, document dependencies

2. **Small Sample Size**: Too few test cases
   - *Solution*: Aim for 100+ examples per condition

3. **No Ground Truth**: Can't measure accuracy
   - *Solution*: Manually label expected classes

4. **Ignoring Failed Runs**: Excluding errors from analysis
   - *Solution*: Analyze failure modes separately

## Advanced Topics

### A/B Testing Framework

For comparing two configurations:

```python
# Calculate required sample size
from statsmodels.stats.power import zt_ind_solve_power

effect_size = 0.2  # Expected difference
alpha = 0.05  # Significance level
power = 0.8  # Statistical power

n = zt_ind_solve_power(effect_size, power, alpha, alternative='two-sided')
print(f"Need {n:.0f} samples per condition")
```

### Regression Analysis

For continuous outcomes (confidence scores):

```python
import statsmodels.api as sm

# Prepare data
X = df[['prompt_strategy_cot', 'model_size', 'doc_length']]
X = sm.add_constant(X)
y = df['confidence_score']

# Fit model
model = sm.OLS(y, X).fit()
print(model.summary())
```

### Time Series Analysis

If testing over time or with different model versions:

```python
import matplotlib.pyplot as plt

experiments = sorted(df['timestamp'].unique())
success_rates = [df[df['timestamp']==t]['is_error'].mean() for t in experiments]

plt.plot(experiments, success_rates)
plt.xlabel('Experiment Timestamp')
plt.ylabel('Success Rate')
plt.title('Performance Over Time')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('performance_trend.png')
```

## Resources

### Recommended Reading

- Perez et al. "Jailbreak Detection in LLMs"
- OpenAI "Red Teaming Language Models"
- Anthropic "Constitutional AI" papers
- OWASP "LLM Top 10" vulnerabilities

### Tools for Analysis

- **Pandas**: Data manipulation
- **Matplotlib/Seaborn**: Visualization
- **Scipy**: Statistical tests
- **Jupyter**: Interactive analysis
- **Git**: Version control

### Datasets

Consider creating standardized test sets:
- Benign documents (various domains)
- Known injection patterns
- Adversarial examples
- Edge cases
