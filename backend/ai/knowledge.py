"""
Knowledge retrieval for the support chatbot.

Ranks published knowledge-base articles against the conversation with BM25
(the standard lexical ranking function behind most search engines), then
adjusts each score by how often that article actually fixed users' problems.

Only *published* articles are searchable. Fixes learned from resolved tickets
enter the knowledge base as drafts and become searchable once a staff member
approves them, so one user's ticket details are never shown to another user.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Sequence

from ai.deflector import STOPWORDS, normalize_query

_TOKEN = re.compile(r"[a-z0-9]+")

# Title and tags describe what an article is about, so they count extra
_FIELD_WEIGHTS = {"title": 3, "tags": 2, "body": 1}


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> List[str]:
    return [_stem(t) for t in _TOKEN.findall(normalize_query(text or "")) if t not in STOPWORDS and len(t) > 1]


@dataclass
class Hit:
    article: Dict
    score: float


def feedback_multiplier(helpful: int, not_helpful: int) -> float:
    """Ranking boost between 0.6x and 1.4x from the article's fix rate.
    Laplace smoothing keeps it at 1.0x with no votes, so a couple of votes
    only nudge the ranking and a consistent track record moves it far."""
    rate = (helpful + 1) / (helpful + not_helpful + 2)
    return 0.6 + 0.8 * rate


class KnowledgeIndex:
    def __init__(self, articles: Sequence[Dict], k1: float = 1.5, b: float = 0.75):
        self.articles = list(articles)
        self.k1, self.b = k1, b
        self.doc_terms: List[Counter] = []
        for art in self.articles:
            terms: Counter = Counter()
            for field, weight in _FIELD_WEIGHTS.items():
                for tok in tokenize(art.get(field) or ""):
                    terms[tok] += weight
            self.doc_terms.append(terms)
        self.doc_len = [sum(t.values()) for t in self.doc_terms]
        self.avg_len = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        df: Counter = Counter()
        for terms in self.doc_terms:
            df.update(terms.keys())
        n = len(self.articles)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def search(self, query: str, limit: int = 3, min_score: float = 1.0) -> List[Hit]:
        q_terms = set(tokenize(query))
        if not q_terms or not self.articles:
            return []
        hits = []
        for art, terms, length in zip(self.articles, self.doc_terms, self.doc_len):
            score = 0.0
            for term in q_terms:
                tf = terms.get(term)
                if not tf:
                    continue
                norm = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1)))
                score += self.idf[term] * norm
            if score <= 0:
                continue
            score *= feedback_multiplier(art.get("helpful_count") or 0, art.get("not_helpful_count") or 0)
            if score >= min_score:
                hits.append(Hit(art, score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]


def conversation_query(message: str, history: Sequence[Dict], max_user_turns: int = 3) -> str:
    """The latest message alone is often just "still not working"; include
    the user's recent turns so the search keeps the original problem."""
    user_turns = [
        (m.get("text") or m.get("body") or "")
        for m in history
        if m.get("sender") == "user" or m.get("sender_type") in ("user", "enduser")
    ]
    recent = user_turns[-max_user_turns:]
    if not recent or recent[-1].strip() != message.strip():
        recent.append(message)
    return " ".join(recent)
