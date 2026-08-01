#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_DIR = SCRIPT_DIR
TIMEOUT_SECONDS = 900


def tool_path(name):
    return SCRIPT_DIR / name


def helper_path(name):
    return HELPER_DIR / name


def work_path(name):
    return WORK_DIR / name


def fail(message, exit_code=1):
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def existing_file(path, description):
    path = Path(path)
    if not path.is_file():
        fail(f"{description} not found: {path}")
    return path


def strip_inline_comment(line):
    return line.split("%", 1)[0].strip()


def predicate_matches(atom, predicates):
    return any(atom.startswith(pred + "(") for pred in predicates)


def filter_guess_file(source_file, target_file, omitpreds, include_aux=False):
    source_file = existing_file(source_file, "helper file")
    picked_lines = []

    with source_file.open("r") as src:
        for line in src:
            for pred in omitpreds:
                if f"omitted({pred}(" in line or (include_aux and f"omitted(aux{pred}(" in line):
                    picked_lines.append(line)
                    break

    if picked_lines:
        target_file.write_text("".join(picked_lines))
        return True

    return False


def prepare_picked_files(omit_type, omitpreds):
    picked_grounding = work_path("guess_picked_atoms_to_omit_forgrounding.lp")
    picked_guess = work_path("guess_picked_atoms_to_omit.lp")

    if not omitpreds:
        picked_grounding.write_text("")
        picked_guess.write_text("")
        return picked_grounding, picked_guess

    grounding_source = helper_path("guess_atoms_to_omit_forgrounding.lp")
    guess_source = helper_path("guess_atoms_to_omit.lp")

    grounding_matched = filter_guess_file(
        grounding_source,
        picked_grounding,
        omitpreds,
        include_aux=True,
    )
    if not grounding_matched:
        if omit_type == "3":
            shutil.copyfile(grounding_source, picked_grounding)
        else:
            picked_grounding.write_text("")

    guess_matched = filter_guess_file(
        guess_source,
        picked_guess,
        omitpreds,
        include_aux=False,
    )
    if not guess_matched:
        if omit_type == "3":
            shutil.copyfile(guess_source, picked_guess)
        else:
            picked_guess.write_text("")

    return picked_grounding, picked_guess


def rewrite_graph_facts(input_file, omitpreds):
    rewritten = []
    omit_for_grounding = []
    omit_guess = []

    with input_file.open("r") as graph_input:
        for line_number, raw_line in enumerate(graph_input, start=1):
            line = strip_inline_comment(raw_line)

            if not line:
                rewritten.append("\n")
                continue

            if ":-" not in line:
                if "." not in line:
                    fail(f"expected fact ending with '.' at {input_file}:{line_number}: {raw_line.rstrip()}")

                atom = line[:line.index(".")].strip()
                rewritten.append(f"{atom} :- not omitted({atom}).\n")

                if not omitpreds or predicate_matches(atom, omitpreds):
                    omit_for_grounding.append(f"{{omitted({atom})}}.\n")
                    omit_guess.append(f"{{guessedomitted({atom})}}.\n")
            else:
                match = re.search(r"not\s+([^\s.]+(?:\([^)]*\))?)\s*\.", line)
                if not match:
                    fail(f"unsupported constraint format at {input_file}:{line_number}: {raw_line.rstrip()}")

                atom = match.group(1)
                rewritten.append(f"f :- not f, not {atom}, not omitted({atom}).\n")

    return "".join(rewritten), "".join(omit_for_grounding), "".join(omit_guess)


def build_show_text(omit_type, omitpreds):
    if not omitpreds:
        return "#show notomitted/1.\n"

    if omitpreds == ["arg", "att"] and omit_type == "3":
        return "#show notomitted/1.\n"

    lines = []
    for pred in omitpreds:
        if pred in {"att", "link"}:
            lines.append(
                f"#show notomitted(atom({pred}(X,Y))) : notomitted(atom({pred}(X,Y))).\n"
            )
        else:
            lines.append(
                f"#show notomitted(atom({pred}(X))) : notomitted(atom({pred}(X))).\n"
            )
    return "".join(lines)


