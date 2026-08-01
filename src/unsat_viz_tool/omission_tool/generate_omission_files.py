#!/usr/bin/env python3
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from clingo import ast


INTERNAL_PREDS = {"f", "omitted", "guessedomitted", "notomitted", "output_omitted"}


@dataclass(frozen=True)
class Atom:
    pred: str
    args: tuple[str, ...]

    @property
    def key(self):
        return self.pred, len(self.args)

    def render(self):
        return self.pred if not self.args else f"{self.pred}({','.join(self.args)})"


@dataclass
class RuleInfo:
    head: Atom | None
    head_text: str
    body_atoms: list[Atom]
    body_texts: list[str]


def csv_set(text: str) -> set[str]:
    return {x.strip() for x in text.split(",") if x.strip()}


def atom_from_literal(lit) -> Atom | None:
    if lit.ast_type != ast.ASTType.Literal:
        return None
    if lit.atom.ast_type != ast.ASTType.SymbolicAtom:
        return None

    sym = lit.atom.symbol
    if sym.ast_type != ast.ASTType.Function:
        return None

    pred = sym.name
    if pred in INTERNAL_PREDS:
        return None

    return Atom(pred, tuple(str(arg).replace(" ", "") for arg in sym.arguments))


def parse_rules(program: str) -> list[RuleInfo]:
    rules: list[RuleInfo] = []

    def on_statement(stmt):
        if stmt.ast_type != ast.ASTType.Rule:
            return

        head = atom_from_literal(stmt.head) if stmt.head.ast_type == ast.ASTType.Literal else None
        head_text = str(stmt.head).strip()
        body_atoms = [a for lit in stmt.body if (a := atom_from_literal(lit)) is not None]
        body_texts = [str(lit).strip() for lit in stmt.body]

        rules.append(RuleInfo(head, head_text, body_atoms, body_texts))

    ast.parse_string(program, on_statement)
    return rules


def transformed_program(rules: list[RuleInfo]) -> str:
    out = []

    for rule in rules:
        if not rule.body_texts:
            out.append(f"{rule.head_text}.")
            continue

        guards = [f"not omitted({atom.render()})" for atom in rule.body_atoms]
        body = ", ".join(rule.body_texts + guards)

        if rule.head_text == "#false":
            out.append(f"f :- {body}, not f.")
        else:
            out.append(f"{rule.head_text} :- {body}.")

    return "\n".join(out) + "\n"


def first_target_atom(rules: list[RuleInfo], target_pred: str, target_arity: int) -> Atom:
    for rule in rules:
        atoms = ([rule.head] if rule.head else []) + rule.body_atoms
        for atom in atoms:
            if atom.pred == target_pred and len(atom.args) == target_arity:
                return atom

    raise SystemExit(f"Error: target predicate {target_pred}/{target_arity} not found")


def atoms_in_rule(rule: RuleInfo) -> list[Atom]:
    return ([rule.head] if rule.head else []) + rule.body_atoms


def canonical_shapes(
    rules: list[RuleInfo],
    target: Atom,
    context_preds: set[str],
) -> list[Atom]:
    shapes: dict[tuple[str, int], Atom] = {target.key: target}

    # First collect ordinary first-seen shapes.
    for rule in rules:
        for atom in atoms_in_rule(rule):
            if atom.pred in context_preds or atom.pred in INTERNAL_PREDS:
                continue
            shapes.setdefault(atom.key, atom)

    # Improve unary shapes that share a variable with the target:
    # colored(X) with node(X) becomes colored(N).
    target_name = target.args[0] if len(target.args) == 1 else None

    if target_name is not None:
        for rule in rules:
            target_atoms = [
                atom for atom in rule.body_atoms
                if atom.key == target.key
            ]

            for t in target_atoms:
                t_var = t.args[0]

                for atom in atoms_in_rule(rule):
                    if atom.key == target.key:
                        continue
                    if atom.pred in context_preds or atom.pred in INTERNAL_PREDS:
                        continue
                    if len(atom.args) == 1 and atom.args[0] == t_var:
                        shapes[atom.key] = Atom(atom.pred, (target_name,))

    ordered = [shapes[target.key]]
    ordered.extend(atom for key, atom in shapes.items() if key != target.key)
    return ordered


