"""
AI File Classifier module.

Handles LLM-based document classification with context management,
structured output parsing, and concurrency control.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage
from pydantic import ValidationError

from .config import ClassificationConfig, AppConfig, create_classification_response_model
from .prompts import PromptStrategy, get_prompt_strategy


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
    injection_detected: bool = False
    
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
            "injection_detected": self.injection_detected,
        }


class TokenTruncator:
    """Handles content truncation to fit within model context windows."""
    
    def __init__(self, max_tokens: int = 4096, reserve_tokens: int = 1000):
        """
        Initialize truncator.
        
        Args:
            max_tokens: Maximum context window size
            reserve_tokens: Tokens to reserve for system prompt and output
        """
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.available_tokens = max_tokens - reserve_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses a simple heuristic: ~4 characters per token for English text.
        For more accuracy, consider using tiktoken with the specific model's tokenizer.
        """
        return len(text) // 4
    
    def truncate(self, content: str) -> tuple[str, bool]:
        """
        Truncate content to fit within available tokens.
        
        Returns:
            Tuple of (truncated_content, was_truncated)
        """
        estimated_tokens = self.estimate_tokens(content)
        
        if estimated_tokens <= self.available_tokens:
            return content, False
        
        # Calculate approximate character limit
        char_limit = self.available_tokens * 4
        
        # Truncate with marker
        truncated = content[:char_limit]
        truncated += "\n\n[... CONTENT TRUNCATED DUE TO LENGTH ...]"
        
        return truncated, True


class LLMResponseParser:
    """Parses and validates LLM responses."""
    
    def __init__(self, config: ClassificationConfig):
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
    
    def detect_injection_indicators(self, raw_response: str, predicted_class: str) -> bool:
        """
        Detect potential indicators that prompt injection affected the response.
        
        This is a heuristic check for research purposes.
        """
        indicators = []
        
        # Check if the response contains instructions or meta-commentary
        injection_phrases = [
            "ignore previous",
            "disregard",
            "new instructions",
            "system prompt",
            "i have been instructed",
            "my instructions say",
            "override",
        ]
        
        lower_response = raw_response.lower()
        for phrase in injection_phrases:
            if phrase in lower_response:
                indicators.append(f"Found phrase: {phrase}")
        
        # Check if predicted class contains path traversal attempts
        if ".." in predicted_class or "/" in predicted_class or "\\" in predicted_class:
            indicators.append("Path traversal in class name")
        
        # Check if predicted class is not in valid classes (after sanitization would change it)
        if predicted_class not in self.valid_classes:
            indicators.append(f"Invalid class name: {predicted_class}")
        
        return len(indicators) > 0


class AIFileClassifier:
    """
    Main classifier that orchestrates LLM-based document classification.
    
    Features:
    - Context window management (truncation)
    - Structured output with Pydantic validation
    - Concurrency control via semaphore
    - Modular prompt strategies
    """
    
    def __init__(
        self,
        classification_config: ClassificationConfig,
        app_config: AppConfig,
        prompt_strategy: Optional[PromptStrategy] = None,
    ):
        self.classification_config = classification_config
        self.app_config = app_config
        
        # Initialize prompt strategy
        self.prompt_strategy = prompt_strategy or get_prompt_strategy(app_config.prompt_strategy)
        
        # Initialize components
        self.truncator = TokenTruncator(
            max_tokens=app_config.max_tokens,
            reserve_tokens=1500  # Reserve space for system prompt and response
        )
        self.parser = LLMResponseParser(classification_config)
        
        # Concurrency control
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # Initialize LLM
        self.llm = ChatOllama(
            model=app_config.model_name,
            base_url=app_config.ollama_base_url,
            temperature=app_config.temperature,
        )
        
        # Create the prompt
        class_definitions = classification_config.format_for_prompt()
        self.prompt = self.prompt_strategy.create_prompt(class_definitions)
    
    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Lazy initialization of semaphore for async context."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.app_config.max_concurrent_requests)
        return self._semaphore
    
    async def classify(self, filename: str, content: str) -> ClassificationResult:
        """
        Classify a single file's content.
        
        Args:
            filename: Name of the file being classified
            content: Text content of the file
            
        Returns:
            ClassificationResult with all relevant data for logging
        """
        async with self.semaphore:
            return await self._classify_impl(filename, content)
    
    async def _classify_impl(self, filename: str, content: str) -> ClassificationResult:
        """Internal classification implementation."""
        
        # Truncate content if necessary
        truncated_content, was_truncated = self.truncator.truncate(content)
        
        # Format the prompt
        formatted_messages = self.prompt.format_messages(
            class_definitions=self.classification_config.format_for_prompt(),
            file_content=truncated_content
        )
        
        try:
            # Call the LLM
            response = await self.llm.ainvoke(formatted_messages)
            raw_response = response.content if hasattr(response, 'content') else str(response)
            
            # Parse the response
            parsed, error = self.parser.parse(raw_response)
            
            if parsed is None:
                # Failed to parse - return error result
                return ClassificationResult(
                    filename=filename,
                    predicted_class=self.app_config.quarantine_folder,
                    confidence=0.0,
                    reasoning=f"Parse error: {error}",
                    raw_llm_response=raw_response,
                    prompt_template_used=self.prompt_strategy.get_template_string(),
                    is_error=True,
                    error_message=error or "Unknown parse error",
                )
            
            # Check for injection indicators
            injection_detected = self.parser.detect_injection_indicators(
                raw_response, parsed.predicted_class
            )
            
            return ClassificationResult(
                filename=filename,
                predicted_class=parsed.predicted_class,
                confidence=parsed.confidence,
                reasoning=parsed.reasoning,
                raw_llm_response=raw_response,
                prompt_template_used=self.prompt_strategy.get_template_string(),
                is_error=False,
                injection_detected=injection_detected,
            )
            
        except Exception as e:
            # Handle any LLM or network errors
            return ClassificationResult(
                filename=filename,
                predicted_class=self.app_config.quarantine_folder,
                confidence=0.0,
                reasoning="",
                raw_llm_response="",
                prompt_template_used=self.prompt_strategy.get_template_string(),
                is_error=True,
                error_message=str(e),
            )
    
    def classify_sync(self, filename: str, content: str) -> ClassificationResult:
        """Synchronous wrapper for classification."""
        return asyncio.run(self.classify(filename, content))
