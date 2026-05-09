from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# ── Model identity ────────────────────────────────────────────────────────────
# Bump MODEL_VERSION whenever the model changes. Old Redis keys are different
# strings, so stale embeddings are simply ignored (they expire by TTL naturally).
# fastembed uses ONNX runtime — no PyTorch dependency (~60 MB install vs ~1.5 GB for torch).
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_VERSION = "v1"

# ── Redis storage — article embeddings ───────────────────────────────────────
# Pre-computed article embeddings written by the scheduler, consumed by topic search.
ARTICLE_EMBED_KEY = f"news:article_embeddings:all-MiniLM-L6-v2:{MODEL_VERSION}"
ARTICLE_EMBED_TTL = 3600  # seconds — matches the scheduler refresh interval

# ── Redis storage — category label embeddings ────────────────────────────────
# One embedding per news category, computed on first use and cached for 24 h.
# Used for zero-shot category routing when topic search returns no results.
CATEGORY_EMBED_KEY = f"news:category_embeddings:all-MiniLM-L6-v2:{MODEL_VERSION}"
CATEGORY_EMBED_TTL = 86400  # 24 h — labels rarely change

# Descriptive label strings for each category. Richer descriptions produce
# better separation in embedding space than single words.
# Tunable without code changes — just update strings and flush the Redis key.
CATEGORY_LABELS: dict[str, str] = {
    "ai":          "artificial intelligence machine learning deep learning neural networks LLM GPT model training inference",
    "programming": "software engineering coding programming developer tools frameworks languages DevOps infrastructure backend frontend",
    "political":   "politics government policy election war military law legislation diplomacy international relations",
    "biology":     "biology genetics DNA cell evolution species ecology microbiology neuroscience organism reproduction",
    "economy":     "economics finance markets stocks business trade investment banking currency GDP inflation recession",
    "health":      "health medicine wellness medical treatment disease hospital nutrition beauty skincare fitness pregnancy childbirth",
}

# ── Scoring weights ───────────────────────────────────────────────────────────
# Titles are denser signal than summaries, which often include boilerplate.
_TITLE_WEIGHT = 0.7