def guess_atoms_to_omit_forgrounding(shapes: list[Atom]) -> str:
    return "".join(f"{{omitted({a.render()})}} :- {a.render()}.\n" for a in shapes)


def guess_atoms_to_omit(shapes: list[Atom]) -> str:
    return "".join(
        f"{{guessedomitted({a.render()})}} :- elem(atom({a.render()})).\n"
        for a in shapes
    )


def matching_context_atom(var: str, atoms: list[Atom], context_preds: set[str]) -> Atom | None:
    for atom in atoms:
        if atom.pred in context_preds and var in atom.args:
            return atom
    return None


def subst_atom(atom: Atom, mapping: dict[str, str]) -> Atom:
    return Atom(atom.pred, tuple(mapping.get(arg, arg) for arg in atom.args))


def dependency_rules(
    rules: list[RuleInfo],
    shapes: list[Atom],
    target: Atom,
    context_preds: set[str],
) -> str:
    shape_by_key = {s.key: s for s in shapes}
    generated = []
    seen = set()

    for shape in shapes:
        if shape.key == target.key:
            continue

        for pos in range(len(shape.args)):
            found = None

            for rule in rules:
                atoms = atoms_in_rule(rule)

                for candidate in atoms:
                    if candidate.key != shape.key:
                        continue

                    for t in rule.body_atoms:
                        if t.key != target.key:
                            continue

                        if pos < len(candidate.args) and candidate.args[pos] in t.args:
                            found = rule, candidate, t
                            break

                    if found:
                        break

                if found:
                    break

            if not found:
                continue

            rule, candidate, target_occurrence = found
            target_var = candidate.args[pos]
            canonical_target_var = shape.args[pos]

            mapping = {target_var: canonical_target_var}
            canonical_target = subst_atom(target_occurrence, mapping)

            body = [f"guessedomitted({canonical_target.render()})"]

            missing_support = False

            for i, arg in enumerate(candidate.args):
                if i == pos:
                    continue

                canonical_arg = shape.args[i]
                mapping[arg] = canonical_arg

                context = matching_context_atom(arg, rule.body_atoms, context_preds)

                if context is not None:
                    body.append(f"elem(atom({subst_atom(context, mapping).render()}))")
                else:
                    missing_support = True

            if missing_support:
                body.append(f"elem(atom({shape.render()}))")

            line = f"guessedomitted({shape.render()}) :- {', '.join(body)}."

            if line not in seen:
                seen.add(line)
                generated.append(line)

    return "\n".join(generated) + ("\n" if generated else "")


def main():
    parser = argparse.ArgumentParser(
        description="Generate omission-tool files from a simple ASP encoding."
    )
    parser.add_argument("encoding")
    parser.add_argument("target_predicate")
    parser.add_argument("--target-arity", type=int, required=True)
    parser.add_argument("--context-preds", default="")
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--main-name", default=None)
    args = parser.parse_args()

    encoding = Path(args.encoding)
    if not encoding.is_file():
        print(f"Error: encoding not found: {encoding}", file=sys.stderr)
        raise SystemExit(1)

    program = encoding.read_text(encoding="utf-8")
    rules = parse_rules(program)
    context_preds = csv_set(args.context_preds)

    target = first_target_atom(rules, args.target_predicate, args.target_arity)
    shapes = canonical_shapes(rules, target, context_preds)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    main_name = args.main_name or f"{encoding.stem}_main.lp"

    (out_dir / main_name).write_text(transformed_program(rules), encoding="utf-8")
    (out_dir / "guess_atoms_to_omit_forgrounding.lp").write_text(
        guess_atoms_to_omit_forgrounding(shapes),
        encoding="utf-8",
    )
    (out_dir / "guess_atoms_to_omit.lp").write_text(
        guess_atoms_to_omit(shapes),
        encoding="utf-8",
    )
    (out_dir / "infer_omitted_atoms.lp").write_text(
        dependency_rules(rules, shapes, target, context_preds),
        encoding="utf-8",
    )

    print(f"Wrote {out_dir / main_name}")
    print(f"Wrote {out_dir / 'guess_atoms_to_omit_forgrounding.lp'}")
    print(f"Wrote {out_dir / 'guess_atoms_to_omit.lp'}")
    print(f"Wrote {out_dir / 'infer_omitted_atoms.lp'}")


if __name__ == "__main__":
    main()
