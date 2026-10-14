#!/usr/bin/env python
"""Generate synthetic dataset and embeddings."""
import sys
from pathlib import Path
# Add project root to path for script execution
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from meddelta.generate_data import generate_corpus, save_corpus
from meddelta.embed import build_embeddings
from meddelta.config import GENERATED_DIR

def main():
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    observations, queries = generate_corpus()
    save_corpus(observations, queries)
    print(f'Generated {len(observations)} observations and {len(queries)} queries')
    build_embeddings(observations)
    print('Embeddings built and saved')

if __name__ == '__main__':
    main()
