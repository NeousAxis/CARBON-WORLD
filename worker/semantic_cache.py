"""
semantic_cache.py — Semantic deduplication cache for the CARBON WORLD pipeline.

Before sending an article to the LLM classifier, this module checks whether a
semantically similar article was already fully scored in the last N days.  If so,
the previous verdict is reused without any LLM call, saving Groq/Cerebras quota on
redundant mainstream coverage of the same underlying event.

Public API
----------
    get_embedder()           -> SentenceTransformer   (lazy-load, once per process)
    compute_embedding(text)  -> bytes                 (384-dim float32 = 1536 bytes)
    find_similar_recent(conn, embedding, days_back, threshold) -> Optional[dict]

Storage
-------
    - carbon_events.embedding BLOB  (1536 bytes per event, added by db._migrate_schema)
    - carbon_events.reused_from_event_id INTEGER  (back-pointer for cache-hit events)

Design notes
------------
    - Model all-MiniLM-L6-v2 runs entirely on CPU; ~100 MB RAM, ~50 ms/article on VPS.
    - Similarity is computed in Python with numpy cosine (no sqlite-vec dependency).
    - Only events with a non-NULL embedding are candidates for cache lookup — this
      naturally limits the candidate set to recently scored, fully validated events.
    - The module-level _model singleton is initialised once and shared across the run.
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger("semantic_cache")

# ---------------------------------------------------------------------------
# Module-level model singleton (lazy-loaded on first call to get_embedder)
# ---------------------------------------------------------------------------

_model = None


def get_embedder():
    """
    Return the SentenceTransformer model, initialising it on first call.

    Uses device='cpu' explicitly because the VPS has no GPU.  The model
    (~25 MB download, ~100 MB RAM) is kept alive for the lifetime of the
    Python process so that a single worker run pays the load cost only once.
    """
    global _model
    if _model is None:
        # Import here to keep sentence-transformers as an optional dep at module level
        from sentence_transformers import SentenceTransformer
        from config import SEMANTIC_MODEL_NAME

        logger.info("Loading sentence-transformer model '%s' (CPU)…", SEMANTIC_MODEL_NAME)
        _model = SentenceTransformer(SEMANTIC_MODEL_NAME, device="cpu")
        logger.info("Model loaded.")
    return _model


def compute_embedding(text: str) -> bytes:
    """
    Encode *text* into a 384-dimensional float32 vector and return it as raw bytes.

    The caller should pass:  title + ' — ' + description[:2000]

    Returns
    -------
    bytes
        Little-endian float32 array, 384 × 4 = 1536 bytes.
    """
    model = get_embedder()
    # encode() returns a numpy float32 array of shape (384,)
    vector: np.ndarray = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vector.astype(np.float32).tobytes()


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two pre-normalised vectors (fast path)."""
    # If both vectors were produced by compute_embedding with normalize_embeddings=True,
    # their L2 norm is already 1.0, so cosine = dot product.
    return float(np.dot(a, b))


def find_similar_recent(
    conn: sqlite3.Connection,
    embedding: bytes,
    days_back: int = 7,
    threshold: float = 0.92,
) -> Optional[dict]:
    """
    Search carbon_events for the closest semantic match within the last *days_back* days.

    Parameters
    ----------
    conn        : open sqlite3.Connection (row_factory = sqlite3.Row recommended)
    embedding   : bytes — result of compute_embedding() for the candidate article
    days_back   : int   — look-back window (default 7 days)
    threshold   : float — minimum cosine similarity to consider a match (default 0.92)

    Returns
    -------
    None if no match is found above *threshold*, otherwise a dict:
        {
            'event_id':    int,
            'event_title': str,
            'decision':    str,   # 'BURN' | 'MINT' | 'NEUTRAL'
            'amount_crbn': int,
            'final_score': float,
            'confidence':  int,
            'cosine':      float,
        }

    Implementation note
    -------------------
    All candidate rows (embedding IS NOT NULL, within date window) are loaded into
    Python memory for batch cosine computation via numpy.  At a rate of ~6 scored
    events/run × 96 runs/day this stays well below 1 000 rows in the first months.
    Revisit with an ANN index (e.g. sqlite-vec or faiss) if candidates exceed ~10 000.
    """
    query_vec = np.frombuffer(embedding, dtype=np.float32)

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days_back)).isoformat()

    try:
        cursor = conn.execute(
            """
            SELECT id, event_title, decision, amount_crbn, final_score, confidence, embedding
            FROM carbon_events
            WHERE embedding IS NOT NULL
              AND created_at >= ?
            ORDER BY id DESC
            """,
            (cutoff,),
        )
        rows = cursor.fetchall()
    except Exception as exc:
        logger.warning("find_similar_recent: DB query failed: %s", exc)
        return None

    if not rows:
        return None

    best_cosine = -1.0
    best_row = None

    for row in rows:
        raw = row[6] if isinstance(row, tuple) else row["embedding"]
        if raw is None or len(raw) != 1536:
            continue
        candidate_vec = np.frombuffer(raw, dtype=np.float32)
        sim = _cosine(query_vec, candidate_vec)
        if sim > best_cosine:
            best_cosine = sim
            best_row = row

    if best_cosine < threshold or best_row is None:
        return None

    # Normalise row access (sqlite3.Row or tuple)
    def _get(r, key, idx):
        try:
            return r[key]
        except (IndexError, KeyError, TypeError):
            return r[idx]

    return {
        "event_id":    _get(best_row, "id", 0),
        "event_title": _get(best_row, "event_title", 1),
        "decision":    _get(best_row, "decision", 2),
        "amount_crbn": _get(best_row, "amount_crbn", 3),
        "final_score": _get(best_row, "final_score", 4),
        "confidence":  _get(best_row, "confidence", 5),
        "cosine":      best_cosine,
    }
