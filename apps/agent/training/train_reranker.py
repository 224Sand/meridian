"""Fine-tune a cross-encoder re-ranker (FR-029).

A bi-encoder scores a query and a chunk independently and compares the vectors.
A cross-encoder reads both together, so it can weigh how the question's terms
interact with the passage's - which is exactly the distinction retrieval keeps
getting wrong here, where a question about one entity's property retrieves the
passage stating that property for a different entity.

Trained offline in PyTorch, exported to ONNX, served with onnxruntime
(ADR-0009). torch is ~1GB installed; onnxruntime is ~50MB.

Negatives are HARD: sampled from the chunks hybrid retrieval actually returns
for that query but which do not belong to the gold document. Random negatives
would teach the model to separate 'about databases' from 'about certificates',
which retrieval already does. The useful signal is in the confusable pairs.

Question splits are by SOURCE DOCUMENT throughout, matching the discipline used
everywhere else in this sprint. Evaluation uses only held-out documents, so no
chunk the model trained on appears in a scored ranking.

    python training/train_reranker.py
"""

from __future__ import annotations

import json
import math
import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from sandscope_agent.evaluation.dataset import Label, build_dataset
from sandscope_agent.retrieval.corpus import chunk_corpus, load_corpus
from sandscope_agent.retrieval.embedding import HashingEmbedder
from sandscope_agent.retrieval.hybrid import HybridRetriever

#: TinyBERT rather than MiniLM-L-6. The MiniLM checkpoint loads with no NaN in
#: any parameter and then produces NaN logits on a plain forward pass on this
#: platform - verified across torch 2.8 and 2.13, transformers 4.57 and 5.15,
#: Anaconda and Homebrew interpreters, and with the duplicate-libomp conflict
#: eliminated. TinyBERT produces correct, ordered logits under identical
#: conditions.
#:
#: It is also the better serving choice: 2 layers against 6, roughly 3x faster
#: on the 2 vCPU the container has.
BASE_MODEL = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
MODEL_DIR = Path(__file__).resolve().parents[1] / "sandscope_agent" / "retrieval" / "reranker"
MAX_LENGTH = 256
CANDIDATES = 20
NEGATIVES_PER_QUESTION = 4
EPOCHS = 2
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
SEED = 20260820


@dataclass
class Pair:
    query: str
    passage: str
    label: float


class PairDataset(Dataset):
    def __init__(self, pairs: list[Pair], tokenizer) -> None:
        self.pairs = pairs
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, index: int):
        return self.pairs[index]


