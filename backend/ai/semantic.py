"""
Meaning-based article matching with a small sentence-embedding model.

The text classifier in article_matcher.py learns from word and letter
patterns, so it only recognises phrasings close to its examples. This module
compares *meaning*: "the underside of my notebook is scorching" lands next to
"laptop is overheating" although they share no words.

Model: BAAI/bge-small-en-v1.5 (MIT licence) run with fastembed (Apache-2.0) on
ONNX Runtime — free, no PyTorch, no API calls. It is downloaded once (~65 MB)
into ai/training/.model_cache/fastembed and runs offline afterwards. If the
package or model is unavailable, every function here returns nothing and the
chatbot simply uses the text classifier alone.
"""

import hashlib
import logging
import os
import threading
from typing import Dict, List, Optional, Sequence

from ai.intent_model import TRAINING_DIR

logger = logging.getLogger("relaydesk.semantic")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
CACHE_DIR = os.path.join(TRAINING_DIR, ".model_cache", "fastembed")
# Set RELAYDESK_SEMANTIC=0 to switch the meaning model off (e.g. on a small server)
ENABLED = os.environ.get("RELAYDESK_SEMANTIC", "1") != "0"

_model = None
_model_failed = False
_lock = threading.Lock()
_index: Dict[str, "_ArticleIndex"] = {}


def _load_model():
    global _model, _model_failed
    if _model is not None or _model_failed or not ENABLED:
        return _model
    with _lock:
        if _model is None and not _model_failed:
            try:
                from fastembed import TextEmbedding
                os.makedirs(CACHE_DIR, exist_ok=True)
                _model = TextEmbedding(MODEL_NAME, cache_dir=CACHE_DIR)
            except Exception as exc:  # not installed, no network for the first download, ...
                logger.warning("Meaning model unavailable, using the text classifier only: %s", exc)
                _model_failed = True
    return _model


def _embed(texts: List[str]):
    import numpy as np
    vectors = np.array(list(_load_model().embed(texts)), dtype="float32")
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class _ArticleIndex:
    """Embeddings of every training text of every article (cached on disk)."""

    def __init__(self, articles: Sequence[Dict], texts_by_article: Dict[int, List[str]], key: str):
        import numpy as np
        self.owner: List[int] = []
        texts: List[str] = []
        for art in articles:
            for text in texts_by_article.get(art["id"], []):
                texts.append(text)
                self.owner.append(art["id"])
        path = os.path.join(CACHE_DIR, f"articles-{key[:16]}.npy")
        vectors = None
        if os.path.exists(path):
            vectors = np.load(path)  # our own file, written below
            if vectors.shape[0] != len(texts):
                vectors = None
        if vectors is None:
            vectors = _embed(texts)
            for old in os.listdir(CACHE_DIR):
                if old.startswith("articles-") and old.endswith(".npy"):
                    os.remove(os.path.join(CACHE_DIR, old))
            np.save(path, vectors)
        self.vectors = vectors
        self.owner_array = np.array(self.owner)

    def similarities(self, text: str) -> Dict[int, float]:
        """Best cosine similarity between `text` and each article's examples."""
        import numpy as np
        sims = self.vectors @ _embed([text])[0]
        best: Dict[int, float] = {}
        for article_id in np.unique(self.owner_array):
            best[int(article_id)] = float(sims[self.owner_array == article_id].max())
        return best


def similarities(text: str, articles: Sequence[Dict], texts_by_article: Dict[int, List[str]]) -> Optional[Dict[int, float]]:
    """{article id: meaning similarity 0-1} or None when the model is unavailable."""
    if not articles or _load_model() is None:
        return None
    digest = hashlib.sha256(MODEL_NAME.encode())
    for art in sorted(articles, key=lambda a: a["id"]):
        digest.update(repr((art["id"], texts_by_article.get(art["id"], []))).encode())
    key = digest.hexdigest()
    with _lock:
        index = _index.get(key)
        if index is None:
            index = _ArticleIndex(articles, texts_by_article, key)
            _index.clear()
            _index[key] = index
    return index.similarities(text)
