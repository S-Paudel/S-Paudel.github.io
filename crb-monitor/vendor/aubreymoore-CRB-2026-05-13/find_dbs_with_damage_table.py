import sqlite3
from pathlib import Path
from typing import List


def is_sqlite_db(file_path: Path) -> bool:
    """Check if a file is a valid SQLite database header-wise.

    Args:
        file_path (Path): Path to the file to check.

    Returns:
        bool: True if the file header matches SQLite 3 format, False otherwise.
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
            return header == b"SQLite format 3\x00"
    except (OSError, PermissionError):
        return False


def has_damage_table(db_path: Path) -> bool:
    """Check if a SQLite database contains a table named 'damage'.

    Args:
        db_path (Path): Path to the SQLite database file.

    Returns:
        bool: True if the 'damage' table exists, False otherwise.
    """
    try:
        # Open in read-only URI mode to prevent modifying files or creating locks
        uri = f"file:{db_path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='damage';"
            )
            return cursor.fetchone() is not None
    except (sqlite3.Error, OSError):
        return False


def find_damage_databases(search_path: Path) -> List[Path]:
    """Recursively search a directory for SQLite databases containing a 'damage' table.

    Args:
        search_path (Path): The root directory path to search.

    Returns:
        List[Path]: A list of Path objects for matching SQLite databases.
    """
    matching_dbs: List[Path] = []

    for file_path in search_path.rglob("*"):
        if file_path.is_file() and is_sqlite_db(file_path):
            if has_damage_table(file_path):
                matching_dbs.append(file_path)

    return matching_dbs


if __name__ == "__main__":
    desktop_dir = Path.home() / "Desktop"

    if not desktop_dir.exists():
        print(f"Error: Directory '{desktop_dir}' does not exist.")
    else:
        print(f"Searching for SQLite databases with a 'damage' table in:\n  {desktop_dir}\n")
        results = find_damage_databases(desktop_dir)

        if results:
            print(f"Found {len(results)} matching database(s):")
            for db in results:
                print(f"  - {db}")
        else:
            print("No matching SQLite databases found.")