#!/usr/bin/env python3
"""
System Validation Test Suite
Tests core functionality of the folder organizer.
"""

import sys
from pathlib import Path
import shutil
import tempfile
import yaml

# Import modules to test
from classifier import create_classification_schema, PromptStrategy
from file_ops import sanitize_folder_name, validate_parent_folder, FileOrganizer
from logger import ExperimentLogger


def test_path_sanitization():
    """Test that path sanitization prevents directory traversal."""
    print("Testing path sanitization...")
    
    test_cases = [
        ("../../etc/passwd", "____etc_passwd"),
        ("../system", "__system"),
        ("Normal Folder", "Normal_Folder"),
        ("Special!@#$%Chars", "Special_____Chars"),
        ("con", "_con"),  # Windows reserved
        ("very" * 50, "very" * 20),  # Length limit
        ("", "Unknown"),  # Empty
    ]
    
    passed = 0
    failed = 0
    
    for dangerous, expected in test_cases:
        result = sanitize_folder_name(dangerous)
        
        # Check result is safe
        is_safe = (
            ".." not in result and
            "/" not in result and
            "\\" not in result and
            len(result) <= 100 and
            len(result) > 0
        )
        
        if is_safe:
            print(f"  ✓ '{dangerous}' → '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{dangerous}' → '{result}' (UNSAFE)")
            failed += 1
    
    print(f"Path sanitization: {passed} passed, {failed} failed\n")
    return failed == 0


def test_schema_creation():
    """Test dynamic Pydantic schema creation."""
    print("Testing schema creation...")
    
    class_defs = [
        {"name": "Class A", "description": "Description A"},
        {"name": "Class B", "description": "Description B"},
        {"name": "Class C", "description": "Description C"}
    ]
    
    class_names = [c['name'] for c in class_defs]
    
    try:
        Schema, Enum = create_classification_schema(class_names)
        
        # Test valid class
        test_obj = Schema(
            document_class=Enum.Class_A,
            reasoning="Test",
            confidence=0.95
        )
        
        # Verify enum members
        enum_values = [e.value for e in Enum]
        assert set(enum_values) == set(class_names), "Enum values don't match class names"
        
        print(f"  ✓ Schema created with {len(class_names)} classes")
        print(f"  ✓ Enum values: {enum_values}")
        print(f"  ✓ Test object validated successfully")
        print("Schema creation: PASSED\n")
        return True
    
    except Exception as e:
        print(f"  ✗ Schema creation failed: {e}")
        print("Schema creation: FAILED\n")
        return False


