"""Pre-annotated block markers, as produced by the upstream analyzer:

    /*BLOCKID 1:2645661869534515, Proc SQL, Lines: 23 - 7 to 30 : 100%;*/
    ...sas code...
    /*ENDBLOCKID 1:2645661869534515, Proc SQL;*/

When a file carries these markers, the annotated id (`1:2645661869534515`)
becomes the block_id for the step(s) inside the span — replacing the fallback
`b_<n>_<hash8>` — and flows through occurrences, edges, and the Excel export.
Code outside any marker keeps synthetic ids.
"""
import re
from dataclasses import dataclass

_ANNOTATED = re.compile(
    r"/\*BLOCKID\s+([^,*]+?)\s*,([^*]*?)\*/"   # open marker: id, metadata
    r"(.*?)"                                    # the annotated code span
    r"/\*ENDBLOCKID\s+\1\b[^*]*?\*/",           # close marker with the same id
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class Segment:
    block_id: str | None  # annotated id, or None for un-annotated code
    text: str
    meta: str = ""  # the marker's metadata ("Proc SQL, Lines: ...")


def split_annotated(source: str) -> list[Segment]:
    """Split a file into annotated and un-annotated segments, in order."""
    segments: list[Segment] = []
    last = 0
    for m in _ANNOTATED.finditer(source):
        gap = source[last:m.start()]
        if gap.strip():
            segments.append(Segment(None, gap))
        segments.append(Segment(m.group(1).strip(), m.group(3), m.group(2).strip()))
        last = m.end()
    tail = source[last:]
    if tail.strip():
        segments.append(Segment(None, tail))
    if not segments:
        segments.append(Segment(None, source))
    return segments
