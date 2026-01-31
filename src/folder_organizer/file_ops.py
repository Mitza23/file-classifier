"""
File operations module.

Handles safe file operations with cross-platform compatibility,
input sanitization, and directory traversal protection.
"""

import re
import shutil
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field, field_validator


class SanitizedPath(BaseModel):
    """A validated and sanitized path component."""
    
    value: str = Field(..., description="The sanitized path component")
    original: str = Field(..., description="The original input before sanitization")
    was_modified: bool = Field(default=False, description="Whether sanitization changed the value")
    
    @classmethod
    def from_string(cls, name: str) -> "SanitizedPath":
        """Create a sanitized path from a string."""
        original = name
        sanitized = cls._sanitize(name)
        return cls(
            value=sanitized,
            original=original,
            was_modified=(sanitized != original)
        )
    
    @staticmethod
    def _sanitize(name: str) -> str:
        """
        Sanitize a path component to prevent directory traversal and other attacks.
        
        Security measures:
        1. Remove path separators (/ and \)
        2. Remove path traversal patterns (..)
        3. Remove null bytes
        4. Remove leading/trailing whitespace and dots
        5. Replace invalid filesystem characters
        6. Limit length
        """
        if not name:
            return "_Empty"
        
        sanitized = name
        
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        
        # Remove path separators
        sanitized = sanitized.replace("/", "_")
        sanitized = sanitized.replace("\\", "_")
        
        # Remove path traversal patterns
        sanitized = sanitized.replace("..", "_")
        
        # Remove characters invalid on Windows/Linux filesystems
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            sanitized = sanitized.replace(char, "_")
        
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # Strip leading/trailing whitespace and dots
        sanitized = sanitized.strip(". \t\n\r")
        
        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Limit length (255 is common max for most filesystems)
        max_length = 200
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        # Ensure we have something valid
        if not sanitized:
            sanitized = "_Sanitized"
        
        # Avoid reserved names on Windows
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if sanitized.upper() in reserved_names:
            sanitized = f"_{sanitized}"
        
        return sanitized


