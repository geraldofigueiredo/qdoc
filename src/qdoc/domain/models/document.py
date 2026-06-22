from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time

@dataclass(frozen=True)
class Chunk:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None

@dataclass
class Document:
    url: str
    content: str
    service: str
    hash: str
    updated_at: float = field(default_factory=time.time)
    chunks: List[Chunk] = field(default_factory=list)

@dataclass
class SearchResult:
    content: str
    url: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
