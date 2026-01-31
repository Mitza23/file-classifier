"""
Configuration models and schema definitions.

This module handles loading class definitions from YAML and creating
dynamic Pydantic models and Enums for strict output validation.
"""

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ClassDefinition(BaseModel):
    """A single classification category."""
    
    name: str = Field(..., description="The class name/label")
    description: str = Field(..., description="Description of what belongs in this class")
    
    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Ensure class name is safe for filesystem use."""
        # Remove any path traversal attempts or dangerous characters
        sanitized = v.strip()
        # Only allow alphanumeric, spaces, hyphens, and underscores
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ")
        sanitized = "".join(c for c in sanitized if c in safe_chars)
        # Replace spaces with underscores for folder names
        sanitized = sanitized.replace(" ", "_")
        # Ensure not empty after sanitization
        if not sanitized:
            sanitized = "Unknown"
        return sanitized


class ClassesDefinition(BaseModel):
    """Configuration containing all class definitions."""
    
    classes: list[ClassDefinition] = Field(..., min_length=1)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "ClassesDefinition":
        """Load configuration from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Handle both list format and dict with 'classes' key
        if isinstance(data, list):
            return cls(classes=data)
        elif isinstance(data, dict) and "classes" in data:
            return cls(classes=data["classes"])
        else:
            raise ValueError("YAML must contain a list of classes or a dict with 'classes' key")
    
    def create_class_enum(self) -> type[Enum]:
        """Dynamically create an Enum from the class definitions."""
        enum_members = {cls.name.upper(): cls.name for cls in self.classes}
        # Add special fallback class
        enum_members["UNCLASSIFIED"] = "_Unclassified"
        return Enum("ClassLabel", enum_members)
    
    def get_class_names(self) -> list[str]:
        """Get list of valid class names."""
        return [cls.name for cls in self.classes]
    
    def get_class_descriptions(self) -> dict[str, str]:
        """Get mapping of class names to descriptions."""
        return {cls.name: cls.description for cls in self.classes}
    
    def format_for_prompt(self) -> str:
        """Format class definitions for inclusion in prompts."""
        lines = ["Available categories for classification:"]
        for i, cls in enumerate(self.classes, 1):
            lines.append(f"{i}. {cls.name}: {cls.description}")
        return "\n".join(lines)


class AppConfig(BaseModel):
    """Application-level configuration."""
    
    # LLM settings
    model_name: str = Field(default="llama3.1:8b", description="Ollama model name")
    max_tokens: int = Field(default=4096, description="Maximum context window tokens")
    temperature: float = Field(default=0.1, description="LLM temperature for classification")
    
    # Concurrency settings
    max_concurrent_requests: int = Field(default=3, description="Maximum concurrent Ollama requests")
    
    # Prompt strategy
    prompt_strategy: str = Field(default="direct", description="Prompt strategy: 'direct' or 'cot'")
    
    # Ollama settings
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    
    # Output settings
    quarantine_folder: str = Field(default="_Unclassified", description="Folder for unclassified files")
    log_file: str = Field(default="classification_results.jsonl", description="Experiment log file name")
    
    @classmethod
    def from_yaml(cls, path: Path) -> "AppConfig":
        """Load app configuration from YAML."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data) if data else cls()


def create_classification_response_model(config: ClassesDefinition) -> type[BaseModel]:
    """
    Create a dynamic Pydantic model for structured LLM output.
    
    This ensures the LLM can only output valid class names.
    """
    valid_classes = config.get_class_names()
    
    class ClassificationResponse(BaseModel):
        """Structured response from the LLM classifier."""
        
        predicted_class: str = Field(
            ..., 
            description=f"The predicted class. Must be one of: {', '.join(valid_classes)}"
        )
        confidence: float = Field(
            default=0.0,
            ge=0.0,
            le=1.0,
            description="Confidence score between 0 and 1"
        )
        reasoning: str = Field(
            default="",
            description="Brief explanation of the classification decision"
        )
        
        @field_validator("predicted_class")
        @classmethod
        def validate_class(cls, v: str) -> str:
            """Ensure the predicted class is valid."""
            # Sanitize the input first
            sanitized = v.strip()
            
            # Check for exact match
            if sanitized in valid_classes:
                return sanitized
            
            # Check for case-insensitive match
            lower_map = {c.lower(): c for c in valid_classes}
            if sanitized.lower() in lower_map:
                return lower_map[sanitized.lower()]
            
            # If no match, raise validation error
            raise ValueError(
                f"Invalid class '{sanitized}'. Must be one of: {', '.join(valid_classes)}"
            )
    
    return ClassificationResponse
