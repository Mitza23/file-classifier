"""
File Operations Module
Handles safe file operations with path sanitization to prevent directory traversal attacks.
"""

import re
from pathlib import Path
from typing import List, Optional
import shutil


class FileOperationError(Exception):
    """Custom exception for file operation errors."""
    pass


def sanitize_folder_name(name: str) -> str:
    """
    Sanitize a folder name to prevent directory traversal attacks and ensure
    cross-platform compatibility.
    
    This is CRITICAL for security when the folder name comes from LLM output
    which may be compromised by prompt injection.
    
    Args:
        name: Raw folder name from LLM
        
    Returns:
        Sanitized folder name safe for filesystem operations
    """
    # Remove path separators and parent directory references
    name = name.replace('/', '_').replace('\\', '_')
    name = name.replace('..', '_')
    name = name.replace('~', '_')
    
    # Remove any other potentially dangerous characters
    # Keep alphanumeric, spaces, hyphens, underscores
    name = re.sub(r'[^\w\s\-]', '_', name)
    
    # Trim whitespace and limit length
    name = name.strip()[:100]
    
    # Ensure name is not empty after sanitization
    if not name:
        name = "Unknown"
    
    # Prevent reserved Windows names
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    if name.upper() in reserved_names:
        name = f"_{name}"
    
    return name


def validate_parent_folder(parent_path: Path) -> None:
    """
    Validate that the parent folder exists, is a directory, and contains no subfolders.
    
    Args:
        parent_path: Path to the parent folder
        
    Raises:
        FileOperationError: If validation fails
    """
    if not parent_path.exists():
        raise FileOperationError(f"Parent folder does not exist: {parent_path}")
    
    if not parent_path.is_dir():
        raise FileOperationError(f"Path is not a directory: {parent_path}")
    
    # Check for existing subdirectories
    subdirs = [item for item in parent_path.iterdir() if item.is_dir()]
    if subdirs:
        raise FileOperationError(
            f"Parent folder must not contain subdirectories. Found: {', '.join(d.name for d in subdirs)}"
        )


def get_text_files(parent_path: Path) -> List[Path]:
    """
    Get all text files in the parent folder (non-recursive).
    
    Args:
        parent_path: Path to the parent folder
        
    Returns:
        List of Path objects for text files
    """
    text_extensions = {'.txt', '.md', '.text', '.log', '.csv', '.json', '.xml', '.html', '.htm'}
    
    files = []
    for item in parent_path.iterdir():
        if item.is_file() and item.suffix.lower() in text_extensions:
            files.append(item)
    
    return files


def read_file_safely(file_path: Path) -> Optional[str]:
    """
    Safely read a text file with multiple encoding attempts.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File content as string, or None if reading failed
    """
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    
    # If all encodings fail, try reading as binary and decode with errors='ignore'
    try:
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')
    except Exception:
        return None


class FileOrganizer:
    """
    Handles safe file organization with sanitization and error handling.
    """
    
    def __init__(self, parent_path: Path, class_names: List[str]):
        """
        Initialize the file organizer.
        
        Args:
            parent_path: Path to the parent folder containing files
            class_names: List of valid class names for validation
        """
        self.parent_path = parent_path
        self.class_names = set(class_names)
        self.class_folders = {}  # Maps class name to Path object
        self.unclassified_folder = None
        
        # Validate parent folder
        validate_parent_folder(parent_path)
    
    def create_class_folders(self) -> None:
        """
        Create subfolders for each class and the unclassified folder.
        """
        # Create unclassified folder first
        unclassified_name = sanitize_folder_name("_Unclassified")
        self.unclassified_folder = self.parent_path / unclassified_name
        self.unclassified_folder.mkdir(exist_ok=True)
        
        # Create folders for each class
        for class_name in self.class_names:
            sanitized_name = sanitize_folder_name(class_name)
            folder_path = self.parent_path / sanitized_name
            folder_path.mkdir(exist_ok=True)
            self.class_folders[class_name] = folder_path
    
    def move_file(self, file_path: Path, predicted_class: str, is_error: bool = False) -> Path:
        """
        Move a file to the appropriate class folder with sanitization.
        
        Args:
            file_path: Path to the file to move
            predicted_class: Class name from classifier
            is_error: Whether classification resulted in error
            
        Returns:
            Path where the file was moved
        """
        # Determine destination folder
        if is_error or predicted_class not in self.class_names:
            dest_folder = self.unclassified_folder
        else:
            dest_folder = self.class_folders[predicted_class]
        
        # Handle filename conflicts
        dest_path = dest_folder / file_path.name
        if dest_path.exists():
            # Add counter to filename
            stem = file_path.stem
            suffix = file_path.suffix
            counter = 1
            while dest_path.exists():
                new_name = f"{stem}_{counter}{suffix}"
                dest_path = dest_folder / new_name
                counter += 1
        
        # Move the file
        try:
            shutil.move(str(file_path), str(dest_path))
            return dest_path
        except Exception as e:
            raise FileOperationError(f"Failed to move {file_path.name}: {str(e)}")
    
    def get_file_count(self) -> int:
        """Return the number of text files in the parent folder."""
        return len(get_text_files(self.parent_path))
