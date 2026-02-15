"""
Tests for the Folder Organizer application.
"""

import pytest

from file_classifier.classifier_config import (
    ClassDefinition,
    ClassesDefinition,
    create_classification_response_model,
)
from src.folder_organizer.file_ops import FileOperations, SanitizedPath
from file_classifier.prompts import (
    get_prompt_strategy,
    list_available_strategies,
    DirectPromptStrategy,
    ChainOfThoughtPromptStrategy,
)
from file_classifier.classifier import LLMResponseParser


class TestSanitizedPath:
    """Tests for path sanitization."""
    
    def test_normal_name(self):
        """Normal names should pass through."""
        result = SanitizedPath.from_string("Financial")
        assert result.value == "Financial"
        assert not result.was_modified
    
    def test_path_traversal(self):
        """Path traversal attempts should be sanitized."""
        result = SanitizedPath.from_string("../../etc/passwd")
        assert ".." not in result.value
        assert "/" not in result.value
        assert result.was_modified
    
    def test_backslash_traversal(self):
        """Windows path separators should be sanitized."""
        result = SanitizedPath.from_string("..\\..\\system")
        assert ".." not in result.value
        assert "\\" not in result.value
        assert result.was_modified
    
    def test_null_bytes(self):
        """Null bytes should be removed."""
        result = SanitizedPath.from_string("class\x00name")
        assert "\x00" not in result.value
        assert result.was_modified
    
    def test_invalid_windows_chars(self):
        """Windows-invalid characters should be sanitized."""
        result = SanitizedPath.from_string('file<>:"|?*name')
        for char in '<>:"|?*':
            assert char not in result.value
        assert result.was_modified
    
    def test_empty_string(self):
        """Empty strings should get a default value."""
        result = SanitizedPath.from_string("")
        assert result.value != ""
        assert result.value == "_Empty"
    
    def test_reserved_windows_names(self):
        """Reserved Windows names should be prefixed."""
        result = SanitizedPath.from_string("CON")
        assert result.value.startswith("_")
        
        result = SanitizedPath.from_string("NUL")
        assert result.value.startswith("_")
    

class TestClassesDefinition:
    """Tests for classification configuration."""
    
    def test_from_yaml_list_format(self, tmp_path):
        """Test loading YAML with list format."""
        config_content = """
- name: Category1
  description: First category
- name: Category2
  description: Second category
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        
        config = ClassesDefinition.from_yaml(config_file)
        assert len(config.classes) == 2
        assert config.classes[0].name == "Category1"
    
    def test_from_yaml_dict_format(self, tmp_path):
        """Test loading YAML with dict format."""
        config_content = """
classes:
  - name: Category1
    description: First category
  - name: Category2
    description: Second category
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        
        config = ClassesDefinition.from_yaml(config_file)
        assert len(config.classes) == 2
    
    def test_get_class_names(self):
        """Test extracting class names."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="A", description="A desc"),
            ClassDefinition(name="B", description="B desc"),
        ])
        assert config.get_class_names() == ["A", "B"]
    
    def test_format_for_prompt(self):
        """Test formatting for prompt inclusion."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="Test", description="Test description"),
        ])
        formatted = config.format_for_prompt()
        assert "Test" in formatted
        assert "Test description" in formatted


class TestResponseModel:
    """Tests for dynamic response model creation."""
    
    def test_valid_class(self):
        """Test that valid classes pass validation."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="ValidClass", description="desc"),
        ])
        Model = create_classification_response_model(config)
        
        response = Model(predicted_class="ValidClass", confidence=0.9)
        assert response.predicted_class == "ValidClass"
    
    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="ValidClass", description="desc"),
        ])
        Model = create_classification_response_model(config)
        
        response = Model(predicted_class="validclass", confidence=0.9)
        assert response.predicted_class == "ValidClass"
    
    def test_invalid_class_raises(self):
        """Test that invalid classes raise validation error."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="ValidClass", description="desc"),
        ])
        Model = create_classification_response_model(config)
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            Model(predicted_class="InvalidClass", confidence=0.9)



