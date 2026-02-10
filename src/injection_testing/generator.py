"""Custom Garak Generator that wraps AIFileClassifier.

Bridges the file classifier into Garak's pipeline so that probe texts
are passed as file content to the classifier, and structured results
are returned via Message.notes for detectors to inspect.
"""

import logging
from typing import List, Union

from garak import _config
from garak.generators.base import Generator
from garak.attempt import Message, Conversation

from folder_organizer.classifier import AIFileClassifier
from folder_organizer.config import ClassesDefinition, AppConfig
from folder_organizer.prompts import get_prompt_strategy


class ClassifierGenerator(Generator):
    """Garak Generator wrapping AIFileClassifier for injection testing."""

    generator_family_name = "file-classifier"
    parallel_capable = False
    supports_multiple_generations = False

    def __init__(
        self,
        classes_definition: ClassesDefinition,
        app_config: AppConfig,
        strategy_name: str,
        config_root=_config,
    ):
        self.classes_definition = classes_definition
        self.app_config = app_config
        self.strategy_name = strategy_name
        self.valid_classes = classes_definition.get_class_names()

        # Build the classifier with the requested prompt strategy
        prompt_strategy = get_prompt_strategy(strategy_name)
        self.classifier = AIFileClassifier(
            classes_definition=classes_definition,
            app_config=app_config,
            prompt_strategy=prompt_strategy,
        )

        self.name = f"{strategy_name}"
        super().__init__(name=self.name, config_root=config_root)

    def _call_model(
        self, prompt: Conversation, generations_this_call: int = 1
    ) -> List[Union[Message, None]]:
        """Send probe text through the classifier and return structured results."""
        # Extract the probe text from the conversation
        probe_text = prompt.last_message().text
        if probe_text is None:
            return [None]

        # Classify using a synthetic filename
        result = self.classifier.classify_sync(
            filename="probe_input.txt",
            content=probe_text,
        )

        # Build Message with raw LLM response as text and parsed fields in notes
        msg = Message(
            text=result.raw_llm_response,
            notes={
                "predicted_class": result.predicted_class,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "is_error": result.is_error,
                "error_message": result.error_message,
            },
        )

        logging.debug(
            "ClassifierGenerator [%s]: predicted=%s confidence=%.2f",
            self.strategy_name,
            result.predicted_class,
            result.confidence,
        )

        return [msg]
