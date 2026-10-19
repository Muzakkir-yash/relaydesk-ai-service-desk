"""
Machine-learning models for the free offline chatbot (scikit-learn, BSD
licensed — no paid service, no network, nothing to download).

Two text classifiers are trained from the example sentences in ai/training/:
  - intent:   what the user is doing (describing a problem, confirming a fix,
              asking for a person, reporting a security incident, ...)
  - category: what area the problem is in (network, access, hardware, ...)

Each model combines word n-grams (meaning of phrases) with character n-grams
(robust to typos like "conect" or "wont") and a logistic-regression
classifier that outputs a probability, so the chatbot can fall back to its
rules when the model is unsure. Training takes well under a second, so the
models are trained in memory on first use — there is no model file to ship.

To improve them: add real user messages to the JSON files and restart.
Measure with:  python evals/train_report.py   and   python evals/run_chatbot_eval.py --set holdout
"""

import hashlib
import itertools
import json
import os
import random
import re
from functools import lru_cache
from typing import Dict, List, Sequence, Tuple

import joblib
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline, make_union

from ai.deflector import normalize_query

TRAINING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "training")
INTENTS_FILE = os.path.join(TRAINING_DIR, "intents.json")
CATEGORIES_FILE = os.path.join(TRAINING_DIR, "categories.json")
TEMPLATES_FILE = os.path.join(TRAINING_DIR, "templates.json")


def normalize(text: str) -> str:
    text = normalize_query(text or "")
    text = text.replace("’", "'").replace("'", "")  # "won't" and "wont" become the same token
    return re.sub(r"\s+", " ", text).strip()


def load_examples(path: str) -> Tuple[List[str], List[str]]:
    with open(path, encoding="utf-8") as f:
        data: Dict[str, List[str]] = json.load(f)
    texts, labels = [], []
    for label, examples in data.items():
        if label.startswith("_"):
            continue  # documentation keys
        for example in examples:
            texts.append(example)
            labels.append(label)
    return texts, labels


def expand_templates(model: str, seed: int = 7) -> Tuple[List[str], List[str]]:
    """Generate sentences from templates.json, e.g. "{who} can't {action}"
    with every combination of the slot values, sampled down to `limit`
    per pattern group so templates never outweigh the hand-written examples."""
    if not os.path.exists(TEMPLATES_FILE):
        return [], []
    with open(TEMPLATES_FILE, encoding="utf-8") as f:
        groups = json.load(f).get(model, {})
    rng = random.Random(seed)
    texts, labels = [], []
    for label, specs in groups.items():
        for spec in specs:
            slots = spec["slots"]
            sentences = []
            for pattern in spec["patterns"]:
                names = re.findall(r"{(\w+)}", pattern)
                for values in itertools.product(*(slots[n] for n in names)):
                    sentences.append(pattern.format(**dict(zip(names, values))))
            sentences = sorted(set(sentences))
            rng.shuffle(sentences)
            for sentence in sentences[: spec.get("limit", 40)]:
                texts.append(sentence)
                labels.append(label)
    return texts, labels


_KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
_NEIGHBOUR_KEYS = {
    ch: [_KEY_ROWS[r2][c2] for r2 in (r - 1, r, r + 1) if 0 <= r2 < 3
         for c2 in (c - 1, c, c + 1) if 0 <= c2 < len(_KEY_ROWS[r2]) and (r2, c2) != (r, c)]
    for r, row in enumerate(_KEY_ROWS) for c, ch in enumerate(row)
}


def make_typo(text: str, rng: random.Random) -> str:
    """One realistic typo: drop, swap or double a letter in a longer word, or
    hit the key next to the right one."""
    words = text.split()
    candidates = [i for i, w in enumerate(words) if len(w) >= 4 and w.isalpha()]
    if not candidates:
        return text
    i = rng.choice(candidates)
    w = words[i]
    pos = rng.randrange(1, len(w) - 1)
    kind = rng.choice(("drop", "swap", "double", "neighbour"))
    if kind == "drop":
        w = w[:pos] + w[pos + 1:]
    elif kind == "swap":
        w = w[:pos - 1] + w[pos] + w[pos - 1] + w[pos + 1:]
    elif kind == "neighbour" and w[pos].lower() in _NEIGHBOUR_KEYS:
        w = w[:pos] + rng.choice(_NEIGHBOUR_KEYS[w[pos].lower()]) + w[pos + 1:]
    else:
        w = w[:pos] + w[pos] + w[pos:]
    words[i] = w
    return " ".join(words)


