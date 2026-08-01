import subprocess
from pathlib import Path


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


def write_clingo_json_model(
    instance_path: str | Path,
    omission_path: str | Path,
    cleaned_encoding_path: str | Path,
    viz_path: str | Path,
    overlay_path: str | Path,
    out_json_path: str | Path,
) -> None:
    out_json_path = Path(out_json_path)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "clingo",
        str(instance_path),
        str(omission_path),
        str(cleaned_encoding_path),
        str(viz_path),
        str(overlay_path),
        "--outf=2",
    ]

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode not in {10, 30}:
        raise RuntimeError(
            f"clingo failed with return code {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    out_json_path.write_text(result.stdout, encoding="utf-8")

def render_with_clingraph(
    clingo_json_path: str | Path,
    out_dir: str | Path,
    output_format: str = "png",
) -> None:
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
        "neato",
    ]

    run_command(command)


def render_graph(
    instance_path: str | Path,
    omission_path: str | Path,
    cleaned_encoding_path: str | Path,
    viz_path: str | Path,
    overlay_path: str | Path,
    out_dir: str | Path,
    output_format: str = "png",
) -> Path:
    out_dir = Path(out_dir)
    clingo_json_path = out_dir / "clingo_model.json"

    write_clingo_json_model(
        instance_path=instance_path,
        omission_path=omission_path,
        cleaned_encoding_path=cleaned_encoding_path,
        viz_path=viz_path,
        overlay_path=overlay_path,
        out_json_path=clingo_json_path,
    )

    render_with_clingraph(
        clingo_json_path=clingo_json_path,
        out_dir=out_dir,
        output_format=output_format,
    )

    return clingo_json_path