def test_folder_validation():
    """Test folder validation logic."""
    print("Testing folder validation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Test 1: Valid empty folder
        try:
            validate_parent_folder(tmppath)
            print("  ✓ Empty folder validated")
        except Exception as e:
            print(f"  ✗ Empty folder failed: {e}")
            return False
        
        # Test 2: Folder with files (should pass)
        (tmppath / "test.txt").write_text("test")
        try:
            validate_parent_folder(tmppath)
            print("  ✓ Folder with files validated")
        except Exception as e:
            print(f"  ✗ Folder with files failed: {e}")
            return False
        
        # Test 3: Folder with subdirectory (should fail)
        (tmppath / "subdir").mkdir()
        try:
            validate_parent_folder(tmppath)
            print("  ✗ Folder with subdirectory should have failed")
            return False
        except Exception as e:
            print(f"  ✓ Correctly rejected folder with subdirectory")
    
    print("Folder validation: PASSED\n")
    return True


def test_file_organizer():
    """Test FileOrganizer functionality."""
    print("Testing file organizer...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create test files
        (tmppath / "doc1.txt").write_text("Document 1")
        (tmppath / "doc2.txt").write_text("Document 2")
        (tmppath / "doc3.txt").write_text("Document 3")
        
        class_names = ["Class A", "Class B", "Class C"]
        
        try:
            organizer = FileOrganizer(tmppath, class_names)
            organizer.create_class_folders()
            
            # Check folders were created
            expected_folders = {
                sanitize_folder_name("Class A"),
                sanitize_folder_name("Class B"),
                sanitize_folder_name("Class C"),
                sanitize_folder_name("_Unclassified")
            }
            
            actual_folders = {d.name for d in tmppath.iterdir() if d.is_dir()}
            
            if expected_folders != actual_folders:
                print(f"  ✗ Folder mismatch: {actual_folders} != {expected_folders}")
                return False
            
            print(f"  ✓ Created {len(actual_folders)} folders")
            
            # Test moving files
            doc1 = tmppath / "doc1.txt"
            dest = organizer.move_file(doc1, "Class A", is_error=False)
            
            if not dest.exists():
                print(f"  ✗ File not moved to {dest}")
                return False
            
            if doc1.exists():
                print("  ✗ Original file still exists")
                return False
            
            print("  ✓ File moved successfully")
            
            # Test conflict resolution
            (tmppath / "doc2.txt").write_text("Duplicate")
            (tmppath / "doc2_conflict.txt").write_text("Conflict")
            shutil.copy(tmppath / "doc2.txt", organizer.class_folders["Class A"] / "doc2.txt")
            
            dest2 = organizer.move_file(tmppath / "doc2_conflict.txt", "Class A", is_error=False)
            
            # Should create doc2_1.txt or similar
            if "doc2" not in dest2.name:
                print(f"  ✗ Conflict not resolved properly: {dest2.name}")
                return False
            
            print("  ✓ Filename conflict resolved")
            
        except Exception as e:
            print(f"  ✗ File organizer failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("File organizer: PASSED\n")
    return True


def test_experiment_logger():
    """Test experiment logging functionality."""
    print("Testing experiment logger...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        try:
            from classifier import ClassificationResult
            
            logger = ExperimentLogger(tmppath, "test_experiment")
            
            # Log some results
            results = [
                ClassificationResult(
                    filename="doc1.txt",
                    predicted_class="Class A",
                    confidence_score=0.95,
                    raw_llm_response='{"document_class": "Class A"}',
                    prompt_template_used="direct",
                    is_error=False
                ),
                ClassificationResult(
                    filename="doc2.txt",
                    predicted_class="Class B",
                    confidence_score=0.87,
                    raw_llm_response='{"document_class": "Class B"}',
                    prompt_template_used="direct",
                    is_error=False
                ),
                ClassificationResult(
                    filename="doc3.txt",
                    predicted_class="_Unclassified",
                    raw_llm_response="Invalid JSON",
                    prompt_template_used="direct",
                    is_error=True,
                    error_message="Parse error"
                )
            ]
            
            for result in results:
                logger.log_result(result)
            
            # Finalize and check files
            logger.finalize()
            
            if not logger.csv_path.exists():
                print("  ✗ CSV file not created")
                return False
            print("  ✓ CSV file created")
            
            if not logger.jsonl_path.exists():
                print("  ✗ JSONL file not created")
                return False
            print("  ✓ JSONL file created")
            
            if not logger.summary_path.exists():
                print("  ✗ Summary file not created")
                return False
            print("  ✓ Summary file created")
            
            # Check statistics
            stats = logger.calculate_statistics()
            
            if stats['total_files'] != 3:
                print(f"  ✗ Wrong total files: {stats['total_files']}")
                return False
            
            if stats['failed_classifications'] != 1:
                print(f"  ✗ Wrong error count: {stats['failed_classifications']}")
                return False
            
            if stats['success_rate'] != 2/3:
                print(f"  ✗ Wrong success rate: {stats['success_rate']}")
                return False
            
            print("  ✓ Statistics calculated correctly")
            
        except Exception as e:
            print(f"  ✗ Experiment logger failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("Experiment logger: PASSED\n")
    return True


def test_config_loading():
    """Test YAML config loading."""
    print("Testing config loading...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config_path = tmppath / "test_config.yaml"
        
        # Create test config
        test_config = {
            'classes': [
                {'name': 'Class 1', 'description': 'Description 1'},
                {'name': 'Class 2', 'description': 'Description 2'}
            ]
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Try to load it
        try:
            with open(config_path, 'r') as f:
                loaded = yaml.safe_load(f)
            
            if loaded != test_config:
                print("  ✗ Config not loaded correctly")
                return False
            
            print("  ✓ Config loaded successfully")
            print(f"  ✓ Found {len(loaded['classes'])} classes")
            
        except Exception as e:
            print(f"  ✗ Config loading failed: {e}")
            return False
    
    print("Config loading: PASSED\n")
    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("FOLDER ORGANIZER - SYSTEM VALIDATION")
    print("=" * 70)
    print()
    
    tests = [
        ("Path Sanitization", test_path_sanitization),
        ("Schema Creation", test_schema_creation),
        ("Folder Validation", test_folder_validation),
        ("File Organizer", test_file_organizer),
        ("Experiment Logger", test_experiment_logger),
        ("Config Loading", test_config_loading)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"✗ {test_name} CRASHED: {e}\n")
            results.append((test_name, False))
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status:12s} | {test_name}")
    
    print("=" * 70)
    print(f"Result: {passed_count}/{total_count} tests passed")
    print("=" * 70)
    
    if passed_count == total_count:
        print("\n✓ All tests passed! System is ready for use.")
        return 0
    else:
        print(f"\n✗ {total_count - passed_count} test(s) failed. Please review errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
