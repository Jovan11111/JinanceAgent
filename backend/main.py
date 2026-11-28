import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli_interface import CliInterface

if __name__ == "__main__":
    CliInterface().run()
