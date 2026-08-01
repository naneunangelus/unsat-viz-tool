import json
from dataclasses import dataclass
from pathlib import Path

import clingo

from .models import Violation, to_jsonable


@dataclass(frozen=True)
class CapturedModel:
    """
    Immutable copy of one answer set returned by Clingo.

    A clingo.Model object is only valid while processing the model,
    so all symbols must be copied immediately.
    """

    symbols: tuple[clingo.Symbol, ...]
    cost: tuple[int, ...]
    optimality_proven: bool


def is_better_cost(
    cost: tuple[int, ...],
    best_cost: tuple[int, ...] | None,
) -> bool:
    if best_cost is None:
        return True

    return cost < best_cost


def capture_model(model: clingo.Model) -> CapturedModel:
    """
    Copy the complete answer set while the clingo.Model is valid.

    atoms=True is deliberately used instead of shown=True. This captures
    every true symbolic atom, regardless of #show declarations.
    """
    return CapturedModel(
        symbols=tuple(model.symbols(atoms=True)),
        cost=tuple(model.cost),
        optimality_proven=model.optimality_proven,
    )


def extract_unsat_symbols(
    symbols: tuple[clingo.Symbol, ...] | list[clingo.Symbol],
) -> list[Violation]:
    violations: list[Violation] = []

    for symbol in symbols:
        if symbol.type != clingo.SymbolType.Function:
            continue

        if symbol.name != "unsat":
            continue

        if len(symbol.arguments) < 1:
            continue

        name = str(symbol.arguments[0])
        arguments = [str(argument) for argument in symbol.arguments[1:]]

        violations.append(
            Violation(
                atom=str(symbol),
                name=name,
                arguments=arguments,
            )
        )

    return sorted(
        violations,
        key=lambda violation: violation.atom,
    )


def symbol_as_fact(symbol: clingo.Symbol) -> str:
    """
    Serialize a symbolic atom as an ASP fact.
    """
    if symbol.type != clingo.SymbolType.Function:
        raise ValueError(
            f"Cannot serialize non-function symbol as an ASP fact: {symbol}"
        )

    return f"{symbol}."


def model_atom_strings(model: CapturedModel) -> list[str]:
    """
    Return all symbolic atoms in deterministic order.

    Duplicate atoms are removed defensively.
    """
    return sorted(
        {
            str(symbol)
            for symbol in model.symbols
            if symbol.type == clingo.SymbolType.Function
        }
    )


