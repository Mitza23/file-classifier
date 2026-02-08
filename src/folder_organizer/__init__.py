# """
# Folder Organizer - AI-powered document classification for prompt injection research.
#
# This package provides tools for:
# - Classifying documents into predefined categories using LLMs
# - Testing prompt injection vulnerabilities and defenses
# - Logging experiment data for research analysis
# """
#
# from .config import ClassesDefinition, AppConfig, ClassDefinition
# from .classifier import AIFileClassifier, ClassificationResult
# from .file_ops import FileOperations, SanitizedPath
# from .logger import ExperimentLogger
# from .organizer import FolderOrganizer, organize_folder, OrganizationSummary
# from .prompts import (
#     PromptStrategy,
#     DirectPromptStrategy,
#     ChainOfThoughtPromptStrategy,
#     DefensivePromptStrategy,
#     get_prompt_strategy,
#     list_available_strategies,
# )
#
# __version__ = "1.0.0"
# __author__ = "Folder Organizer Team"
#
# __all__ = [
#     # Configuration
#     "ClassesDefinition",
#     "AppConfig",
#     "ClassDefinition",
#     # Classifier
#     "AIFileClassifier",
#     "ClassificationResult",
#     # File operations
#     "FileOperations",
#     "SanitizedPath",
#     # Logging
#     "ExperimentLogger",
#     # Orchestration
#     "FolderOrganizer",
#     "organize_folder",
#     "OrganizationSummary",
#     # Prompts
#     "PromptStrategy",
#     "DirectPromptStrategy",
#     "ChainOfThoughtPromptStrategy",
#     "DefensivePromptStrategy",
#     "get_prompt_strategy",
#     "list_available_strategies",
# ]
