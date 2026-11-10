"""Keep connector/session secrets in the Windows user's private profile."""
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ['LOCALAPPDATA'])/'StudyDesk' if os.name=='nt' and os.environ.get('LOCALAPPDATA') else ROOT/'.home'