def build_pipeline() -> Pipeline:
    features = make_union(
        TfidfVectorizer(preprocessor=normalize, analyzer="word", ngram_range=(1, 2), sublinear_tf=True),
        TfidfVectorizer(preprocessor=normalize, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
    )
    classifier = LogisticRegression(C=10.0, max_iter=5000, class_weight="balanced")
    return make_pipeline(features, classifier)


class AugmentedClassifier(BaseEstimator, ClassifierMixin):
    """Trains build_pipeline() on the given examples plus generated data:
    `typo_copies` misspelled copies of each example and the template
    sentences in `extra`. Augmentation happens inside fit(), so during
    cross-validation it only ever touches the training folds — the test
    folds stay pure hand-written sentences and the score stays honest."""

    def __init__(self, typo_copies: int = 2, extra: Sequence = ((), ()), seed: int = 13):
        self.typo_copies = typo_copies
        self.extra = extra
        self.seed = seed

    def fit(self, X, y):
        rng = random.Random(self.seed)
        texts, labels = list(X), list(y)
        extra_texts, extra_labels = self.extra
        texts += list(extra_texts)
        labels += list(extra_labels)
        originals = list(zip(texts, labels))
        for text, label in originals:
            for _ in range(self.typo_copies):
                texts.append(make_typo(text, rng))
                labels.append(label)
        self.pipeline_ = build_pipeline().fit(texts, labels)
        self.classes_ = self.pipeline_.classes_
        return self

    def predict(self, X):
        return self.pipeline_.predict(X)

    def predict_proba(self, X):
        return self.pipeline_.predict_proba(X)


MODEL_FILES = {"intents": INTENTS_FILE, "categories": CATEGORIES_FILE}
CACHE_DIR = os.path.join(TRAINING_DIR, ".model_cache")
# Bump when the training code changes so stale cached models are not reused
MODEL_VERSION = "3"


def _fingerprint(model: str) -> str:
    """Changes whenever the training data, templates or model version change."""
    digest = hashlib.sha256(MODEL_VERSION.encode())
    for path in (MODEL_FILES[model], TEMPLATES_FILE):
        if os.path.exists(path):
            with open(path, "rb") as f:
                digest.update(f.read())
    return digest.hexdigest()[:16]


class TextClassifier:
    def __init__(self, model: str, use_cache: bool = True):
        texts, labels = load_examples(MODEL_FILES[model])
        self.size = len(texts)
        cache_path = os.path.join(CACHE_DIR, f"{model}-{_fingerprint(model)}.joblib")
        if use_cache and os.path.exists(cache_path):
            # Our own file, written below from our own training data
            self.pipeline = joblib.load(cache_path)
        else:
            extra = expand_templates(model)
            self.pipeline = AugmentedClassifier(extra=extra).fit(texts, labels)
            if use_cache:
                os.makedirs(CACHE_DIR, exist_ok=True)
                for old in os.listdir(CACHE_DIR):
                    if old.startswith(f"{model}-"):
                        os.remove(os.path.join(CACHE_DIR, old))
                joblib.dump(self.pipeline, cache_path)
        self.labels = list(self.pipeline.classes_)

    def predict(self, text: str) -> Tuple[str, float]:
        """Most likely label and its probability (0-1)."""
        probabilities = self.pipeline.predict_proba([text])[0]
        best = int(probabilities.argmax())
        return self.labels[best], float(probabilities[best])

    def probabilities(self, text: str) -> Dict[str, float]:
        """Probability of every label."""
        return dict(zip(self.labels, map(float, self.pipeline.predict_proba([text])[0])))


@lru_cache(maxsize=1)
def intent_model() -> TextClassifier:
    return TextClassifier("intents")


@lru_cache(maxsize=1)
def category_model() -> TextClassifier:
    return TextClassifier("categories")


def warm_up() -> None:
    """Load (or train and cache) both models, so no chat has to wait."""
    intent_model()
    category_model()
