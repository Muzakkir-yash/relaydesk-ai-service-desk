"""
Training report for the chatbot's ML models (free, offline — scikit-learn).

5-fold cross-validation: the hand-written examples are split into 5 parts;
the model trains on 4 and is tested on the 5th, five times over. Generated
data (typo copies and template sentences) is only ever added to the training
folds, so every test sentence is a real hand-written one and the score is
honest. Compares plain training against augmented training.

Usage (from backend/):  python evals/train_report.py
"""

import os
import sys
import warnings
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")

from sklearn.metrics import classification_report  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402

from ai.intent_model import MODEL_FILES, AugmentedClassifier, expand_templates, load_examples  # noqa: E402


def accuracy(predicted, labels):
    return sum(p == y for p, y in zip(predicted, labels)) / len(labels)


def report(model: str) -> None:
    texts, labels = load_examples(MODEL_FILES[model])
    extra = expand_templates(model)
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    plain = cross_val_predict(AugmentedClassifier(typo_copies=0), texts, labels, cv=folds)
    augmented = cross_val_predict(AugmentedClassifier(extra=extra), texts, labels, cv=folds)

    print(f"\n=== {model} model — {len(texts)} hand-written examples (+{len(extra[0])} from templates, "
          f"+typo copies), {len(set(labels))} labels ===")
    print(f"Cross-validated accuracy:  plain {accuracy(plain, labels):.0%}  →  augmented {accuracy(augmented, labels):.0%}\n")
    print(classification_report(labels, augmented, zero_division=0))
    mistakes = Counter((y, p) for p, y in zip(augmented, labels) if p != y)
    if mistakes:
        print("Most common confusions (true -> predicted):")
        for (true, pred), count in mistakes.most_common(5):
            print(f"  {true:>10} -> {pred:<10} x{count}")


def report_articles() -> None:
    """The article matcher: which KB article answers a message. Cross-validated
    over the example messages in ai/training/articles.json; every article's
    title, tags and opening line are always in the training folds."""
    from ai.article_matcher import _article_texts, _load_examples, _title_key
    from evals.run_chatbot_eval import load_articles

    articles = load_articles()
    examples = _load_examples()
    texts, labels, base_texts, base_labels = [], [], [], []
    titles = {a["id"]: a["title"] for a in articles}
    for art in articles:
        for example in examples.get(_title_key(art["title"]), []):
            texts.append(example)
            labels.append(art["id"])
        for text in _article_texts(art, {}):
            base_texts.append(text)
            base_labels.append(art["id"])
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    predicted = cross_val_predict(AugmentedClassifier(extra=(base_texts, base_labels)), texts, labels, cv=folds)

    print(f"\n=== article matcher — {len(texts)} example messages for {len(set(labels))} of "
          f"{len(articles)} published articles ===")
    print(f"Cross-validated accuracy (right article first): {accuracy(predicted, labels):.0%}\n")
    mistakes = Counter((y, p) for p, y in zip(predicted, labels) if p != y)
    if mistakes:
        print("Most common confusions (true -> predicted):")
        for (true, pred), count in mistakes.most_common(8):
            print(f"  {titles[true][:40]:>40} -> {titles[pred][:40]:<40} x{count}")


if __name__ == "__main__":
    report("intents")
    report("categories")
    report_articles()
