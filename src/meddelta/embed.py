from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from meddelta.config import GENERATED_DIR, MODEL_NAME
from meddelta.models import Observation

_ENCODER_TYPE = None
_ENCODER_MODEL = None
_QUERY_CACHE = {}


def build_embeddings(observations: list[Observation]) -> None:
    global _ENCODER_TYPE, _ENCODER_MODEL
    texts = [obs.note_text for obs in observations]
    
    try:
        from sentence_transformers import SentenceTransformer
        _ENCODER_MODEL = SentenceTransformer(MODEL_NAME)
        _ENCODER_TYPE = 'sentence-transformers'
        matrix = _ENCODER_MODEL.encode(texts, convert_to_numpy=True)
    except (ImportError, OSError):
        from sklearn.feature_extraction.text import TfidfVectorizer
        _ENCODER_MODEL = TfidfVectorizer(max_features=384)
        _ENCODER_TYPE = 'tfidf'
        matrix = _ENCODER_MODEL.fit_transform(texts).toarray().astype(np.float32)

    # Normalize to unit length
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    matrix = (matrix / norms).astype(np.float32)
    
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    np.save(GENERATED_DIR / "embeddings.npy", matrix)
    
    record_ids = [obs.record_id for obs in observations]
    
    manifest_path = GENERATED_DIR / "corpus_manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
    manifest["encoder_type"] = _ENCODER_TYPE
    manifest["record_ids"] = record_ids
    manifest["record_id_to_index"] = {rid: idx for idx, rid in enumerate(record_ids)}
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def load_embeddings() -> tuple[np.ndarray, list[str], dict[str, int]]:
    matrix = np.load(GENERATED_DIR / "embeddings.npy")
    with open(GENERATED_DIR / "corpus_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return matrix, manifest["record_ids"], manifest.get("record_id_to_index", {rid: i for i, rid in enumerate(manifest["record_ids"])})


def encode_query(text: str) -> np.ndarray:
    global _ENCODER_TYPE, _ENCODER_MODEL, _QUERY_CACHE
    
    if text in _QUERY_CACHE:
        return _QUERY_CACHE[text]
        
    if _ENCODER_MODEL is None:
        with open(GENERATED_DIR / "corpus_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
            _ENCODER_TYPE = manifest.get("encoder_type")
            if _ENCODER_TYPE == 'sentence-transformers':
                from sentence_transformers import SentenceTransformer
                _ENCODER_MODEL = SentenceTransformer(MODEL_NAME)
            else:
                raise RuntimeError("TF-IDF vectorizer must be built in this session to encode queries.")
                
    if _ENCODER_TYPE == 'sentence-transformers':
        vec = _ENCODER_MODEL.encode([text], convert_to_numpy=True)[0]
    else:
        vec = _ENCODER_MODEL.transform([text]).toarray()[0].astype(np.float32)
        
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
        
    _QUERY_CACHE[text] = vec
    return vec


def cosine_similarity_scores(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return matrix @ query_vec
