import re

from .models import AnnotationBlock


UNSAT_RE = re.compile(r"^\s*%!\s*unsat\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
AFFECTS_RE = re.compile(r"^\s*%!\s*affects\s+(.+?)\s*$")


def parse_annotation_blocks(program: str) -> dict[int, AnnotationBlock]:
    """
    Returns mapping:

        target_rule_line -> AnnotationBlock

    The target rule is the first non-empty, non-comment line after the annotation block.
    """

    blocks: dict[int, AnnotationBlock] = {}
    pending: AnnotationBlock | None = None

    for line_no, line in enumerate(program.splitlines(), start=1):
        stripped = line.strip()

        unsat_match = UNSAT_RE.match(line)
        if unsat_match:
            pending = AnnotationBlock(
                name=unsat_match.group(1),
                effects=[],
                annotation_line=line_no,
            )
            continue

        affects_match = AFFECTS_RE.match(line)
        if affects_match and pending is not None:
            pending.effects.append(affects_match.group(1))
            continue

        if pending is not None:
            if not stripped:
                continue
            if stripped.startswith("%"):
                continue

            pending.target_line = line_no
            blocks[line_no] = pending
            pending = None

    return blocks