def run_reification(graph_input_modified, omit_for_grounding, encoding, picked_grounding, output_file):
    gringo_reify = existing_file(tool_path("gringo-3.0.3-x86-linux/gringo"), "gringo 3 reify binary")

    first_cmd = [
        "gringo",
        "--text",
        str(graph_input_modified),
        str(omit_for_grounding),
        str(encoding),
        str(picked_grounding),
    ]
    second_cmd = [str(gringo_reify), "--reify"]

    print(" ".join(first_cmd) + " | " + " ".join(second_cmd) + f" > {output_file}")
    print("========")

    with output_file.open("wb") as out:
        first = subprocess.Popen(first_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second = subprocess.Popen(second_cmd, stdin=first.stdout, stdout=out, stderr=subprocess.PIPE)

        if first.stdout is not None:
            first.stdout.close()

        _, first_stderr = first.communicate()
        _, second_stderr = second.communicate()

    if first.returncode != 0:
        fail("gringo --text failed:\n" + first_stderr.decode("utf-8", errors="replace"))

    if second.returncode != 0:
        fail("gringo --reify failed:\n" + second_stderr.decode("utf-8", errors="replace"))


def remove_unsupported_reify_lines(input_file, output_file):
    with input_file.open("r") as src, output_file.open("w") as dst:
        for line in src:
            if "wlist" not in line and "sum" not in line:
                dst.write(line)


def run_clingo(omit_type, picked_guess, omit_guess, reify_modified, show_atoms):
    helper_files = [
        tool_path("aux_meta_omitted.lp"),
        tool_path("metaD.lp"),
        tool_path("optimization.lp"),
    ]
    for helper in helper_files:
        existing_file(helper, "helper file")

    cmd = ["clingo", str(picked_guess)]

    if omit_type == "3":
        cmd.append(str(existing_file(helper_path("infer_omitted_atoms.lp"), "helper file")))

    cmd.extend([
        str(omit_guess),
        str(reify_modified),
        str(show_atoms),
        *(str(path) for path in helper_files),
    ])

    print(" ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        Path(work_path("raw_final_clingo_output.txt")).write_text(partial)
        fail(f"clingo timed out after {TIMEOUT_SECONDS} seconds")

    if result.returncode not in (0, 10, 20, 30):
        fail(
            f"clingo failed with code {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    return result.stdout


def parse_final_model(clingo_output):
    if "UNSATISFIABLE" in clingo_output:
        fail("clingo returned UNSATISFIABLE; omission_result.lp was not written")

    lines = clingo_output.splitlines()
    models = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("Answer:"):
            i += 1
            model_parts = []

            while i < len(lines):
                current = lines[i].strip()

                if (
                    current.startswith("Answer:")
                    or current.startswith("Optimization:")
                    or current.startswith("OPTIMUM FOUND")
                    or current.startswith("Models")
                    or current.startswith("Calls")
                    or current.startswith("Time")
                    or current.startswith("CPU Time")
                    or current.startswith("SATISFIABLE")
                    or current.startswith("UNSATISFIABLE")
                ):
                    break

                if current:
                    model_parts.append(current)

                i += 1

            models.append(" ".join(model_parts))
            continue

        i += 1

    if not models:
        fail("no Answer block found in clingo output")

    return models[-1]


def write_omission_result(clingo_output, output_file):
    final_model = parse_final_model(clingo_output)

    omitted_atoms = []

    for token in final_model.split():
        if token.startswith("omitted(atom(") and token.endswith("))"):
            atom = token[len("omitted(atom("):-2]
            omitted_atoms.append(atom)

    omitted_atoms = sorted(set(omitted_atoms))

    with output_file.open("w") as out:
        for atom in omitted_atoms:
            out.write(f"output_omitted(atom({atom})).\n")
        out.write("\n")
        out.write("omitted(X):- output_omitted(atom(X)).\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute maximum omission for node/link graph instances."
    )
    parser.add_argument("graph_facts", help="file containing graph facts")
    parser.add_argument("encoding", help="domain encoding extended with omitted atoms")
    parser.add_argument("omission_type", choices=["2", "3"], help="2: selected predicates, 3: selected predicates with omission dependency")
    parser.add_argument("omit_pred", nargs="?", default="", help="comma-separated predicates to omit, e.g. node,link")
    parser.add_argument(
    "--helper-dir",
    default=None,
    help="directory containing omission helper files",)
    parser.add_argument(
    "--out-dir",
    default=".",
    help="directory where generated files are written",)
    return parser.parse_args()


def main():
    args = parse_args()
    
    global WORK_DIR
    WORK_DIR = Path(args.out_dir).resolve()
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    global HELPER_DIR

    if args.helper_dir is not None:
        HELPER_DIR = Path(args.helper_dir).resolve()

    input_file = existing_file(args.graph_facts, "graph facts file")
    encoding = existing_file(args.encoding, "encoding file")
    omit_type = args.omission_type
    omitpreds = [pred.strip() for pred in args.omit_pred.split(",") if pred.strip()]

    auxiliary_dir = work_path("auxiliaryFiles")
    auxiliary_dir.mkdir(exist_ok=True)

    picked_grounding, picked_guess = prepare_picked_files(omit_type, omitpreds)

    rewritten, omit_for_grounding_text, omit_guess_text = rewrite_graph_facts(input_file, omitpreds)

    input_base = input_file.stem
    graph_input_modified = auxiliary_dir / f"{input_base}_omission.lp"
    omit_for_grounding = auxiliary_dir / f"{input_base}_guess_to_omit_for_grounding.lp"
    omit_guess = auxiliary_dir / f"{input_base}_guess_to_omit.lp"
    show_atoms = auxiliary_dir / f"{input_base}_show_atoms.lp"
    graph_reify = auxiliary_dir / f"{input_base}_omission_reify.lp"
    graph_reify_modified = auxiliary_dir / f"{input_base}_omission_reify_modified.lp"

    graph_input_modified.write_text(rewritten)
    omit_for_grounding.write_text(omit_for_grounding_text)
    omit_guess.write_text(omit_guess_text)
    show_atoms.write_text(build_show_text(omit_type, omitpreds))

    run_reification(graph_input_modified, omit_for_grounding, encoding, picked_grounding, graph_reify)
    remove_unsupported_reify_lines(graph_reify, graph_reify_modified)

    clingo_output = run_clingo(omit_type, picked_guess, omit_guess, graph_reify_modified, show_atoms)
    work_path("raw_final_clingo_output.txt").write_text(clingo_output)

    output_file = work_path("omission_result.lp")
    write_omission_result(clingo_output, output_file)
    print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()