class TestLLMResponseParser:
    """Tests for LLM response parsing."""
    
    def test_extract_json_simple(self):
        """Test extracting JSON from simple response."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="Test", description="desc"),
        ])
        parser = LLMResponseParser(config)
        
        response = '{"predicted_class": "Test", "confidence": 0.9, "reasoning": "test"}'
        result = parser.extract_json(response)
        
        assert result is not None
        assert result["predicted_class"] == "Test"
    
    def test_extract_json_with_markdown(self):
        """Test extracting JSON from markdown code blocks."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="Test", description="desc"),
        ])
        parser = LLMResponseParser(config)
        
        response = '```json\n{"predicted_class": "Test", "confidence": 0.9}\n```'
        result = parser.extract_json(response)
        
        assert result is not None
        assert result["predicted_class"] == "Test"
    
    def test_extract_json_with_surrounding_text(self):
        """Test extracting JSON from text with surrounding content."""
        config = ClassesDefinition(classes=[
            ClassDefinition(name="Test", description="desc"),
        ])
        parser = LLMResponseParser(config)
        
        response = 'Here is my analysis: {"predicted_class": "Test", "confidence": 0.9} That is my answer.'
        result = parser.extract_json(response)
        
        assert result is not None
        assert result["predicted_class"] == "Test"



class TestPromptStrategies:
    """Tests for prompt strategies."""
    
    def test_list_strategies(self):
        """Test listing available strategies."""
        strategies = list_available_strategies()
        assert "direct" in strategies
        assert "cot" in strategies
        assert "defensive" in strategies
    
    def test_get_direct_strategy(self):
        """Test getting direct strategy."""
        strategy = get_prompt_strategy("direct")
        assert isinstance(strategy, DirectPromptStrategy)
        assert strategy.metadata.strategy_name == "direct"
    
    def test_get_cot_strategy(self):
        """Test getting chain-of-thought strategy."""
        strategy = get_prompt_strategy("cot")
        assert isinstance(strategy, ChainOfThoughtPromptStrategy)
    
    def test_invalid_strategy_raises(self):
        """Test that invalid strategy name raises error."""
        with pytest.raises(ValueError):
            get_prompt_strategy("nonexistent")
    
    def test_prompt_creation(self):
        """Test that prompts are created correctly."""
        strategy = get_prompt_strategy("direct")
        prompt = strategy.create_prompt("Class1: Description1\nClass2: Description2")
        
        # Should have messages
        messages = prompt.format_messages(
            class_definitions="test",
            file_content="test content"
        )
        assert len(messages) >= 2  # System and human messages


class TestFileOperations:
    """Tests for file operations."""
    
    def test_validate_empty_folder(self, tmp_path):
        """Test validation of empty folder."""
        ops = FileOperations(tmp_path)
        is_valid, error = ops.validate_base_folder()
        assert is_valid
        assert error == ""
    
    def test_validate_folder_with_subfolders(self, tmp_path):
        """Test that folder with subfolders fails validation."""
        (tmp_path / "subfolder").mkdir()
        
        ops = FileOperations(tmp_path)
        is_valid, error = ops.validate_base_folder()
        assert not is_valid
        assert "subfolders" in error
    
    def test_validate_nonexistent_folder(self, tmp_path):
        """Test that nonexistent folder fails validation."""
        ops = FileOperations(tmp_path / "nonexistent")
        is_valid, error = ops.validate_base_folder()
        assert not is_valid
        assert "does not exist" in error
    
    def test_get_text_files(self, tmp_path):
        """Test getting text files from folder."""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.md").write_text("content2")
        (tmp_path / "file3.pdf").write_bytes(b"binary")
        
        ops = FileOperations(tmp_path)
        files = list(ops.get_text_files())
        
        assert len(files) == 2
        names = {f.name for f in files}
        assert "file1.txt" in names
        assert "file2.md" in names
    
    def test_read_file(self, tmp_path):
        """Test reading file content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        ops = FileOperations(tmp_path)
        content, error = ops.read_file(test_file)
        
        assert content == "test content"
        assert error is None
    
    def test_ensure_class_folder(self, tmp_path):
        """Test creating class folders."""
        ops = FileOperations(tmp_path)
        folder, sanitized = ops.ensure_class_folder("TestClass")
        
        assert folder.exists()
        assert folder.name == "TestClass"
        assert not sanitized.was_modified
    
    def test_move_file(self, tmp_path):
        """Test moving file to class folder."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        ops = FileOperations(tmp_path)
        dest, success, message = ops.move_file(test_file, "Category")
        
        assert success
        assert dest.parent.name == "Category"
        assert not test_file.exists()
        assert dest.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
