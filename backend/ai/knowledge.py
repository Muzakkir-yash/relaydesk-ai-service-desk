"""
Knowledge retrieval for the support chatbot.

Ranks published knowledge-base articles against the conversation with BM25
(the standard lexical ranking function behind most search engines), then
adjusts each score by how often that article actually fixed users' problems.

Only *published* articles are searchable. Fixes learned from resolved tickets
enter the knowledge base as drafts and become searchable once a staff member
approves them, so one user's ticket details are never shown to another user.
"""


import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Sequence

from ai.deflector import IT_PROBLEM_KEYWORDS, STOPWORDS, normalize_query

_TOKEN = re.compile(r"[a-z0-9]+")
_TRAINING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "training")

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


@lru_cache(maxsize=1)
def _training_words() -> Counter:
    """How often each word appears in the chatbot's training data, related
    words and IT keywords — the vocabulary typos are corrected towards."""
    words: Counter = Counter()
    for name in ("intents.json", "categories.json", "articles.json", "related_terms.json"):
        path = os.path.join(_TRAINING_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for label, examples in json.load(f).items():
                if label.startswith("_"):
                    continue
                words.update(_TOKEN.findall(label.lower()))
                for example in examples:
                    words.update(_TOKEN.findall(example.lower()))
    for keyword in IT_PROBLEM_KEYWORDS:
        words.update(_TOKEN.findall(keyword))
    common = os.path.join(_TRAINING_DIR, "common_words.txt")
    if os.path.exists(common):
        with open(common, encoding="utf-8") as f:
            for line in f:
                if not line.startswith("#"):
                    words.update(_TOKEN.findall(line.lower()))
    return words


_KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
_KEY_POS = {ch: (r, c) for r, row in enumerate(_KEY_ROWS) for c, ch in enumerate(row)}


def _near_keys(a: str, b: str) -> bool:
    if a not in _KEY_POS or b not in _KEY_POS:
        return False
    (r1, c1), (r2, c2) = _KEY_POS[a], _KEY_POS[b]
    return abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1


def _edit_distance(a: str, b: str, limit: int) -> float:
    """Damerau-Levenshtein distance (a swapped pair counts as one mistake);
    hitting a neighbouring key costs a little less than any other letter.
    Gives up early (returns limit + 1) once the distance must exceed `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cost = 0
            else:
                cost = 0.9 if _near_keys(a[i - 1], b[j - 1]) else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


class _Speller:
    def __init__(self, counts: Counter, english: frozenset = frozenset()):
        self.counts = counts
        self.english = english  # real words to leave alone, never used as corrections
        self.by_length: Dict[int, List[str]] = {}
        for word in counts:
            if word.isalpha() and len(word) >= 2:
                self.by_length.setdefault(len(word), []).append(word)

    def correct(self, word: str) -> str:
        if len(word) < 4 or word in self.counts or word in self.english:
            return word
        # A known word with an ending ("pieces", "crashed", "printing") is spelt right
        for ending in ("es", "s", "ed", "d", "ing", "ly", "er"):
            stem = word[: -len(ending)]
            if word.endswith(ending) and (stem in self.counts or stem in self.english) and len(stem) >= 3:
                return word
        # Two words typed together: "digitkey" -> "digit key"
        for i in range(2, len(word) - 1):
            left, right = word[:i], word[i:]
            if self.counts.get(left, 0) >= 2 and self.counts.get(right, 0) >= 2 and min(len(left), len(right)) >= 3:
                return f"{left} {right}"
        # Two changes only for long words: "scorching" is not a typo of "searching"
        limit = 1 if len(word) <= 9 else 2
        best, best_key = None, None
        for length in range(len(word) - limit, len(word) + limit + 1):
            for candidate in self.by_length.get(length, ()):
                distance = _edit_distance(word, candidate, limit)
                if distance > limit:
                    continue
                # Fewest changes first, then the same first letter (people rarely
                # mistype it), then the more common word
                key = (distance, candidate[0] != word[0], -self.counts[candidate])
                if best_key is None or key < best_key:
                    best, best_key = candidate, key
        return best or word


_speller_cache: Dict[int, _Speller] = {}


@lru_cache(maxsize=1)
def _english_words() -> frozenset:
    """~21,000 English words from the meaning model's vocabulary (if it has
    been downloaded) — used only to recognise correctly spelt words."""
    from glob import glob
    from ai.semantic import CACHE_DIR
    for path in glob(os.path.join(CACHE_DIR, "**", "tokenizer.json"), recursive=True):
        try:
            with open(path, encoding="utf-8") as f:
                vocab = json.load(f)["model"]["vocab"]
            return frozenset(w for w in vocab if w.isalpha() and w.islower() and len(w) >= 2)
        except (OSError, ValueError, KeyError):
            continue
    return frozenset()


def correct_typos(text: str, articles: Sequence[Dict]) -> str:
    """Fix misspelt words ("batery not chargin" -> "battery not charging",
    "hadr dsik" -> "hard disk") by matching words the chatbot doesn't know
    against the vocabulary of the knowledge base and training data. Words it
    already knows, and words of 1-3 letters, are left alone, and a word is
    only changed when one (or, for long words, two) mistakes explain it, so
    names and normal English pass through."""
    key = hash(tuple((a.get("id"), a.get("title"), len(a.get("body") or "")) for a in articles))
    speller = _speller_cache.get(key)
    if speller is None:
        counts = Counter(_training_words())
        for art in articles:
            counts.update(_TOKEN.findall(f"{art.get('title') or ''} {art.get('tags') or ''} {art.get('body') or ''}".lower()))
        speller = _Speller(counts, _english_words())
        _speller_cache.clear()
        _speller_cache[key] = speller

    def fix(match: re.Match) -> str:
        word = match.group(0)
        corrected = speller.correct(word.lower())
        return word if corrected == word.lower() else corrected

    return re.sub(r"[A-Za-z]+", fix, text or "")


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
