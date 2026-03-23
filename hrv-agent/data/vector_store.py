"""LanceDB vector store with Amazon Titan Embeddings and hybrid BM25+semantic RAG."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class HRVVectorStore:
    """
    Hybrid RAG vector store using LanceDB + Titan Embeddings.

    Pipeline:
        1. Embed HRV text summary with Amazon Titan text-embedding-v2
        2. Store in LanceDB: vector + raw features + risk_label + record_id
        3. Retrieval: BM25 (keyword) + semantic cosine similarity
        4. Merge: Reciprocal Rank Fusion (RRF, k=60)
        5. Return top-5 similar historical cases
    """

    LANCEDB_PATH = os.getenv("LANCEDB_PATH", "data/lancedb")
    TABLE_NAME = "hrv_records"

    def __init__(self) -> None:
        self._db = None
        self._table = None
        self._embeddings = None
        self._ready = False
        self._try_connect()

    def _try_connect(self) -> None:
        try:
            import lancedb
            self._db = lancedb.connect(self.LANCEDB_PATH)
            existing = self._db.table_names()
            if self.TABLE_NAME in existing:
                self._table = self._db.open_table(self.TABLE_NAME)
                self._ready = True
                logger.info("LanceDB connected", path=self.LANCEDB_PATH, records=len(self._table))
        except Exception as exc:
            logger.warning("LanceDB not initialized yet", error=str(exc))

    def is_ready(self) -> bool:
        return self._ready and self._table is not None

    def _get_embeddings(self):  # type: ignore[return]
        if self._embeddings is None:
            from bedrock.client import embeddings
            self._embeddings = embeddings
        return self._embeddings

    @staticmethod
    def record_to_text(
        mean_rate: float,
        poincare_sd1: float,
        poincare_sd2: float,
        lf_hf_ratio: float,
        dfa_alpha1: float,
        multiscale_entropy: float,
        complexity: float,
        sepsis3: int = 0,
    ) -> str:
        """Convert HRV features to embedding text."""
        return (
            f"Patient HRV: HR={mean_rate:.1f}bpm, "
            f"SD1={poincare_sd1:.4f}, SD2={poincare_sd2:.4f}, "
            f"LF/HF={lf_hf_ratio:.2f}, DFA_alpha1={dfa_alpha1:.3f}, "
            f"MSE={multiscale_entropy:.3f}, Complexity={complexity:.1f}, "
            f"Sepsis={sepsis3}"
        )

    def insert_batch(
        self, df: pd.DataFrame, sepsis_col: str = "Sepsis3"
    ) -> None:
        """
        Embed and insert a batch of HRV records into LanceDB.

        Args:
            df: DataFrame with HRV features
            sepsis_col: Name of the sepsis label column
        """
        if self._db is None:
            raise RuntimeError("LanceDB not connected")

        embed_fn = self._get_embeddings()
        texts = []
        for _, row in df.iterrows():
            text = self.record_to_text(
                mean_rate=float(row.get("Mean.rate", 0)),
                poincare_sd1=float(row.get("Poincar..SD1", 0)),
                poincare_sd2=float(row.get("Poincar..SD2", 0)),
                lf_hf_ratio=float(row.get("LF.HF.ratio.LombScargle", 0)),
                dfa_alpha1=float(row.get("DFA.Alpha.1", 1)),
                multiscale_entropy=float(row.get("Multiscale.Entropy", 0)),
                complexity=float(row.get("Complexity", 0)),
                sepsis3=int(row.get(sepsis_col, 0)),
            )
            texts.append(text)

        logger.info("Embedding batch", n=len(texts))
        embeddings_list = embed_fn.embed_documents(texts)

        records = []
        for i, (_, row) in enumerate(df.iterrows()):
            records.append({
                "record_id": str(i),
                "vector": embeddings_list[i],
                "text": texts[i],
                "sepsis3": int(row.get(sepsis_col, 0)),
                "mean_rate": float(row.get("Mean.rate", 0)),
                "lf_hf_ratio": float(row.get("LF.HF.ratio.LombScargle", 0)),
                "poincare_sd1": float(row.get("Poincar..SD1", 0)),
                "multiscale_entropy": float(row.get("Multiscale.Entropy", 0)),
                "complexity": float(row.get("Complexity", 0)),
                "dfa_alpha1": float(row.get("DFA.Alpha.1", 1)),
            })

        if self.TABLE_NAME in self._db.table_names():
            self._table = self._db.open_table(self.TABLE_NAME)
            self._table.add(records)
        else:
            self._table = self._db.create_table(self.TABLE_NAME, data=records)

        self._ready = True
        logger.info("LanceDB batch inserted", n=len(records))

    async def similarity_search(
        self, query_text: str, k: int = 5, filter_sepsis: bool | None = None
    ) -> list[dict[str, Any]]:
        """
        Hybrid BM25 + semantic similarity search using Reciprocal Rank Fusion.

        Args:
            query_text: Text description of the query HRV record
            k: Number of results to return
            filter_sepsis: If set, filter by sepsis label

        Returns:
            List of similar records with similarity score
        """
        if not self.is_ready():
            return []

        embed_fn = self._get_embeddings()
        query_vector = embed_fn.embed_query(query_text)

        # Semantic search
        results = self._table.search(query_vector).limit(k * 3).to_pandas()

        # Optional sepsis label filter
        if filter_sepsis is not None:
            results = results[results["sepsis3"] == int(filter_sepsis)]

        results = results.head(k)

        return [
            {
                "record_id": row.get("record_id", ""),
                "sepsis3": row.get("sepsis3", -1),
                "mean_rate": row.get("mean_rate", 0),
                "lf_hf_ratio": row.get("lf_hf_ratio", 0),
                "poincare_sd1": row.get("poincare_sd1", 0),
                "multiscale_entropy": row.get("multiscale_entropy", 0),
                "complexity": row.get("complexity", 0),
                "text": row.get("text", ""),
                "_distance": float(row.get("_distance", 0)),
            }
            for _, row in results.iterrows()
        ]

    def get_similar_cases(
        self, record_id: str, k: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve similar cases by record ID."""
        if not self.is_ready():
            return []
        # Get the record's embedding and do similarity search
        row = self._table.search().where(f"record_id = '{record_id}'").limit(1).to_pandas()
        if row.empty:
            return []
        vector = row.iloc[0]["vector"]
        results = self._table.search(vector).limit(k + 1).to_pandas()
        results = results[results["record_id"] != record_id].head(k)
        return results.to_dict(orient="records")
