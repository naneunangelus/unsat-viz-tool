import json
import re
from pathlib import Path

from .models import RuleMeta, Violation


EFFECT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$")


HIGHLIGHT_RULES = """
attr(edge, E, color, red) :-
    edge(E),
    violated_edge(E).

attr(edge, E, penwidth, 5) :-
    edge(E),
    violated_edge(E).

attr(node, X, color, red) :-
    node(X),
    violated_node(X).

attr(node, X, penwidth, 4) :-
    node(X),
    violated_node(X).
""".strip()

OMITTED_STYLE_RULES = """
attr(node, X, fillcolor, lightgray) :-
    node(X),
    omitted(node(X)),
    not violated_node(X).

attr(node, X, color, gray) :-
    node(X),
    omitted(node(X)),
    not violated_node(X).

attr(node, X, fontcolor, gray) :-
    node(X),
    omitted(node(X)),
    not violated_node(X).

attr(edge, E, color, lightgray) :-
    edge(E),
    omitted_edge(E),
    not violated_edge(E).

attr(edge, E, style, dashed) :-
    edge(E),
    omitted_edge(E),
    not violated_edge(E).

omitted_edge((X,Y)) :-
    omitted(link(X,Y)),
    X < Y.

omitted_edge((Y,X)) :-
    omitted(link(X,Y)),
    Y < X.
""".strip()


def load_meta(path: str | Path) -> list[RuleMeta]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [RuleMeta(**item) for item in data]


def load_violations(path: str | Path) -> list[Violation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Violation(**item) for item in data]


def substitution_map(meta: RuleMeta, violation: Violation) -> dict[str, str]:
    if len(meta.variables) != len(violation.arguments):
        raise ValueError(
            f"Violation {violation.atom} does not match variables for rule {meta.name}"
        )

    return dict(zip(meta.variables, violation.arguments))


def substitute_term(term: str, values: dict[str, str]) -> str:
    result = term
    for variable, value in values.items():
        result = re.sub(rf"\b{re.escape(variable)}\b", value, result)
    return result


def effect_to_fact(effect: str, values: dict[str, str]) -> str:
    match = EFFECT_RE.match(effect.strip())

    if not match:
        raise ValueError(f"Invalid effect annotation: {effect}")

    kind = match.group(1)
    args = substitute_term(match.group(2), values)

    if kind == "node":
        return f"violated_node({args})."

    if kind == "edge":
        return f"violated_edge(({args}))."

    raise ValueError(f"Unsupported effect kind: {kind}")


def generate_overlay(meta: list[RuleMeta], violations: list[Violation]) -> str:
    meta_by_name = {item.name: item for item in meta}

    facts: list[str] = []

    for violation in violations:
        rule_meta = meta_by_name.get(violation.name)

        if rule_meta is None:
            raise ValueError(f"No metadata found for violation rule: {violation.name}")

        values = substitution_map(rule_meta, violation)

        for effect in rule_meta.effects:
            facts.append(effect_to_fact(effect, values))

    unique_facts = sorted(set(facts))

    parts = []
    parts.append("% generated violation facts")
    parts.extend(unique_facts)
    parts.append("")

    parts.append("% omitted-part styling")
    parts.append(OMITTED_STYLE_RULES)
    parts.append("")

    parts.append("% standard violation highlighting")
    parts.append(HIGHLIGHT_RULES)
    parts.append("")

    return "\n".join(parts)


def write_overlay(
    meta_path: str | Path,
    violations_path: str | Path,
    out_path: str | Path,
) -> str:
    meta = load_meta(meta_path)
    violations = load_violations(violations_path)

    overlay = generate_overlay(meta, violations)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(overlay, encoding="utf-8")

    return overlay