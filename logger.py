"""
Experiment Logger Module
Captures detailed logs of classification results for prompt injection analysis.
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from classifier import ClassificationResult


class ExperimentLogger:
    """
    Logs classification experiments to CSV and JSON formats for analysis.
    Designed to capture data needed for measuring prompt injection success rates.
    """
    
    def __init__(self, output_dir: Path, experiment_name: str = None):
        """
        Initialize the logger.
        
        Args:
            output_dir: Directory where log files will be saved
            experiment_name: Optional name for the experiment run
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate experiment name if not provided
        if experiment_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            experiment_name = f"experiment_{timestamp}"
        
        self.experiment_name = experiment_name
        self.results: List[ClassificationResult] = []
        
        # Define output file paths
        self.csv_path = self.output_dir / f"{experiment_name}_results.csv"
        self.jsonl_path = self.output_dir / f"{experiment_name}_results.jsonl"
        self.summary_path = self.output_dir / f"{experiment_name}_summary.json"
    
    def log_result(self, result: ClassificationResult) -> None:
        """
        Add a classification result to the log.
        
        Args:
            result: ClassificationResult object to log
        """
        self.results.append(result)
    
    def write_csv(self) -> None:
        """Write all results to a CSV file."""
        if not self.results:
            return
        
        fieldnames = [
            'filename',
            'predicted_class',
            'confidence_score',
            'prompt_template_used',
            'is_error',
            'error_message',
            'timestamp',
            'raw_llm_response'
        ]
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                # Convert result to dict
                row = {
                    'filename': result.filename,
                    'predicted_class': result.predicted_class,
                    'confidence_score': result.confidence_score if result.confidence_score else '',
                    'prompt_template_used': result.prompt_template_used,
                    'is_error': result.is_error,
                    'error_message': result.error_message if result.error_message else '',
                    'timestamp': result.timestamp,
                    'raw_llm_response': result.raw_llm_response.replace('\n', '\\n')  # Escape newlines
                }
                writer.writerow(row)
    
    def write_jsonl(self) -> None:
        """Write all results to a JSONL file (one JSON object per line)."""
        if not self.results:
            return
        
        with open(self.jsonl_path, 'w', encoding='utf-8') as f:
            for result in self.results:
                json_line = result.model_dump_json()
                f.write(json_line + '\n')
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """
        Calculate summary statistics for the experiment.
        
        Returns:
            Dictionary with experiment statistics
        """
        if not self.results:
            return {}
        
        total_files = len(self.results)
        error_count = sum(1 for r in self.results if r.is_error)
        success_count = total_files - error_count
        
        # Count files per class
        class_distribution = {}
        for result in self.results:
            if not result.is_error:
                class_name = result.predicted_class
                class_distribution[class_name] = class_distribution.get(class_name, 0) + 1
        
        # Calculate average confidence (if available)
        confidences = [r.confidence_score for r in self.results 
                      if r.confidence_score is not None and not r.is_error]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        
        # Analyze error types
        error_types = {}
        for result in self.results:
            if result.is_error and result.error_message:
                error_type = result.error_message.split(':')[0]  # Get first part of error message
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'experiment_name': self.experiment_name,
            'total_files': total_files,
            'successful_classifications': success_count,
            'failed_classifications': error_count,
            'success_rate': success_count / total_files if total_files > 0 else 0,
            'error_rate': error_count / total_files if total_files > 0 else 0,
            'average_confidence': avg_confidence,
            'class_distribution': class_distribution,
            'error_types': error_types,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def write_summary(self) -> None:
        """Write summary statistics to a JSON file."""
        stats = self.calculate_statistics()
        
        with open(self.summary_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
    
    def finalize(self) -> None:
        """
        Write all log files and summary statistics.
        Call this after all classifications are complete.
        """
        self.write_csv()
        self.write_jsonl()
        self.write_summary()
    
    def print_summary(self) -> None:
        """Print a summary of the experiment results to console."""
        stats = self.calculate_statistics()
        
        print("\n" + "=" * 70)
        print(f"EXPERIMENT SUMMARY: {stats['experiment_name']}")
        print("=" * 70)
        print(f"Total Files:                {stats['total_files']}")
        print(f"Successful Classifications: {stats['successful_classifications']}")
        print(f"Failed Classifications:     {stats['failed_classifications']}")
        print(f"Success Rate:               {stats['success_rate']:.2%}")
        
        if stats.get('average_confidence'):
            print(f"Average Confidence:         {stats['average_confidence']:.3f}")
        
        print("\nClass Distribution:")
        for class_name, count in sorted(stats['class_distribution'].items(), 
                                       key=lambda x: x[1], reverse=True):
            print(f"  {class_name:30s}: {count:3d} files")
        
        if stats['error_types']:
            print("\nError Types:")
            for error_type, count in sorted(stats['error_types'].items(), 
                                           key=lambda x: x[1], reverse=True):
                print(f"  {error_type:40s}: {count:3d} occurrences")
        
        print("\nOutput Files:")
        print(f"  CSV:     {self.csv_path}")
        print(f"  JSONL:   {self.jsonl_path}")
        print(f"  Summary: {self.summary_path}")
        print("=" * 70 + "\n")
