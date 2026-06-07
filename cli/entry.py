"""PyInstaller entry point — avoids relative import issues."""
from pacific_cli.__main__ import main

if __name__ == "__main__":
    main()
