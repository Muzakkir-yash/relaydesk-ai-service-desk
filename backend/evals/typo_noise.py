"""
Realistic spelling mistakes for robustness testing (run_chatbot_eval.py --typos N).

Deliberately broader than the typo augmentation used in training
(ai/intent_model.make_typo), so the score shows how the bot copes with the
kinds of mistakes real people make, not just the ones it was trained on:
  - neighbouring-key slips      ("printer" -> "prinyer")
  - a missing letter            ("battery" -> "battry")
  - a doubled letter            ("screen"  -> "screeen")
  - two letters swapped         ("laptop"  -> "lpatop")
  - two words run together      ("not working" -> "notworking")
  - common phonetic spellings   ("receive" -> "recieve", "phone" -> "fone")
Deterministic: the same case and seed always get the same mistakes.
"""

import random
import re

_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
_NEIGHBOURS = {}
for r, row in enumerate(_ROWS):
    for c, ch in enumerate(row):
        near = set()
        for dr in (-1, 0, 1):
            if 0 <= r + dr < len(_ROWS):
                other = _ROWS[r + dr]
                for dc in (-1, 0, 1):
                    if 0 <= c + dc < len(other) and (dr, dc) != (0, 0):
                        near.add(other[c + dc])
        _NEIGHBOURS[ch] = sorted(near)

_PHONETIC = [("ph", "f"), ("ei", "ie"), ("ie", "ei"), ("ou", "o"), ("ck", "k"), ("tion", "shun"), ("ss", "s"),
             ("ll", "l"), ("ea", "ee"), ("y", "i"), ("c", "k"), ("e", "a")]


def _misspell(word: str, rng: random.Random) -> str:
    kinds = ["neighbour", "drop", "double", "swap", "phonetic"]
    for _ in range(10):
        kind = rng.choice(kinds)
        if kind == "phonetic":
            options = [(a, b) for a, b in _PHONETIC if a in word[1:]]
            if not options:
                continue
            a, b = rng.choice(options)
            i = word.index(a, 1)
            return word[:i] + b + word[i + len(a):]
        pos = rng.randrange(1, len(word))
        ch = word[pos]
        if kind == "neighbour" and ch in _NEIGHBOURS:
            return word[:pos] + rng.choice(_NEIGHBOURS[ch]) + word[pos + 1:]
        if kind == "drop":
            return word[:pos] + word[pos + 1:]
        if kind == "double":
            return word[:pos] + ch + word[pos:]
        if kind == "swap" and pos < len(word) - 1:
            return word[:pos] + word[pos + 1] + word[pos] + word[pos + 2:]
    return word


def add_typos(text: str, count: int, seed: str) -> str:
    """`count` spelling mistakes in words of 4+ letters (one may be a run-together pair)."""
    rng = random.Random(seed)
    words = text.split(" ")
    for _ in range(count):
        candidates = [i for i, w in enumerate(words) if len(re.sub(r"[^a-z]", "", w.lower())) >= 4 and w.isalpha()]
        if not candidates:
            break
        i = rng.choice(candidates)
        if rng.random() < 0.15 and i + 1 < len(words) and words[i + 1].isalpha():
            words[i:i + 2] = [words[i] + words[i + 1]]  # "not working" -> "notworking"
        else:
            words[i] = _misspell(words[i].lower(), rng)
    return " ".join(words)
