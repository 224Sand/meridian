"""Corpus loading and chunking.

Front matter is parsed by hand rather than with a YAML library. The schema here
is a handful of scalar keys, and ADR-0004 makes image size a real constraint, so
a dependency is not worth it. The parser is strict: an unexpected shape raises
rather than being tolerated, because a silently-dropped `id` would surface much
later as a document that can never be cited.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "corpus"

VALID_KINDS = frozenset({"runbook", "postmortem", "policy", "architecture"})
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_KEY_VALUE = re.compile(r"^([a-z_]+):\s*(.*)$")
#: Chunks below this many characters are merged into the preceding chunk. A
#: two-line section retrieved on its own carries a heading and no evidence.
MIN_CHUNK_CHARS = 200


class CorpusError(ValueError):
    """A corpus document is malformed."""


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    kind: str
    title: str
    source_uri: str
    body: str


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    ordinal: int
    heading: str | None
    body: str
    token_count: int


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate.

    Not a tokeniser. A real one would mean a dependency and a model-specific
    vocabulary; this is used for budgeting and for the schema's token_count, both
    of which need consistency rather than exactness. The 1.3 factor approximates
    subword splitting on English technical prose.
    """
    words = len(text.split())
    return max(1, int(words * 1.3))


def parse_front_matter(text: str, *, source: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise CorpusError(f"{source}: missing front matter block")

    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        kv = _KEY_VALUE.match(line)
        if kv is None:
            raise CorpusError(f"{source}: front matter line is not `key: value` -> {line!r}")
        fields[kv.group(1)] = kv.group(2).strip().strip('"')

    body = text[match.end() :].strip()
    return fields, body


def load_document(path: Path) -> Document:
    fields, body = parse_front_matter(path.read_text(encoding="utf-8"), source=path.name)

    for required in ("id", "kind", "title"):
        if not fields.get(required):
            raise CorpusError(f"{path.name}: front matter is missing `{required}`")
    if fields["kind"] not in VALID_KINDS:
        raise CorpusError(
            f"{path.name}: kind {fields['kind']!r} is not one of {sorted(VALID_KINDS)}"
        )
    if not body:
        raise CorpusError(f"{path.name}: document has front matter but no body")

    return Document(
        id=fields["id"],
        kind=fields["kind"],
        title=fields["title"],
        source_uri=f"corpus/{path.parent.name}/{path.name}",
        body=body,
    )


def load_corpus(root: Path | None = None) -> list[Document]:
    """Every document under `root`, ordered by id.

    GAPS.md is skipped: it documents what the corpus deliberately does not
    contain, so indexing it would let the system answer questions about its own
    blind spots using a description of those blind spots.
    """
    directory = root or CORPUS_ROOT
    documents = [
        load_document(path) for path in sorted(directory.rglob("*.md")) if path.name != "GAPS.md"
    ]

    ids = [d.id for d in documents]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise CorpusError(f"duplicate document ids: {sorted(duplicates)}")

    return sorted(documents, key=lambda d: d.id)


def chunk_document(document: Document) -> list[Chunk]:
    """Split on markdown headings.

    Headings are the author's own statement of where one idea ends and the next
    begins, which is a better boundary than a fixed window and costs nothing to
    detect. Sections too short to stand alone are merged backwards so that a
    retrieved chunk always carries evidence rather than just a title.
    """
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in document.body.splitlines():
        if line.startswith("#"):
            sections.append((line.lstrip("#").strip(), []))
        else:
            sections[-1][1].append(line)

    merged: list[tuple[str | None, str]] = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text and heading is None:
            continue
        block = f"{heading}\n\n{text}".strip() if heading else text
        if merged and len(block) < MIN_CHUNK_CHARS:
            previous_heading, previous_block = merged[-1]
            merged[-1] = (previous_heading, f"{previous_block}\n\n{block}")
        else:
            merged.append((heading, block))

    return [
        Chunk(
            id=f"{document.id}#{ordinal:02d}",
            document_id=document.id,
            ordinal=ordinal,
            heading=heading,
            body=block,
            token_count=estimate_tokens(block),
        )
        for ordinal, (heading, block) in enumerate(merged)
        if block
    ]


def chunk_corpus(documents: list[Document]) -> list[Chunk]:
    return [chunk for document in documents for chunk in chunk_document(document)]
