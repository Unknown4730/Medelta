#!/usr/bin/env python
"""Run all experiments and write result artifacts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from meddelta.evaluation import run_full_evaluation

def main():
    run_full_evaluation()

if __name__ == '__main__':
    main()