def collate(tokenizer):
    def inner(batch: list[Pair]):
        encoded = tokenizer(
            [p.query for p in batch],
            [p.passage for p in batch],
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        encoded["labels"] = torch.tensor([p.label for p in batch], dtype=torch.float32)
        return encoded

    return inner


def build_pairs(questions, retriever: HybridRetriever, chunks_by_document) -> list[Pair]:
    rng = random.Random(SEED)
    pairs: list[Pair] = []

    for question in questions:
        if question.label is not Label.ANSWERABLE or not question.gold_document_id:
            continue
        gold_chunks = chunks_by_document.get(question.gold_document_id, [])
        if not gold_chunks:
            continue

        retrieved = retriever.search(question.text, limit=CANDIDATES).hits
        positives = [h.chunk for h in retrieved if h.chunk.document_id == question.gold_document_id]
        if not positives:
            positives = [gold_chunks[0]]
        hard_negatives = [
            h.chunk for h in retrieved if h.chunk.document_id != question.gold_document_id
        ]
        rng.shuffle(hard_negatives)

        for chunk in positives[:2]:
            pairs.append(Pair(question.text, chunk.body, 1.0))
        for chunk in hard_negatives[:NEGATIVES_PER_QUESTION]:
            pairs.append(Pair(question.text, chunk.body, 0.0))

    rng.shuffle(pairs)
    return pairs


def fmt(metrics: dict[str, float]) -> str:
    return "  ".join(f"{k}={v:.3f}" for k, v in metrics.items())


def rank_metrics(rankings: list[list[bool]]) -> dict[str, float]:
    """hit@1, hit@3 and MRR over lists flagging whether each position is gold."""
    if not rankings:
        return {"hit@1": 0.0, "hit@3": 0.0, "mrr": 0.0, "n": 0.0}
    hit1 = statistics.mean(1.0 if r and r[0] else 0.0 for r in rankings)
    hit3 = statistics.mean(1.0 if any(r[:3]) else 0.0 for r in rankings)
    reciprocal = []
    for row in rankings:
        rank = next((i + 1 for i, is_gold in enumerate(row) if is_gold), 0)
        reciprocal.append(1.0 / rank if rank else 0.0)
    return {
        "hit@1": hit1,
        "hit@3": hit3,
        "mrr": statistics.mean(reciprocal),
        "n": float(len(rankings)),
    }


@torch.no_grad()
def score_pairs(model, tokenizer, query: str, passages: list[str]) -> list[float]:
    encoded = tokenizer(
        [query] * len(passages),
        passages,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    return model(**encoded).logits.squeeze(-1).tolist()


def evaluate(
    model, tokenizer, questions, retriever: HybridRetriever
) -> tuple[dict, dict, dict, dict, float]:
    """Compare hybrid retrieval with and without re-ranking.

    Measured at BOTH document and chunk level, because the two answer different
    questions and only one of them has any headroom:

        gold DOCUMENT first   98.3%   MRR 0.992
        gold CHUNK    first   21.1%   MRR 0.413

    The first version of this script measured documents only and concluded the
    re-ranker did not help. It was measuring a metric that was already saturated.
    A citation points at a chunk, so chunk-level is the metric that matters.
    """
    model.eval()
    base_doc: list[list[bool]] = []
    rank_doc: list[list[bool]] = []
    base_chunk: list[list[bool]] = []
    rank_chunk: list[list[bool]] = []
    latencies: list[float] = []

    for question in questions:
        if question.label is not Label.ANSWERABLE or not question.gold_document_id:
            continue
        hits = retriever.search(question.text, limit=CANDIDATES).hits
        if not hits:
            continue

        started = time.perf_counter()
        scores = score_pairs(model, tokenizer, question.text, [h.chunk.body for h in hits])
        latencies.append((time.perf_counter() - started) * 1000)

        if not all(math.isfinite(s) for s in scores):
            raise RuntimeError(
                "the re-ranker produced non-finite scores. Sorting NaN preserves "
                "input order, so every metric below would silently equal the "
                "baseline and the run would look like a clean negative result."
            )

        order = sorted(range(len(hits)), key=lambda i: -scores[i])

        base_doc.append([h.chunk.document_id == question.gold_document_id for h in hits])
        rank_doc.append([hits[i].chunk.document_id == question.gold_document_id for i in order])

        if question.gold_chunk_id:
            base_chunk.append([h.chunk.id == question.gold_chunk_id for h in hits])
            rank_chunk.append([hits[i].chunk.id == question.gold_chunk_id for i in order])

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    return (
        rank_metrics(base_doc),
        rank_metrics(rank_doc),
        rank_metrics(base_chunk),
        rank_metrics(rank_chunk),
        p50,
    )


def main() -> None:
    torch.manual_seed(SEED)
    torch.set_num_threads(4)

    documents = load_corpus()
    chunks = chunk_corpus(documents)
    chunks_by_document: dict[str, list] = {}
    for chunk in chunks:
        chunks_by_document.setdefault(chunk.document_id, []).append(chunk)

    retriever = HybridRetriever(chunks=chunks, embedder=HashingEmbedder())
    retriever.build_vectors()

    dataset = build_dataset()
    print(f"train questions {len(dataset.train)}  test questions {len(dataset.test)}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=1)

    print("\nBEFORE fine-tuning (pretrained MS MARCO weights), held-out documents:")
    bd_before, rd_before, bc_before, rc_before, _ = evaluate(
        model, tokenizer, dataset.test, retriever
    )
    print(f"  document | hybrid      {fmt(bd_before)}")
    print(f"  document | + pretrained {fmt(rd_before)}")
    print(f"  chunk    | hybrid      {fmt(bc_before)}")
    print(f"  chunk    | + pretrained {fmt(rc_before)}")

    pairs = build_pairs(dataset.train, retriever, chunks_by_document)
    positives = sum(1 for p in pairs if p.label == 1.0)
    print(
        f"\ntraining pairs {len(pairs)}  ({positives} positive, {len(pairs) - positives} hard negative)"
    )

    loader = DataLoader(
        PairDataset(pairs, tokenizer),
        batch_size=BATCH_SIZE,
        shuffle=True,
        collate_fn=collate(tokenizer),
    )
    optimiser = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    model.train()
    for epoch in range(EPOCHS):
        total = 0.0
        started = time.perf_counter()
        for batch in loader:
            labels = batch.pop("labels")
            optimiser.zero_grad()
            logits = model(**batch).logits.squeeze(-1)
            loss = loss_fn(logits, labels)
            loss.backward()
            optimiser.step()
            total += loss.detach().item()
        print(
            f"  epoch {epoch + 1}  loss {total / len(loader):.4f}  ({time.perf_counter() - started:.0f}s)"
        )

    print("\nAFTER fine-tuning, held-out documents:")
    bd, rd, bc, rc, p50 = evaluate(model, tokenizer, dataset.test, retriever)
    print(f"  document | hybrid      {fmt(bd)}")
    print(f"  document | + finetuned {fmt(rd)}")
    print(f"  chunk    | hybrid      {fmt(bc)}")
    print(f"  chunk    | + finetuned {fmt(rc)}")
    print(f"  re-rank latency p50 {p50:.0f}ms for {CANDIDATES} candidates")
    base_after, rerank_after = bc, rc

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "metrics.json").write_text(
        json.dumps(
            {
                "base_model": BASE_MODEL,
                "training_pairs": len(pairs),
                "held_out_documents": len({q.group for q in dataset.test}),
                "document_level": {"hybrid": bd, "reranked": rd},
                "chunk_level": {
                    "hybrid": bc,
                    "pretrained_reranked": rc_before,
                    "finetuned_reranked": rc,
                },
                "rerank_latency_p50_ms": round(p50, 1),
                "candidates": CANDIDATES,
            },
            indent=2,
        )
        + "\n"
    )

    improved = rerank_after["mrr"] > base_after["mrr"]
    print(
        f"\nVERDICT: fine-tuned re-ranking {'IMPROVES' if improved else 'DOES NOT IMPROVE'} MRR "
        f"({base_after['mrr']:.3f} -> {rerank_after['mrr']:.3f})"
    )

    export_onnx(model, tokenizer)


def export_onnx(model, tokenizer) -> None:
    model.eval()
    # Varied pairs spanning clearly relevant to clearly irrelevant. Four copies
    # of one pair produce four identical logits, and a parity check where every
    # row scores the same passes while testing nothing - the same weakness
    # already caught once in the classifier's parity sample and reproduced here.
    queries = [
        "why is the connection pool exhausted",
        "why is the connection pool exhausted",
        "how long is the observation period between regions",
        "what severity is a tier 0 outage",
    ]
    passages = [
        "Callers hold connections longer than the pool can recycle them. Wait "
        "time climbs first, available connections reach zero.",
        "A certificate has expired. Clients refuse the handshake, and failure is "
        "total and instantaneous rather than gradual.",
        "Tier 0 and Tier 1 services roll out by region, one region at a time, "
        "with a minimum observation period between regions.",
        "Severity 1 is a Tier 0 service unavailable or materially degraded for "
        "customers. It pages immediately, at any hour.",
    ]
    sample = tokenizer(
        queries,
        passages,
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    inputs = (sample["input_ids"], sample["attention_mask"], sample["token_type_ids"])
    with torch.no_grad():
        expected = model(**sample).logits.squeeze(-1).tolist()

    path = MODEL_DIR / "reranker.onnx"
    torch.onnx.export(
        model,
        inputs,
        str(path),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "token_type_ids": {0: "batch", 1: "sequence"},
            "logits": {0: "batch"},
        },
        opset_version=17,
    )
    (MODEL_DIR / "parity_sample.json").write_text(
        json.dumps(
            {
                "input_ids": sample["input_ids"].tolist(),
                "attention_mask": sample["attention_mask"].tolist(),
                "token_type_ids": sample["token_type_ids"].tolist(),
                "expected_logits": expected,
                "max_length": MAX_LENGTH,
            },
            indent=2,
        )
        + "\n"
    )
    tokenizer.save_pretrained(MODEL_DIR)
    print(
        f"exported {path.name} ({path.stat().st_size / 1024 / 1024:.0f} MB) + tokenizer + parity sample"
    )


if __name__ == "__main__":
    main()
