"""Load and run the pinned local sentence-transformer model."""

from collections.abc import Sequence
from typing import Any

import numpy as np
from doc_agent_common.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
)

from doc_agent_core.state import FloatVector


class MiniLmEmbedder:
    """Generate normalized 384-dimensional embeddings on the local machine."""

    def __init__(self, cache_folder: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self._model: Any = SentenceTransformer(
            EMBEDDING_MODEL,
            revision=EMBEDDING_REVISION,
            cache_folder=cache_folder,
        )
        self.tokenizer: Any = self._model.tokenizer

    def encode(self, texts: Sequence[str]) -> list[FloatVector]:
        """Encode a batch and reject unexpected model output dimensions."""
        if not texts:
            return []
        matrix = self._model.encode(
            list(texts),
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        array = np.asarray(matrix, dtype=np.float32)
        if array.ndim != 2 or array.shape[1] != EMBEDDING_DIMENSION:
            raise RuntimeError("The embedding model returned an unexpected dimension.")
        norms = np.linalg.norm(array, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-4):
            raise RuntimeError("The embedding model returned non-normalized vectors.")
        return [row for row in array]
