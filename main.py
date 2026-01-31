#!/usr/bin/env python3
"""
Folder Organizer - Main Application
Classifies and organizes documents for prompt injection research.
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Dict, List
import yaml

from classifier import AIFileClassifier, PromptStrategy, ClassificationResult
from file_ops import FileOrganizer, get_text_files, read_file_safely
from logger import ExperimentLogger


def load_config(config_path: Path) -> Dict:
    """
    Load class definitions from YAML config file.
    
    Args:
        config_path: Path to config.yaml
        
    Returns:
        Parsed configuration dictionary
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if 'classes' not in config or not isinstance(config['classes'], list):
            raise ValueError("Config must contain a 'classes' array")
        
        # Validate each class has name and description
        for cls in config['classes']:
            if 'name' not in cls or 'description' not in cls:
                raise ValueError("Each class must have 'name' and 'description' fields")
        
        return config
    
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


async def process_files(
    files: List[Path],
    classifier: AIFileClassifier,
    organizer: FileOrganizer,
    logger: ExperimentLogger,
    verbose: bool = False
) -> None:
    """
    Process all files: classify and move them to appropriate folders.
    
    Args:
        files: List of file paths to process
        classifier: AIFileClassifier instance
        organizer: FileOrganizer instance
        logger: ExperimentLogger instance
        verbose: Whether to print progress
    """
    total = len(files)
    
    if verbose:
        print(f"\nProcessing {total} files...")
        print("-" * 70)
    
    # Create classification tasks
    tasks = []
    for file_path in files:
        content = read_file_safely(file_path)
        if content is None:
            # File reading failed - log as error
            result = ClassificationResult(
                filename=file_path.name,
                predicted_class="_Unclassified",
                raw_llm_response="",
                prompt_template_used="",
                is_error=True,
                error_message="Failed to read file"
            )
            logger.log_result(result)
            organizer.move_file(file_path, "_Unclassified", is_error=True)
            continue
        
        tasks.append((file_path, classifier.classify_file(file_path.name, content)))
    
    # Execute classifications concurrently
    completed = 0
    for file_path, task in tasks:
        result = await task
        
        # Log result
        logger.log_result(result)
        
        # Move file to appropriate folder
        dest_path = organizer.move_file(
            file_path,
            result.predicted_class,
            is_error=result.is_error
        )
        
        completed += 1
        
        if verbose:
            status = "✗ ERROR" if result.is_error else "✓ OK"
            print(f"[{completed:3d}/{total:3d}] {status} | {file_path.name:40s} → {result.predicted_class}")


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Organize files by classifying them with LLMs (for prompt injection research)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with default settings
  python main.py /path/to/folder
  
  # Use Chain-of-Thought prompting with llama3.1:8b model
  python main.py /path/to/folder --strategy cot --model llama3.1:8b
  
  # Run with custom config and experiment name
  python main.py /path/to/folder --config my_config.yaml --experiment test_01
  
  # Limit concurrent requests and token window
  python main.py /path/to/folder --max-concurrent 2 --max-tokens 2000
        """
    )
    
    # Required arguments
    parser.add_argument(
        'folder',
        type=Path,
        help='Path to folder containing text files to organize'
    )
    
    # Configuration
    parser.add_argument(
        '--config',
        type=Path,
        default=Path('config.yaml'),
        help='Path to YAML config file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--experiment',
        type=str,
        help='Name for this experiment run (default: auto-generated timestamp)'
    )
    
    # Model settings
    parser.add_argument(
        '--model',
        type=str,
        default='llama3.1:8b',
        help='Ollama model name (default: llama3.1:8b)'
    )
    
    parser.add_argument(
        '--ollama-url',
        type=str,
        default='http://localhost:11434',
        help='Ollama base URL (default: http://localhost:11434)'
    )
    
    # Prompt strategy
    parser.add_argument(
        '--strategy',
        choices=['direct', 'cot'],
        default='direct',
        help='Prompt strategy: direct or cot (chain-of-thought) (default: direct)'
    )
    
    # Performance tuning
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=3,
        help='Maximum concurrent Ollama requests (default: 3)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=4000,
        help='Maximum tokens to send to model (default: 4000)'
    )
    
    # Output options
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed progress information'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.folder.exists():
        print(f"Error: Folder does not exist: {args.folder}", file=sys.stderr)
        sys.exit(1)
    
    if not args.config.exists():
        print(f"Error: Config file does not exist: {args.config}", file=sys.stderr)
        sys.exit(1)
    
    # Load configuration
    config = load_config(args.config)
    class_definitions = config['classes']
    
    if not args.quiet:
        print("=" * 70)
        print("FOLDER ORGANIZER - Prompt Injection Research Tool")
        print("=" * 70)
        print(f"Folder:           {args.folder.absolute()}")
        print(f"Config:           {args.config}")
        print(f"Model:            {args.model}")
        print(f"Strategy:         {args.strategy}")
        print(f"Classes:          {len(class_definitions)}")
        print(f"Max Concurrent:   {args.max_concurrent}")
        print("=" * 70)
    
    # Map strategy string to enum
    strategy_map = {
        'direct': PromptStrategy.DIRECT,
        'cot': PromptStrategy.CHAIN_OF_THOUGHT
    }
    prompt_strategy = strategy_map[args.strategy]
    
    # Initialize components
    try:
        # Initialize classifier
        classifier = AIFileClassifier(
            class_definitions=class_definitions,
            model_name=args.model,
            prompt_strategy=prompt_strategy,
            max_tokens=args.max_tokens,
            max_concurrent=args.max_concurrent,
            ollama_base_url=args.ollama_url
        )
        
        # Initialize file organizer
        class_names = [c['name'] for c in class_definitions]
        organizer = FileOrganizer(args.folder, class_names)
        
        # Create class folders
        organizer.create_class_folders()
        
        # Initialize logger
        logger = ExperimentLogger(
            output_dir=args.folder,
            experiment_name=args.experiment
        )
        
        # Get files to process
        files = get_text_files(args.folder)
        
        if not files:
            print("No text files found to process.", file=sys.stderr)
            sys.exit(0)
        
        if not args.quiet:
            print(f"Found {len(files)} text files to classify\n")
        
        # Process files
        asyncio.run(
            process_files(
                files=files,
                classifier=classifier,
                organizer=organizer,
                logger=logger,
                verbose=args.verbose
            )
        )
        
        # Finalize logs
        logger.finalize()
        
        # Print summary
        if not args.quiet:
            logger.print_summary()
        
        print("\n✓ Organization complete!")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(1)
    
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
