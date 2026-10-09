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


if __name__ == "__main__":
    report("intents")
    report("categories")
