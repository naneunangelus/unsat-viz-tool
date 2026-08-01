import json
import subprocess
from pathlib import Path


CLINGO_SUCCESS_CODES = {10, 30}


def run_command(command: list[str]) -> None:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )


def require_file(
    path: str | Path,
    description: str,
) -> Path:
    result = Path(path)

    if not result.is_file():
        raise FileNotFoundError(
            f"{description} not found: {result}"
        )

    return result


def validate_single_witness(clingo_json: str) -> None:
    """
    Rendering a saved model should result in exactly one deterministic
    visualization witness.
    """
    try:
        data = json.loads(clingo_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Clingo did not return valid JSON."
        ) from exc

    result = data.get("Result")

    if result != "SATISFIABLE":
        raise RuntimeError(
            f"Visualization program returned {result!r}, expected "
            "'SATISFIABLE'."
        )

    calls = data.get("Call", [])
    witnesses = [
        witness
        for call in calls
        for witness in call.get("Witnesses", [])
    ]

    if not witnesses:
        raise RuntimeError(
            "Visualization program produced no witness."
        )

    if len(witnesses) != 1:
        raise RuntimeError(
            "Visualization program produced multiple witnesses. "
            "The saved model is fixed, so viz.lp and overlay.lp should "
            "normally be deterministic."
        )


def write_clingo_json_model(
    model_path: str | Path,
    viz_path: str | Path,
    overlay_path: str | Path,
    out_json_path: str | Path,
) -> None:
    """
    Derive visualization atoms from a fixed answer-set snapshot.

    The domain instance, cleaned encoding, and relaxed encoding are
    intentionally not loaded here. Loading them would solve the domain
    problem again and could produce a different model.
    """
    model_path = require_file(
        model_path,
        "selected model snapshot",
    )
    viz_path = require_file(
        viz_path,
        "visualization program",
    )
    overlay_path = require_file(
        overlay_path,
        "visualization overlay",
    )

    out_json_path = Path(out_json_path)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "clingo",
        str(model_path),
        str(viz_path),
        str(overlay_path),
        "--outf=2",
        "--models=1",
    ]

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode not in CLINGO_SUCCESS_CODES:
        raise RuntimeError(
            f"clingo failed with return code {result.returncode}\n\n"
            f"Command:\n{' '.join(command)}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    validate_single_witness(result.stdout)

    out_json_path.write_text(
        result.stdout,
        encoding="utf-8",
    )


def render_with_clingraph(
    clingo_json_path: str | Path,
    out_dir: str | Path,
    output_format: str = "png",
    engine: str = "neato",
) -> None:
    clingo_json_path = require_file(
        clingo_json_path,
        "Clingo visualization JSON",
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "clingraph",
        str(clingo_json_path),
        "--out",
        "render",
        "--dir",
        str(out_dir),
        "--format",
        output_format,
        "--engine",
        engine,
    ]

    run_command(command)


def render_graph(
    model_path: str | Path,
    viz_path: str | Path,
    overlay_path: str | Path,
    out_dir: str | Path,
    output_format: str = "png",
    engine: str = "neato",
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clingo_json_path = out_dir / "clingo_model.json"

    write_clingo_json_model(
        model_path=model_path,
        viz_path=viz_path,
        overlay_path=overlay_path,
        out_json_path=clingo_json_path,
    )

    render_with_clingraph(
        clingo_json_path=clingo_json_path,
        out_dir=out_dir,
        output_format=output_format,
        engine=engine,
    )

    return clingo_json_path