def write_model_snapshot(
    model: CapturedModel,
    lp_path: str | Path,
    json_path: str | Path,
) -> None:
    """
    Write the complete selected answer set in two formats.

    selected_model.lp is consumed by the render stage.
    selected_model.json is useful for inspection and debugging.
    """
    lp_path = Path(lp_path)
    json_path = Path(json_path)

    lp_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    atoms = model_atom_strings(model)

    lp_lines = [
        "% Complete answer set selected during the relaxed solve.",
        "% Rendering must use this file instead of solving the domain",
        "% encoding again.",
        f"% Optimization cost: {list(model.cost)}",
        "",
    ]

    lp_lines.extend(f"{atom}." for atom in atoms)
    lp_lines.append("")

    lp_path.write_text(
        "\n".join(lp_lines),
        encoding="utf-8",
    )

    json_path.write_text(
        json.dumps(
            {
                "cost": list(model.cost),
                "optimality_proven": model.optimality_proven,
                "atoms": atoms,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_violation_files(
    model: CapturedModel,
    out_dir: str | Path,
) -> list[Violation]:
    """
    Extract and write violations from the same captured model that is
    persisted for rendering.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    violations = extract_unsat_symbols(model.symbols)

    violations_lp = "\n".join(
        f"{violation.atom}."
        for violation in violations
    )

    if violations_lp:
        violations_lp += "\n"

    (out_dir / "violations.lp").write_text(
        violations_lp,
        encoding="utf-8",
    )

    (out_dir / "violations.json").write_text(
        json.dumps(
            violations,
            default=to_jsonable,
            indent=2,
        ),
        encoding="utf-8",
    )

    return violations


def load_and_ground(files: list[str | Path], options: list[str]) -> clingo.Control:
    ctl = clingo.Control(options)

    for file in files:
        path = Path(file)

        if not path.is_file():
            raise FileNotFoundError(f"ASP input file not found: {path}")

        ctl.load(str(path))

    ctl.ground([("base", [])])
    return ctl


def solve_relaxed_program_one(
    files: list[str | Path],
) -> CapturedModel:
    """
    Find one optimal relaxed model and capture its complete answer set.

    The selected model is the best-cost model encountered during the full
    optimization run.
    """
    ctl = load_and_ground(
        files=files,
        options=[
            "--opt-mode=opt",
            "--models=0",
        ],
    )

    selected_model: CapturedModel | None = None
    best_cost: tuple[int, ...] | None = None

    with ctl.solve(yield_=True) as handle:
        for model in handle:
            candidate = capture_model(model)

            if is_better_cost(candidate.cost, best_cost):
                best_cost = candidate.cost
                selected_model = candidate

        result = handle.get()

    if not result.satisfiable:
        raise RuntimeError("Relaxed program is still unsatisfiable.")

    if selected_model is None:
        raise RuntimeError("Clingo returned no answer set.")

    selected_model = CapturedModel(
        symbols=selected_model.symbols,
        cost=selected_model.cost,
        optimality_proven=result.exhausted,
    )

    return selected_model


def violation_signature(model: CapturedModel) -> tuple[str, ...]:
    """
    Distinguish explanations using complete grounded violation atoms.

    Using only the rule name would incorrectly merge violations of the
    same rule involving different graph elements.
    """
    return tuple(
        violation.atom
        for violation in extract_unsat_symbols(model.symbols)
    )


def solve_relaxed_program_diverse_optimal(
    files: list[str | Path],
    max_models: int = 200,
) -> list[CapturedModel]:
    """
    Capture representative complete models for distinct optimal
    violation sets.

    optN first proves the optimum and then enumerates optimal models.
    Only models with optimality_proven=True are exported.
    """
    if max_models < 1:
        raise ValueError("max_models must be at least 1")

    ctl = load_and_ground(
        files=files,
        options=[
            "--opt-mode=optN",
            "--models=0",
        ],
    )

    representatives: dict[tuple[str, ...], CapturedModel] = {}

    with ctl.solve(yield_=True) as handle:
        for model in handle:
            if not model.optimality_proven:
                continue

            captured = capture_model(model)
            signature = violation_signature(captured)

            representatives.setdefault(signature, captured)

            if len(representatives) >= max_models:
                handle.cancel()
                break

        result = handle.get()

    if not result.satisfiable:
        raise RuntimeError("Relaxed program is still unsatisfiable.")

    if not representatives:
        raise RuntimeError(
            "Clingo did not return any proven optimal model."
        )

    return list(representatives.values())


def write_captured_model_outputs(
    model: CapturedModel,
    out_dir: str | Path,
) -> list[Violation]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_model_snapshot(
        model=model,
        lp_path=out_dir / "selected_model.lp",
        json_path=out_dir / "selected_model.json",
    )

    return write_violation_files(
        model=model,
        out_dir=out_dir,
    )


def write_violations(
    instance_path: str | Path,
    omission_path: str | Path,
    cleaned_encoding_path: str | Path,
    relaxed_path: str | Path,
    out_dir: str | Path,
    mode: str = "one",
    max_models: int = 200,
) -> list[Violation]:
    """
    Solve the relaxed program and persist both:

    - the complete selected answer set;
    - the violations extracted from that exact answer set.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [
        instance_path,
        omission_path,
        cleaned_encoding_path,
        relaxed_path,
    ]

    if mode == "one":
        selected_model = solve_relaxed_program_one(files)

        return write_captured_model_outputs(
            model=selected_model,
            out_dir=out_dir,
        )

    if mode == "diverse-optimal":
        selected_models = solve_relaxed_program_diverse_optimal(
            files=files,
            max_models=max_models,
        )

        for index, model in enumerate(selected_models):
            explanation_dir = out_dir / f"explanation_{index}"

            write_captured_model_outputs(
                model=model,
                out_dir=explanation_dir,
            )

        # Keep a top-level default explanation for compatibility with the
        # existing overlay and render commands.
        first_model = selected_models[0]

        return write_captured_model_outputs(
            model=first_model,
            out_dir=out_dir,
        )

    raise ValueError(f"Unknown solve mode: {mode}")