#!/usr/bin/env python3
"""
Command-line interface for the Folder Organizer.

Usage:
    folder-organizer <input_folder> --classes_definition <classes.yaml> [options]
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console

from .config import ClassesDefinition, AppConfig
from .organizer import FolderOrganizer
from .prompts import list_available_strategies, get_prompt_strategy


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="folder-organizer",
        description="AI-powered document classifier for organizing files into categories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  folder-organizer ./documents --classes_definition classes.yaml
  
  # Use chain-of-thought prompting
  folder-organizer ./documents --classes_definition classes.yaml --strategy cot
  
  # Specify model and concurrency
  folder-organizer ./documents --classes_definition classes.yaml --model mistral --concurrency 5
  
  # Custom experiment ID
  folder-organizer ./documents --classes_definition classes.yaml --experiment-id test_run_001
        """,
    )
    
    # Required arguments
    parser.add_argument(
        "input_folder",
        type=Path,
        help="Path to the folder containing files to classify",
    )
    
    parser.add_argument(
        "-cd", "--classes_definition",
        type=Path,
        required=True,
        help="Path to classes definition YAML file",
    )
    
    # Optional arguments
    parser.add_argument(
        "-a", "--app-config",
        type=Path,
        default=None,
        help="Path to application config YAML file",
    )
    
    parser.add_argument(
        "-s", "--strategy",
        type=str,
        choices=list_available_strategies(),
        default="direct",
        help="Prompt strategy to use (default: direct)",
    )
    
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="llama3",
        help="Ollama model name (default: llama3)",
    )
    
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama API base URL (default: http://localhost:11434)",
    )
    
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Maximum concurrent LLM requests (default: 3)",
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum context window tokens (default: 4096)",
    )
    
    parser.add_argument(
        "-e", "--experiment-id",
        type=str,
        default=None,
        help="Custom experiment ID for logging",
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without processing files",
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    
    return parser


def main() -> int:
    """Main entry point for the CLI."""
    console = Console()
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # Validate input folder exists
        if not args.input_folder.exists():
            console.print(f"[red]Error: Input folder does not exist: {args.input_folder}[/red]")
            return 1
        
        # Validate config file exists
        if not args.classes_definition.exists():
            console.print(f"[red]Error: Classes definition file does not exist: {args.classes_definition}[/red]")
            return 1
        
        # Load classification config
        try:
            classes_definition = ClassesDefinition.from_yaml(args.classes_definition)
        except Exception as e:
            console.print(f"[red]Error loading classification config: {e}[/red]")
            return 1
        
        # Load or create app config
        if args.app_config and args.app_config.exists():
            app_config = AppConfig.from_yaml(args.app_config)
        else:
            app_config = AppConfig(
                model_name=args.model,
                ollama_base_url=args.ollama_url,
                max_concurrent_requests=args.concurrency,
                max_tokens=args.max_tokens,
                prompt_strategy=args.strategy,
            )
        
        # Get prompt strategy
        prompt_strategy = get_prompt_strategy(args.strategy)
        
        # Create organizer
        organizer = FolderOrganizer(
            input_folder=args.input_folder,
            classification_config=classes_definition,
            app_config=app_config,
            prompt_strategy=prompt_strategy,
            experiment_id=args.experiment_id,
        )
        
        # Validate
        is_valid, error = organizer.validate()
        if not is_valid:
            console.print(f"[red]Validation Error: {error}[/red]")
            return 1
        
        # Dry run check
        if args.dry_run:
            files = list(organizer.file_ops.get_text_files())
            console.print(f"[green]Validation successful![/green]")
            console.print(f"Found {len(files)} text files to process")
            console.print(f"Classes: {', '.join(classes_definition.get_class_names())}")
            console.print(f"Model: {app_config.model_name}")
            console.print(f"Strategy: {prompt_strategy.metadata.strategy_name}")
            return 0
        
        # Print configuration
        if not args.quiet:
            console.print("\n[bold]Folder Organizer[/bold]")
            console.print(f"Input: {args.input_folder}")
            console.print(f"Model: {app_config.model_name}")
            console.print(f"Strategy: {prompt_strategy.metadata.strategy_name}")
            console.print(f"Classes: {', '.join(classes_definition.get_class_names())}")
            console.print()
        
        # Run organization
        summary = organizer.run_sync(show_progress=not args.quiet)
        
        # Print summary
        if not args.quiet:
            organizer.print_summary(summary)
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
