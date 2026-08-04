"""
core/vectorstore.py

Pluggable, tenant-aware vector store for RAGnarok.

Default backend: TF-IDF (scikit-learn) -- deterministic, fully offline,
no model download required. This is a deliberate choice: it keeps the
lab runnable with zero setup friction, and TF-IDF is still a real
retrieval mechanism that is genuinely vulnerable to keyword-stuffing /
semantic-collision attacks (see attacks/attack2_semantic_collision.py).

To use dense embeddings instead (closer to a production RAG stack), set
EMBEDDING_BACKEND=sentence-transformers in your .env. That swaps in
all-MiniLM-L6-v2 via the `sentence-transformers` package with zero other
code changes required, since both backends implement the same interface
(fit / embed). Note this requires internet access on first run to pull
the model weights.
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Document:
    id: str
    tenant_id: str
    title: str
    content: str
    source: str = "unknown"
    trust_level: str = "unverified"   # "verified" | "unverified" | "quarantined"
    metadata: dict = field(default_factory=dict)


class TfidfEmbedder:
    """Default embedding backend. Offline, deterministic, zero downloads."""

    name = "tfidf"

    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self._fitted = False

    def fit(self, corpus):
        if not corpus:
            return
        self.vectorizer.fit(corpus)
        self._fitted = True

    def embed(self, texts):
        if not self._fitted:
            raise RuntimeError("Embedder not fitted yet -- add documents first")
        return self.vectorizer.transform(texts).toarray()


class SentenceTransformerEmbedder:
    """
    Optional dense-embedding backend for a more realistic semantic-collision
    demo. Requires `pip install sentence-transformers` and internet access
    on first run to download the model.
    """

    name = "sentence-transformers"

    def __init__(self, model_name="all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def fit(self, corpus):
        pass  # pretrained model, nothing to fit

    def embed(self, texts):
        return self.model.encode(texts, convert_to_numpy=True)


def get_embedder(backend: str = "tfidf"):
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder()
    return TfidfEmbedder()


class VectorStore:
    def __init__(self, embedder=None):
        self.embedder = embedder or TfidfEmbedder()
        self.documents: dict[str, Document] = {}
        self._matrix: Optional[np.ndarray] = None
        self._doc_ids: list[str] = []

    def add_document(self, tenant_id, title, content, source="unknown",
                      trust_level="unverified", metadata=None) -> Document:
        doc = Document(
            id=str(uuid.uuid4())[:8],
            tenant_id=tenant_id,
            title=title,
            content=content,
            source=source,
            trust_level=trust_level,
            metadata=metadata or {},
        )
        self.documents[doc.id] = doc
        self._reindex()
        return doc

    def _reindex(self):
        corpus = [d.content for d in self.documents.values()]
        self._doc_ids = list(self.documents.keys())
        if not corpus:
            self._matrix = None
            return
        self.embedder.fit(corpus)
        self._matrix = self.embedder.embed(corpus)

    def search(self, query: str, tenant_id: Optional[str] = None,
               top_k: int = 3, enforce_tenant_isolation: bool = True):
        """
        Returns a list of (Document, score) pairs, highest score first.

        enforce_tenant_isolation=True is the DEFENSE: only documents
        belonging to `tenant_id` (or the shared "global" tenant) are
        eligible for retrieval, checked at the retrieval layer itself.

        enforce_tenant_isolation=False is the vulnerable default: every
        document in the index is eligible for every query regardless of
        which tenant it belongs to, relying entirely on "the LLM will
        stay on topic" -- exactly the soft, prompt-level-only trust
        boundary that causes real-world cross-tenant leakage.
        """
        if self._matrix is None or not self.documents:
            return []

        query_vec = self.embedder.embed([query])
        sims = cosine_similarity(query_vec, self._matrix)[0]

        ranked = sorted(zip(self._doc_ids, sims), key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in ranked:
            doc = self.documents[doc_id]
            if enforce_tenant_isolation and tenant_id and doc.tenant_id not in (tenant_id, "global"):
                continue
            results.append((doc, float(score)))
            if len(results) >= top_k:
                break
        return results