# MMR λ: higher = more relevance, lower = more diversity.
_MMR_LAMBDA = 0.6

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        logger.info(
            "Loading embedding model %s via fastembed (first use — one-time ~60 MB download)", MODEL_NAME
        )
        _model = TextEmbedding(MODEL_NAME)
        logger.info("Embedding model ready")
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Return L2-normalised embeddings for a list of texts (shape: N × 384).

    fastembed returns a generator of already-normalised numpy arrays.
    Collecting into a 2D array matches the sentence-transformers interface.
    """
    return np.array(list(_get_model().embed(texts)))


def embed_articles(articles: list[dict]) -> list[dict]:
    """Embed title and summary of each article separately.

    Returns a new list of dicts with two extra keys added:
      - title_emb:   list[float] — L2-normalised title embedding (384 dims)
      - summary_emb: list[float] — L2-normalised summary embedding (384 dims)

    Separate embeddings allow weighted scoring at query time without re-running
    the model. Storing as plain lists keeps them JSON-serialisable for Redis.
    """
    if not articles:
        return []
    titles = [a.get("title") or "" for a in articles]
    summaries = [a.get("summary") or "" for a in articles]
    title_embs = embed(titles)
    summary_embs = embed(summaries)
    result = []
    for i, article in enumerate(articles):
        enriched = dict(article)
        enriched["title_emb"] = title_embs[i].tolist()
        enriched["summary_emb"] = summary_embs[i].tolist()
        result.append(enriched)
    return result


def weighted_scores(
    topic_emb: np.ndarray,
    title_embs: np.ndarray,
    summary_embs: np.ndarray,
) -> np.ndarray:
    """Compute per-article relevance scores as a weighted cosine similarity.

    score = _TITLE_WEIGHT × cos_sim(topic, title)
          + (1 − _TITLE_WEIGHT) × cos_sim(topic, summary)

    All embeddings must be L2-normalised so dot product equals cosine similarity.
    Returns shape (N,).
    """
    return (
        _TITLE_WEIGHT * (title_embs @ topic_emb)
        + (1 - _TITLE_WEIGHT) * (summary_embs @ topic_emb)
    )


def adaptive_threshold(scores: list[float], floor: float = 0.15) -> float:
    """Compute an article-inclusion threshold that scales with match quality.

    threshold = max(floor, top_score × 0.6)

    When the best match is strong (top=0.80) the threshold is strict (0.48),
    filtering out weak articles. When the best match is mediocre (top=0.30) the
    threshold relaxes to 0.18, so niche topics still surface results. The floor
    prevents garbage articles from being included even when nothing matches.
    """
    if not scores:
        return floor
    return max(floor, max(scores) * 0.6)


def mmr_rerank(
    topic_emb: np.ndarray,
    candidates: list[dict],
    title_embs: np.ndarray,
    summary_embs: np.ndarray,
    k: int = 15,
) -> list[dict]:
    """Maximal Marginal Relevance re-ranking for topic-news diversity.

    Iteratively selects the next article that maximises:
      MMR = λ × relevance(article, topic) − (1−λ) × max_sim(article, selected)

    This prevents returning 15 articles from the same source or sub-angle.
    λ = _MMR_LAMBDA (0.6) — biased toward relevance but penalises redundancy.

    Diversity is measured using a per-article combined embedding:
      combined = normalise(_TITLE_WEIGHT × title_emb + (1−_TITLE_WEIGHT) × summary_emb)
    """
    if not candidates:
        return []

    # Build a single representative embedding per article for diversity comparison.
    combined = _TITLE_WEIGHT * title_embs + (1 - _TITLE_WEIGHT) * summary_embs
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    combined = combined / norms  # re-normalise after weighted sum

    relevance = (combined @ topic_emb).tolist()

    selected_indices: list[int] = []
    selected_embs: list[np.ndarray] = []
    remaining = list(range(len(candidates)))

    while remaining and len(selected_indices) < k:
        if not selected_embs:
            # First pick: most relevant article.
            best = max(remaining, key=lambda i: relevance[i])
        else:
            sel_matrix = np.array(selected_embs)  # shape: (n_selected × D)
            best_score = -np.inf
            best = remaining[0]
            for i in remaining:
                max_sim = float(np.max(sel_matrix @ combined[i]))
                mmr = _MMR_LAMBDA * relevance[i] - (1 - _MMR_LAMBDA) * max_sim
                if mmr > best_score:
                    best_score = mmr
                    best = i

        selected_indices.append(best)
        selected_embs.append(combined[best])
        remaining.remove(best)

    return [candidates[i] for i in selected_indices]


def get_category_embeddings(redis_client) -> dict[str, list[float]]:
    """Return L2-normalised embeddings for each CATEGORY_LABELS entry.

    Loaded from Redis on cache hit; computed and stored on miss (TTL 24 h).
    The key encodes model name + version so a model upgrade automatically
    triggers recomputation on the next call — no manual cache flush needed.

    Returns {category_key: embedding_vector (list[float])} for all categories
    in CATEGORY_LABELS.
    """
    import json as _json
    raw = redis_client.get(CATEGORY_EMBED_KEY)
    if raw:
        return _json.loads(raw)

    cats = list(CATEGORY_LABELS.keys())
    texts = [CATEGORY_LABELS[c] for c in cats]
    embs = embed(texts)
    result = {cat: embs[i].tolist() for i, cat in enumerate(cats)}
    redis_client.setex(CATEGORY_EMBED_KEY, CATEGORY_EMBED_TTL, _json.dumps(result))
    logger.info("Computed and stored category embeddings for %d categories", len(result))
    return result
