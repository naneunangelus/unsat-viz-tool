import json
from pathlib import Path

import clingo

from .models import Violation, to_jsonable


def is_better_cost(cost: list[int], best_cost: list[int] | None) -> bool:
    if best_cost is None:
        return True
    return tuple(cost) < tuple(best_cost)


def extract_unsat_symbols(symbols: list[clingo.Symbol]) -> list[Violation]:
    violations: list[Violation] = []

    for symbol in symbols:
        if symbol.type != clingo.SymbolType.Function:
            continue

        if symbol.name != "unsat":
            continue

        if len(symbol.arguments) < 1:
            continue

        name = str(symbol.arguments[0])
        args = [str(arg) for arg in symbol.arguments[1:]]

        violations.append(
            Violation(
                atom=str(symbol),
                name=name,
                arguments=args,
            )
        )

    return violations


def solve_relaxed_program_one(
    files: list[str | Path],
) -> list[Violation]:
    ctl = clingo.Control(["--opt-mode=opt"])

    for file in files:
        ctl.load(str(file))

    ctl.ground([("base", [])])

    best_cost: list[int] | None = None
    best_symbols: list[clingo.Symbol] = []

    with ctl.solve(yield_=True) as handle:
        for model in handle:
            cost = list(model.cost)

            if is_better_cost(cost, best_cost):
                best_cost = cost
                best_symbols = model.symbols(atoms=True)

        result = handle.get()

    if not result.satisfiable:
        raise RuntimeError("Relaxed program is still unsatisfiable.")

    return extract_unsat_symbols(best_symbols)

def violation_signature(violations: list[Violation]) -> tuple[str, ...]:
    return tuple(sorted(v.name for v in violations))

def solve_relaxed_program_diverse_optimal(
    files: list[str | Path],
    max_models: int = 200,
) -> list[list[Violation]]:
    ctl = clingo.Control(["--opt-mode=optN", "--models=0"])

    for file in files:
        ctl.load(str(file))

    ctl.ground([("base", [])])

    best_cost = None
    representatives: dict[tuple[str, ...], list[Violation]] = {}
    seen_models = 0

    with ctl.solve(yield_=True) as handle:
        for model in handle:
            cost = list(model.cost)

            if is_better_cost(cost, best_cost):
                best_cost = cost
                representatives.clear()

            if cost != best_cost:
                continue

            violations = extract_unsat_symbols(model.symbols(atoms=True))
            signature = violation_signature(violations)

            if signature not in representatives:
                representatives[signature] = violations

            seen_models += 1
            if seen_models >= max_models:
                break

        result = handle.get()

    if not result.satisfiable:
        raise RuntimeError("Relaxed program is still unsatisfiable.")

    return list(representatives.values())

def write_violations(
    instance_path: str | Path,
    omission_path: str | Path,
    cleaned_encoding_path: str | Path,
    relaxed_path: str | Path,
    out_dir: str | Path,
    mode: str = "one",
    max_models: int = 200,
) -> list[Violation]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [
        instance_path,
        omission_path,
        cleaned_encoding_path,
        relaxed_path,
    ]

    if mode == "one":
        violations = solve_relaxed_program_one(files)

    elif mode == "diverse-optimal":
        violation_sets = solve_relaxed_program_diverse_optimal(
            files=files,
            max_models=max_models,
        )

        for index, model_violations in enumerate(violation_sets):
            model_dir = out_dir / f"explanation_{index}"
            model_dir.mkdir(parents=True, exist_ok=True)

            violations_lp = "\n".join(f"{v.atom}." for v in model_violations)
            if violations_lp:
                violations_lp += "\n"

            (model_dir / "violations.lp").write_text(
                violations_lp,
                encoding="utf-8",
            )

            (model_dir / "violations.json").write_text(
                json.dumps(model_violations, default=to_jsonable, indent=2),
                encoding="utf-8",
            )

        violations = violation_sets[0] if violation_sets else []

    else:
        raise ValueError(f"Unknown solve mode: {mode}")

    violations_lp = "\n".join(f"{v.atom}." for v in violations)
    if violations_lp:
        violations_lp += "\n"

    (out_dir / "violations.lp").write_text(
        violations_lp,
        encoding="utf-8",
    )

    (out_dir / "violations.json").write_text(
        json.dumps(violations, default=to_jsonable, indent=2),
        encoding="utf-8",
    )

    return violations