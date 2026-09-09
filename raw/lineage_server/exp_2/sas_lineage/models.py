from dataclasses import dataclass, field

PARSED = "PARSED"
NOT_MATCHED = "NOT_MATCHED"
PARTIAL = "PARTIAL"

BLOCK_FLOW = "BLOCK_FLOW"
FILE_FLOW = "FILE_FLOW"


@dataclass
class TableRef:
    name: str  # display name as written in source
    raw: str   # full matched text including dataset options

    @property
    def canonical(self) -> str:
        return self.name.lower()


@dataclass
class TableOccurrence:
    id: str  # "b_1:t_2"
    name: str
    block_id: str
    table_no: int
    role: str  # "read" or "write"

    @property
    def display(self) -> str:
        return f"{self.id}_{self.name}"

    @property
    def canonical(self) -> str:
        return self.name.lower()


@dataclass
class Edge:
    source: str  # occurrence display id
    target: str
    edge_type: str  # BLOCK_FLOW or FILE_FLOW

    @property
    def display(self) -> str:
        return f"{self.source} -> {self.target}"


@dataclass
class BlockResult:
    block_id: str
    status: str = PARSED
    kind: str = ""
    reads: list[TableOccurrence] = field(default_factory=list)
    writes: list[TableOccurrence] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
