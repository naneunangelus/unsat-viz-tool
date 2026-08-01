import json
from pathlib import Path

from clingo import ast

from .ast_tools import (
    is_rule_statement,
    rule_start_line,
    variables_in_body,
)
from .models import RuleMeta, TransformResult, to_jsonable


EFFECT_PREDICATE_MAP = {
    "node": "node",
    "link": "edge",
    "edge": "edge",
}

IGNORED_EFFECT_PREDICATES = {
    "colour",
    "color",
    "chosenColour",
    "notchosenColour",
    "colored",
    "omitted",
    "notomitted",
    "guessedomitted",
    "output_omitted",
}


def is_f_rule(statement: ast.AST) -> bool:
    return is_rule_statement(statement) and str(statement.head).strip() == "f"


def is_negated_head_literal(literal: str, head: str) -> bool:
    return literal.strip() == f"not {head.strip()}"


def constraint_body_literals(meta: RuleMeta) -> list[str]:
    return [
        literal
        for literal in meta.body_literals
        if not is_negated_head_literal(literal, meta.head)
    ]


def body_to_program(body_literals: list[str]) -> str:
    return ", ".join(body_literals)


def unsat_atom(meta: RuleMeta) -> str:
    args = ", ".join([meta.name] + meta.variables)
    return f"unsat({args})"


def restored_constraint(meta: RuleMeta) -> str:
    body = body_to_program(constraint_body_literals(meta))
    return f":- {body}."


def relaxed_rule(meta: RuleMeta) -> str:
    body = body_to_program(constraint_body_literals(meta))
    return f"{unsat_atom(meta)} :- {body}."


def weak_constraint(meta: RuleMeta) -> str:
    atom = unsat_atom(meta)

    if meta.variables:
        terms = ", ".join(meta.variables)
        return f":~ {atom}. [1@1, {terms}]"

    return f":~ {atom}. [1@1]"


def literal_symbolic_function(literal: ast.AST) -> ast.AST | None:
    if literal.ast_type != ast.ASTType.Literal:
        return None

    if literal.atom.ast_type != ast.ASTType.SymbolicAtom:
        return None

    symbol = literal.atom.symbol

    if symbol.ast_type != ast.ASTType.Function:
        return None

    return symbol


def effect_from_literal(literal: ast.AST) -> str | None:
    symbol = literal_symbolic_function(literal)

    if symbol is None:
        return None

    predicate = symbol.name

    if predicate in IGNORED_EFFECT_PREDICATES:
        return None

    effect_predicate = EFFECT_PREDICATE_MAP.get(predicate)

    if effect_predicate is None:
        return None

    args = [str(arg).replace(" ", "") for arg in symbol.arguments]

    if not args:
        return effect_predicate

    return f"{effect_predicate}({','.join(args)})"


def infer_effects(body: list[ast.AST]) -> list[str]:
    effects: list[str] = []

    for literal in body:
        effect = effect_from_literal(literal)

        if effect is not None and effect not in effects:
            effects.append(effect)

    return effects


def extract_rule_meta(program: str) -> list[RuleMeta]:
    metas: list[RuleMeta] = []
    counter = 1

    def on_statement(statement: ast.AST) -> None:
        nonlocal counter

        if not is_f_rule(statement):
            return

        body = list(statement.body)
        variables = variables_in_body(body)
        effects = infer_effects(body)

        metas.append(
            RuleMeta(
                name=f"unsat_rule_{counter}",
                variables=variables,
                effects=effects,
                rule_line=rule_start_line(statement),
                head=str(statement.head),
                body_literals=[str(literal) for literal in body],
            )
        )

        counter += 1

    ast.parse_string(program, on_statement)
    return metas


def f_rule_line_spans(program: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []

    def on_statement(statement: ast.AST) -> None:
        if not is_f_rule(statement):
            return

        spans.append(
            (
                statement.location.begin.line,
                statement.location.end.line,
            )
        )

    ast.parse_string(program, on_statement)
    return spans


def remove_line_spans(program: str, spans: list[tuple[int, int]]) -> str:
    lines = program.splitlines()
    removed: set[int] = set()

    for begin, end in spans:
        for line_no in range(begin, end + 1):
            removed.add(line_no)

    kept_lines = [
        line
        for index, line in enumerate(lines, start=1)
        if index not in removed
    ]

    return "\n".join(kept_lines).rstrip() + "\n"


def transform_program(program: str) -> TransformResult:
    metas = extract_rule_meta(program)

    restored_parts: list[str] = []
    relaxed_parts: list[str] = []

    for meta in metas:
        restored_parts.append(f"% restored constraint: {meta.name}")
        restored_parts.append(restored_constraint(meta))
        restored_parts.append("")

        relaxed_parts.append(f"% relaxation: {meta.name}")
        relaxed_parts.append(relaxed_rule(meta))
        relaxed_parts.append(weak_constraint(meta))
        relaxed_parts.append("")

    spans = f_rule_line_spans(program)
    cleaned_program = remove_line_spans(program, spans)

    return TransformResult(
        meta=metas,
        restored_program="\n".join(restored_parts).strip() + "\n",
        relaxed_program="\n".join(relaxed_parts).strip() + "\n",
        cleaned_program=cleaned_program,
    )


def write_meta_json(input_path: str | Path, output_path: str | Path) -> list[RuleMeta]:
    input_path = Path(input_path)
    output_path = Path(output_path)

    program = input_path.read_text(encoding="utf-8")
    metas = extract_rule_meta(program)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(metas, default=to_jsonable, indent=2),
        encoding="utf-8",
    )

    return metas


def write_transform_outputs(
    encoding_path: str | Path,
    out_dir: str | Path,
) -> TransformResult:
    encoding_path = Path(encoding_path)
    out_dir = Path(out_dir)

    program = encoding_path.read_text(encoding="utf-8")
    result = transform_program(program)

    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "meta.json").write_text(
        json.dumps(result.meta, default=to_jsonable, indent=2),
        encoding="utf-8",
    )

    (out_dir / "restored.lp").write_text(
        result.restored_program,
        encoding="utf-8",
    )

    (out_dir / "relaxed.lp").write_text(
        result.relaxed_program,
        encoding="utf-8",
    )

    (out_dir / "cleaned_encoding.lp").write_text(
        result.cleaned_program,
        encoding="utf-8",
    )

    return result