class FileOperations:
    """
    Safe file operations with cross-platform support.
    
    Uses pathlib for all path operations to ensure Windows/Linux compatibility.
    Implements security measures to prevent directory traversal attacks.
    """
    
    def __init__(self, base_folder: Path, quarantine_folder: str = "_Unclassified"):
        """
        Initialize file operations.
        
        Args:
            base_folder: The parent folder containing files to organize
            quarantine_folder: Name of the folder for unclassified files
        """
        self.base_folder = Path(base_folder).resolve()
        self.quarantine_folder = quarantine_folder
        self._created_folders: set[str] = set()
    
    def validate_base_folder(self) -> tuple[bool, str]:
        """
        Validate the base folder meets requirements.
        
        Requirements:
        - Folder must exist
        - Must be a directory
        - Must not contain any subfolders
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.base_folder.exists():
            return False, f"Folder does not exist: {self.base_folder}"
        
        if not self.base_folder.is_dir():
            return False, f"Path is not a directory: {self.base_folder}"
        
        # Check for existing subfolders
        subfolders = [p for p in self.base_folder.iterdir() if p.is_dir()]
        if subfolders:
            folder_names = [f.name for f in subfolders[:5]]  # Show first 5
            return False, (
                f"Folder contains existing subfolders: {', '.join(folder_names)}"
                + (" ..." if len(subfolders) > 5 else "")
                + ". The parent folder must not contain any pre-existing subfolders."
            )
        
        return True, ""
    
    def get_text_files(self) -> Iterator[Path]:
        """
        Yield all text files in the base folder.
        
        Only returns files directly in the base folder (not recursive).
        """
        text_extensions = {'.txt', '.md', '.text', '.log', '.csv', '.json', '.xml', '.html', '.htm'}
        
        for path in self.base_folder.iterdir():
            if path.is_file():
                # Check extension
                if path.suffix.lower() in text_extensions:
                    yield path
                # Also include files without extension that might be text
                elif path.suffix == '':
                    # Try to detect if it's text by reading first few bytes
                    try:
                        with open(path, 'rb') as f:
                            sample = f.read(512)
                            # Simple heuristic: check if it's mostly printable ASCII
                            if sample and all(b < 128 for b in sample):
                                yield path
                    except (IOError, OSError):
                        pass
    
    def get_all_files(self) -> Iterator[Path]:
        """Yield all files in the base folder."""
        for path in self.base_folder.iterdir():
            if path.is_file():
                yield path
    
    def read_file(self, filepath: Path) -> tuple[Optional[str], Optional[str]]:
        """
        Safely read a text file.
        
        Returns:
            Tuple of (content, error_message)
        """
        try:
            # Try UTF-8 first
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read(), None
        except UnicodeDecodeError:
            try:
                # Fall back to latin-1 which accepts any byte sequence
                with open(filepath, 'r', encoding='latin-1') as f:
                    return f.read(), None
            except Exception as e:
                return None, f"Failed to read file: {e}"
        except Exception as e:
            return None, f"Failed to read file: {e}"
    
    def ensure_class_folder(self, class_name: str) -> tuple[Path, SanitizedPath]:
        """
        Create a folder for a class if it doesn't exist.
        
        Args:
            class_name: The class name (will be sanitized)
            
        Returns:
            Tuple of (folder_path, sanitized_info)
        """
        sanitized = SanitizedPath.from_string(class_name)
        folder_path = self.base_folder / sanitized.value
        
        if sanitized.value not in self._created_folders:
            folder_path.mkdir(exist_ok=True)
            self._created_folders.add(sanitized.value)
        
        return folder_path, sanitized
    
    def ensure_quarantine_folder(self) -> Path:
        """Create the quarantine folder for unclassified files."""
        folder_path, _ = self.ensure_class_folder(self.quarantine_folder)
        return folder_path
    
    def move_file(self, source: Path, class_name: str) -> tuple[Path, bool, str]:
        """
        Move a file to its class folder.
        
        Args:
            source: Path to the source file
            class_name: Target class name (will be sanitized)
            
        Returns:
            Tuple of (destination_path, success, message)
        """
        try:
            # Ensure source is within base folder (prevent any path tricks)
            source_resolved = source.resolve()
            if not str(source_resolved).startswith(str(self.base_folder)):
                return source, False, "Source file is outside base folder"
            
            # Create destination folder
            dest_folder, sanitized = self.ensure_class_folder(class_name)
            
            # Handle filename conflicts
            dest_path = dest_folder / source.name
            if dest_path.exists():
                # Add numeric suffix
                stem = source.stem
                suffix = source.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = dest_folder / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Move the file
            shutil.move(str(source), str(dest_path))
            
            message = ""
            if sanitized.was_modified:
                message = f"Class name was sanitized: '{sanitized.original}' -> '{sanitized.value}'"
            
            return dest_path, True, message
            
        except Exception as e:
            return source, False, f"Failed to move file: {e}"
    
    def move_to_quarantine(self, source: Path, reason: str = "") -> tuple[Path, bool, str]:
        """Move a file to the quarantine folder."""
        return self.move_file(source, self.quarantine_folder)
    
    def get_folder_summary(self) -> dict[str, int]:
        """Get a summary of files per folder after organization."""
        summary = {}
        for folder in self.base_folder.iterdir():
            if folder.is_dir():
                file_count = sum(1 for f in folder.iterdir() if f.is_file())
                summary[folder.name] = file_count
        return summary


def is_safe_path(base: Path, path: Path) -> bool:
    """Check if a path is safely within the base directory."""
    try:
        base_resolved = base.resolve()
        path_resolved = path.resolve()
        return str(path_resolved).startswith(str(base_resolved))
    except (ValueError, OSError):
        return False
