import re
from collections import Counter
from typing import List


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "this",
    "that",
    "it",
    "as",
    "at",
    "by",
    "from",
    "we",
    "you",
    "your",
}


def _split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9']+", text)]


def summarize_text(text: str, max_sentences: int = 4) -> str:
    sentences = _split_sentences(text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    tokens = [t for t in _tokenize(text) if t not in STOPWORDS and len(t) > 2]
    if not tokens:
        return " ".join(sentences[:max_sentences])

    frequencies = Counter(tokens)
    scored = []
    for idx, sentence in enumerate(sentences):
        words = [w for w in _tokenize(sentence) if w in frequencies]
        score = sum(frequencies[w] for w in words) / max(len(words), 1)
        # Small bonus for earlier sentences to preserve flow
        score += max(0, 1 - idx / max(len(sentences), 1))
        scored.append((idx, sentence, score))

    top = sorted(scored, key=lambda x: x[2], reverse=True)[:max_sentences]
    ordered = sorted(top, key=lambda x: x[0])
    return " ".join(item[1] for item in ordered)
