"""
AI File Classifier module.

Handles LLM-based document classification with context management,
structured output parsing, and concurrency control.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from langchain_ollama import ChatOllama
from pydantic import ValidationError

from file_classifier.classifier_config import ClassesDefinition, ClassifierConfig, create_classification_response_model
from file_classifier.prompts import get_prompt_strategy


@dataclass
class ClassificationResult:
    """Result of a single file classification."""
    
    filename: str
    predicted_class: str
    confidence: float
    reasoning: str
    raw_llm_response: str
    prompt_template_used: str
    is_error: bool = False
    error_message: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "filename": self.filename,
            "predicted_class": self.predicted_class,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "raw_llm_response": self.raw_llm_response,
            "prompt_template_used": self.prompt_template_used,
            "is_error": self.is_error,
            "error_message": self.error_message,
        }


class LLMResponseParser:
    """Parses and validates LLM responses."""
    
    def __init__(self, config: ClassesDefinition):
        self.config = config
        self.response_model = create_classification_response_model(config)
        self.valid_classes = set(config.get_class_names())
    
    def extract_json(self, text: str) -> Optional[dict[str, Any]]:
        """Extract JSON from LLM response text."""
        # Try to find JSON in the response
        # Pattern 1: Look for JSON object
        json_pattern = r'\{[^{}]*"predicted_class"[^{}]*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # Pattern 2: Try parsing the entire response as JSON
        try:
            # Remove markdown code blocks if present
            cleaned = re.sub(r'```json\s*', '', text)
            cleaned = re.sub(r'```\s*', '', cleaned)
            cleaned = cleaned.strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Pattern 3: Look for any JSON object
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
        
        return None
    
    def parse(self, raw_response: str) -> tuple[Optional[Any], Optional[str]]:
        """
        Parse and validate the LLM response.
        
        Returns:
            Tuple of (validated_response, error_message)
        """
        json_data = self.extract_json(raw_response)
        
        if json_data is None:
            return None, "Failed to extract JSON from LLM response"
        
        try:
            validated = self.response_model(**json_data)
            return validated, None
        except ValidationError as e:
            return None, f"Validation error: {e}"



class AIFileClassifier:
    """
    Main classifier that orchestrates LLM-based document classification.
    
    Features:
    - Structured output with Pydantic validation
    - Concurrency control via semaphore
    - Modular prompt strategies
    """
    
    def __init__(self, classifier_config: ClassifierConfig):
        self.classifier_config = classifier_config
        
        # Initialize prompt strategy
        self.prompt_strategy = get_prompt_strategy(classifier_config.prompt_strategy)

        self.parser = LLMResponseParser(classifier_config.classes_definitions)

        self.classes_definitions = classifier_config.classes_definitions
        
        # Initialize LLM
        self.llm = ChatOllama(
            model=classifier_config.model_name,
            base_url=classifier_config.ollama_base_url,
            temperature=classifier_config.temperature,
        )
        
        # Create the prompt
        class_definitions = self.classes_definitions.format_for_prompt()
        self.prompt = self.prompt_strategy.create_prompt(class_definitions)
    

    def _classify_impl(self, filename: str, content: str) -> ClassificationResult:
        """Internal classification implementation."""

        
        # Format the prompt
        formatted_messages = self.prompt.format_messages(
            class_definitions=self.classes_definitions.format_for_prompt(),
            file_content=content
        )
        
        try:
            # Call the LLM
            response = self.llm.invoke(formatted_messages)
            raw_response = response.content if hasattr(response, 'content') else str(response)
            
            # Parse the response
            parsed, error = self.parser.parse(raw_response)
            
            if parsed is None:
                # Failed to parse - return error result
                return ClassificationResult(
                    filename=filename,
                    predicted_class=self.classifier_config.fallback_class,
                    confidence=0.0,
                    reasoning=f"Parse error: {error}",
                    raw_llm_response=raw_response,
                    prompt_template_used=self.prompt_strategy.get_template_string(),
                    is_error=True,
                    error_message=error or "Unknown parse error",
                )

            
            return ClassificationResult(
                filename=filename,
                predicted_class=parsed.predicted_class,
                confidence=parsed.confidence,
                reasoning=parsed.reasoning,
                raw_llm_response=raw_response,
                prompt_template_used=self.prompt_strategy.get_template_string(),
                is_error=False,
            )
            
        except Exception as e:
            # Handle any LLM or network errors
            print("ERROR during classification:", e)
            return ClassificationResult(
                filename=filename,
                predicted_class=self.classifier_config.fallback_class,
                confidence=0.0,
                reasoning="",
                raw_llm_response="",
                prompt_template_used=self.prompt_strategy.get_template_string(),
                is_error=True,
                error_message=str(e),
            )
    
    def classify_sync(self, filename: str, content: str) -> ClassificationResult:
        """Synchronous wrapper for classification."""
        return self._classify_impl(filename, content)
