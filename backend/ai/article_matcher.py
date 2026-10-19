"""
Article matcher: a text classifier that learns which knowledge-base article
answers a user's message (free and offline — scikit-learn, like intent_model).

Each published article is one class. It is trained on the article's title,
tags and opening sentence, plus the example user messages for that article
in ai/training/articles.json, with misspelt copies so typos still match.
Word n-grams capture phrasing ("second screen"), character n-grams handle
typos and word forms ("charing", "chargin").

Keyword scoring (deflector._score_article) only sees exact words; this model
recognises new wordings of a known problem ("the base of my laptop is
burning hot" → overheating). Articles staff add or approve later are learned
from their title, tags and text — add example messages for them to
articles.json to make them easier to find.
"""

import hashlib
import json
import os
import random
import re
import threading
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ai import semantic
from ai.deflector import expand_related
from ai.intent_model import TRAINING_DIR, build_pipeline, make_typo

ARTICLES_FILE = os.path.join(TRAINING_DIR, "articles.json")
TYPO_COPIES = 2
SEMANTIC_WEIGHT = 0.5  # share of the meaning model in the blended probability
SEMANTIC_TEMPERATURE = 0.02  # lower = the closest-meaning article dominates more
# The meaning model always finds a "closest" article, even for "what's the lunch menu".
# Real IT problems reach a similarity of ~0.8+; unrelated messages stay near 0.6-0.7.
# Its say ramps from nothing at SEMANTIC_FLOOR to full weight at SEMANTIC_FULL.
SEMANTIC_FLOOR = 0.72
SEMANTIC_FULL = 0.80


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def _load_examples() -> Dict[str, List[str]]:
    if not os.path.exists(ARTICLES_FILE):
        return {}
    with open(ARTICLES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return {_title_key(title): examples for title, examples in data.items() if not title.startswith("_")}


def _article_texts(article: Dict, examples: Dict[str, List[str]]) -> List[str]:
    body = (article.get("body") or "").strip()
    texts = [article.get("title") or "", article.get("tags") or "", body.split("\n", 1)[0]]
    texts += examples.get(_title_key(article.get("title")), [])
    # Same related-word expansion as at question time (deflector.matcher_ranking)
    return [expand_related(t) for t in texts if t.strip()]


class ArticleMatcher:
    def __init__(self, articles: Sequence[Dict]):
        examples = _load_examples()
        rng = random.Random(17)
        texts, labels = [], []
        self.articles = {art["id"]: art for art in articles}
        for art in articles:
            for text in _article_texts(art, examples):
                texts.append(text)
                labels.append(art["id"])
                for _ in range(TYPO_COPIES):
                    texts.append(make_typo(text, rng))
                    labels.append(art["id"])
        self.pipeline = build_pipeline().fit(texts, labels)
        self.labels = list(self.pipeline.classes_)
        # Plain sentences for the meaning model (no tag lists, no added topic words)
        self.sentences = {
            art["id"]: [t for t in [art.get("title") or "", (art.get("body") or "").strip().split("\n", 1)[0]]
                        + examples.get(_title_key(art.get("title")), []) if t.strip()]
            for art in articles
        }

    def ranking(self, text: str, limit: int = 5, plain_text: Optional[str] = None) -> List[Tuple[Dict, float]]:
        """The most likely articles for `text` with their probabilities, best first.
        With the meaning model available, its view of `plain_text` (the message
        without added topic words) is blended in — see SEMANTIC_WEIGHT."""
        probabilities = self.pipeline.predict_proba([text])[0]
        sims = semantic.similarities(plain_text or text, list(self.articles.values()), self.sentences)
        if sims:
            raw = np.array([sims.get(i, 0.0) for i in self.labels])
            strength = min(max((raw.max() - SEMANTIC_FLOOR) / (SEMANTIC_FULL - SEMANTIC_FLOOR), 0.0), 1.0)
            if strength > 0:
                scaled = raw / SEMANTIC_TEMPERATURE
                meaning = np.exp(scaled - scaled.max())
                meaning /= meaning.sum()
                weight = SEMANTIC_WEIGHT * strength
                probabilities = (1 - weight) * probabilities + weight * meaning
        order = probabilities.argsort()[::-1][:limit]
        return [(self.articles[self.labels[i]], float(probabilities[i])) for i in order]


_lock = threading.Lock()
_cache: Dict[str, ArticleMatcher] = {}


def _fingerprint(articles: Sequence[Dict]) -> str:
    digest = hashlib.sha256()
    for art in sorted(articles, key=lambda a: a["id"]):
        digest.update(f"{art['id']}\x1f{art.get('title')}\x1f{art.get('tags')}\x1f{art.get('body')}\x1e".encode())
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, "rb") as f:
            digest.update(f.read())
    from ai.deflector import RELATED_TERMS_FILE
    if os.path.exists(RELATED_TERMS_FILE):
        with open(RELATED_TERMS_FILE, "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()


def article_matcher(articles: Sequence[Dict]) -> Optional[ArticleMatcher]:
    """The matcher for this set of published articles, trained once and
    reused until an article is added, edited or removed."""
    if len(articles) < 2:
        return None
    key = _fingerprint(articles)
    with _lock:
        matcher = _cache.get(key)
        if matcher is None:
            matcher = ArticleMatcher(articles)
            _cache.clear()  # only the current knowledge base is needed
            _cache[key] = matcher
    return matcher
