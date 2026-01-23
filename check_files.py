#!/usr/bin/env python3
"""
File integrity checker
Check for syntax errors and encoding issues
"""
import os
import sys
from pathlib import Path
import py_compile


def check_python_file(file_path):
    """Check Python file for syntax errors"""
    try:
        py_compile.compile(file_path, doraise=True)
        return True, "OK"
    except Exception as e:
        return False, str(e)


def check_all_files():
    """Check all Python files in the project"""
    project_root = Path(__file__).parent
    app_dir = project_root / "app"

    print("=" * 60)
    print("Checking Project Files")
    print("=" * 60)

    errors = []
    success_count = 0

    # Get all Python files
    python_files = list(app_dir.glob("**/*.py"))

    for file_path in sorted(python_files):
        relative_path = file_path.relative_to(project_root)
        is_ok, message = check_python_file(file_path)

        if is_ok:
            print(f"✓ {relative_path}")
            success_count += 1
        else:
            print(f"✗ {relative_path}")
            print(f"  Error: {message}")
            errors.append((relative_path, message))

    print("\n" + "=" * 60)
    print(f"Results: {success_count} OK, {len(errors)} Errors")
    print("=" * 60)

    if errors:
        print("\nFiles with errors:")
        for file_path, error in errors:
            print(f"  - {file_path}")
            print(f"    {error[:100]}")
        return False

    return True


if __name__ == "__main__":
    success = check_all_files()
    sys.exit(0 if success else 1)
