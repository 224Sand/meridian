"""Tokenisation shared by lexical retrieval and the offline embedder.

Operational prose is full of identifiers - `db.pool.wait_ms`, `max.poll.records`,
`idle in transaction`. A tokeniser that splits on every non-alphanumeric
character destroys exactly the terms an operator would search for, so identifiers
are emitted whole AND split into parts. A query for "pool wait" and a query for
"db.pool.wait_ms" then both reach the same chunk.
"""

from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"[a-z0-9]+(?:[._][a-z0-9]+)+")
_WORD = re.compile(r"[a-z0-9]+")

#: Deliberately short. An aggressive stop list removes "not", "no" and "never",
#: which in a runbook are the difference between an instruction and its opposite.
STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those of in on at to for
    from by with as is are was were be been being it its into over under
    """.split()
)


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = []

    identifiers = _IDENTIFIER.findall(lowered)
    for identifier in identifiers:
        tokens.append(identifier)
        tokens.extend(part for part in re.split(r"[._]", identifier) if part)

    remainder = _IDENTIFIER.sub(" ", lowered)
    tokens.extend(_WORD.findall(remainder))

    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]
