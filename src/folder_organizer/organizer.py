"""
Main orchestrator for the Folder Organizer application.

Coordinates the classifier, file operations, and logging components
to process documents and organize them into class folders.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from .classifier import AIFileClassifier, ClassificationResult
from .config import ClassesDefinition, AppConfig
from .file_ops import FileOperations
from .logger import ExperimentLogger
from .prompts import get_prompt_strategy, PromptStrategy


@dataclass
class OrganizationSummary:
    """Summary of the organization operation."""
    
    total_files: int
    successful: int
    failed: int
    injection_detections: int
    class_distribution: dict[str, int]
    experiment_id: str
    log_files: list[Path]


class FolderOrganizer:
    """
    Main orchestrator for AI-powered folder organization.
    
    Coordinates:
    - File discovery and reading
    - AI classification
    - Safe file movement
    - Experiment logging
    """
    
    def __init__(
        self,
        input_folder: Path,
        classification_config: ClassesDefinition,
        app_config: Optional[AppConfig] = None,
        prompt_strategy: Optional[PromptStrategy] = None,
        experiment_id: Optional[str] = None,
    ):
        """
        Initialize the folder organizer.
        
        Args:
            input_folder: Path to the folder containing files to organize
            classification_config: Configuration with class definitions
            app_config: Application configuration (uses defaults if not provided)
            prompt_strategy: Prompt strategy to use (uses config default if not provided)
            experiment_id: Optional ID for this experiment run
        """
        self.input_folder = Path(input_folder).resolve()
        self.classification_config = classification_config
        self.app_config = app_config or AppConfig()
        
        # Initialize prompt strategy
        if prompt_strategy is None:
            self.prompt_strategy = get_prompt_strategy(self.app_config.prompt_strategy)
        else:
            self.prompt_strategy = prompt_strategy
        
        # Initialize components
        self.file_ops = FileOperations(
            self.input_folder,
            quarantine_folder=self.app_config.quarantine_folder
        )
        
        self.classifier = AIFileClassifier(classes_definition=classification_config, app_config=self.app_config,
                                           prompt_strategy=self.prompt_strategy)
        
        self.logger = ExperimentLogger(
            output_dir=self.input_folder,
            experiment_id=experiment_id,
            model_name=self.app_config.model_name,
            prompt_strategy=self.prompt_strategy.metadata.strategy_name,
        )
        
        self.console = Console()
    
    def validate(self) -> tuple[bool, str]:
        """Validate the input folder and configuration."""
        return self.file_ops.validate_base_folder()
    
    async def process_file(self, filepath: Path) -> tuple[ClassificationResult, bool, str]:
        """
        Process a single file: read, classify, and move.
        
        Returns:
            Tuple of (classification_result, move_success, move_message)
        """
        # Read file content
        content, read_error = self.file_ops.read_file(filepath)
        
        if content is None:
            # File read error - create error result and quarantine
            result = ClassificationResult(
                filename=filepath.name,
                predicted_class=self.app_config.quarantine_folder,
                confidence=0.0,
                reasoning="",
                raw_llm_response="",
                prompt_template_used=self.prompt_strategy.get_template_string(),
                is_error=True,
                error_message=read_error or "Unknown read error",
            )
            dest, success, message = self.file_ops.move_to_quarantine(filepath, read_error or "")
            return result, success, message
        
        # Classify the content
        result = await self.classifier.classify(filepath.name, content)
        
        # Log the result
        self.logger.log_result(result)
        
        # Move the file
        if result.is_error:
            dest, success, message = self.file_ops.move_to_quarantine(
                filepath, result.error_message
            )
        else:
            dest, success, message = self.file_ops.move_file(
                filepath, result.predicted_class
            )
        
        return result, success, message
    
    async def run(self, show_progress: bool = True) -> OrganizationSummary:
        """
        Run the organization process.
        
        Args:
            show_progress: Whether to show progress bar in console
            
        Returns:
            Summary of the organization operation
        """
        # Validate first
        is_valid, error = self.validate()
        if not is_valid:
            raise ValueError(error)
        
        # Get all files
        files = list(self.file_ops.get_text_files())
        
        if not files:
            self.console.print("[yellow]No text files found in the folder.[/yellow]")
            return OrganizationSummary(
                total_files=0,
                successful=0,
                failed=0,
                injection_detections=0,
                class_distribution={},
                experiment_id=self.logger.experiment_id,
                log_files=[self.logger.jsonl_path, self.logger.csv_path],
            )
        
        # Process files
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
            ) as progress:
                task = progress.add_task("Classifying files...", total=len(files))
                
                for filepath in files:
                    result, success, message = await self.process_file(filepath)
                    
                    # Show per-file status
                    status = "✓" if not result.is_error else "✗"
                    progress.console.print(
                        f"  {status} {filepath.name} → {result.predicted_class}"
                        + (f" ({result.confidence:.0%})" if result.confidence > 0 else "")
                    )
                    
                    progress.advance(task)
        else:
            for filepath in files:
                await self.process_file(filepath)
        
        # Finalize logging
        self.logger.finalize()
        
        # Build summary
        summary = self.logger.get_summary()
        
        return OrganizationSummary(
            total_files=summary["total_files"],
            successful=summary["successful"],
            failed=summary["failed"],
            injection_detections=summary["injection_detections"],
            class_distribution=self.logger.get_class_distribution(),
            experiment_id=self.logger.experiment_id,
            log_files=[
                self.logger.jsonl_path,
                self.logger.csv_path,
                self.logger.metadata_path,
            ],
        )
    
    def run_sync(self, show_progress: bool = True) -> OrganizationSummary:
        """Synchronous wrapper for the run method."""
        return asyncio.run(self.run(show_progress))
    
    def print_summary(self, summary: OrganizationSummary) -> None:
        """Print a formatted summary to console."""
        self.console.print("\n[bold green]Organization Complete![/bold green]\n")
        
        # Summary table
        table = Table(title="Classification Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Total Files", str(summary.total_files))
        table.add_row("Successful", f"[green]{summary.successful}[/green]")
        table.add_row("Failed", f"[red]{summary.failed}[/red]" if summary.failed > 0 else "0")
        table.add_row(
            "Injection Detections",
            f"[yellow]{summary.injection_detections}[/yellow]" if summary.injection_detections > 0 else "0"
        )
        table.add_row("Experiment ID", summary.experiment_id)
        
        self.console.print(table)
        
        # Class distribution
        if summary.class_distribution:
            dist_table = Table(title="\nClass Distribution")
            dist_table.add_column("Class", style="cyan")
            dist_table.add_column("Files", style="white")
            
            for cls, count in sorted(summary.class_distribution.items(), key=lambda x: -x[1]):
                dist_table.add_row(cls, str(count))
            
            self.console.print(dist_table)
        
        # Log files
        self.console.print("\n[bold]Log Files:[/bold]")
        for log_file in summary.log_files:
            if log_file.exists():
                self.console.print(f"  • {log_file}")


def organize_folder(
    input_folder: str | Path,
    config_path: str | Path,
    app_config_path: Optional[str | Path] = None,
    prompt_strategy: str = "direct",
    experiment_id: Optional[str] = None,
    show_progress: bool = True,
) -> OrganizationSummary:
    """
    Convenience function to organize a folder.
    
    Args:
        input_folder: Path to folder containing files
        config_path: Path to classification config YAML
        app_config_path: Optional path to app config YAML
        prompt_strategy: Name of prompt strategy to use
        experiment_id: Optional experiment ID
        show_progress: Whether to show progress
        
    Returns:
        Organization summary
    """
    # Load configs
    classification_config = ClassesDefinition.from_yaml(Path(config_path))
    
    if app_config_path:
        app_config = AppConfig.from_yaml(Path(app_config_path))
    else:
        app_config = AppConfig(prompt_strategy=prompt_strategy)
    
    # Get prompt strategy
    strategy = get_prompt_strategy(prompt_strategy)
    
    # Create and run organizer
    organizer = FolderOrganizer(
        input_folder=Path(input_folder),
        classification_config=classification_config,
        app_config=app_config,
        prompt_strategy=strategy,
        experiment_id=experiment_id,
    )
    
    return organizer.run_sync(show_progress)
