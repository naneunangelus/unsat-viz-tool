from dataclasses import dataclass, asdict, is_dataclass
from typing import Any


@dataclass
class AnnotationBlock:
    name: str
    effects: list[str]
    annotation_line: int
    target_line: int | None = None


@dataclass
class RuleMeta:
    name: str
    variables: list[str]
    effects: list[str]
    rule_line: int
    head: str
    body_literals: list[str]


@dataclass
class TransformResult:
    meta: list[RuleMeta]
    restored_program: str
    relaxed_program: str
    cleaned_program: str


@dataclass
class Violation:
    atom: str
    name: str
    arguments: list[str]


def to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    return obj