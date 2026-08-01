import argparse

from .overlay import write_overlay
from .solve import write_violations
from .transform import write_meta_json, write_transform_outputs
from .render import render_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="unsat-viz-tool",
        description="Explain ASP unsatisfiability via visualization.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    meta_parser = subparsers.add_parser("meta")
    meta_parser.add_argument("--input", required=True)
    meta_parser.add_argument("--out", required=True)

    transform_parser = subparsers.add_parser("transform")
    transform_parser.add_argument("--encoding", required=True)
    transform_parser.add_argument("--out-dir", required=True)

    solve_parser = subparsers.add_parser("solve")
    solve_parser.add_argument("--instance", required=True)
    solve_parser.add_argument("--omission", required=True)
    solve_parser.add_argument("--cleaned-encoding", required=True)
    solve_parser.add_argument("--relaxed", required=True)
    solve_parser.add_argument("--out-dir", required=True)
    solve_parser.add_argument("--mode", default="one")
    solve_parser.add_argument("--max-models", type=int, default=200)

    overlay_parser = subparsers.add_parser("overlay")
    overlay_parser.add_argument("--meta", required=True)
    overlay_parser.add_argument("--violations", required=True)
    overlay_parser.add_argument("--out", required=True)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--instance", required=True)
    render_parser.add_argument("--omission", required=True)
    render_parser.add_argument("--cleaned-encoding", required=True)
    render_parser.add_argument("--viz", required=True)
    render_parser.add_argument("--overlay", required=True)
    render_parser.add_argument("--out-dir", required=True)
    render_parser.add_argument("--format", default="png")

    args = parser.parse_args()

    if args.command == "meta":
        metas = write_meta_json(args.input, args.out)
        print(f"Wrote {len(metas)} rule metadata entries to {args.out}")

    elif args.command == "transform":
        result = write_transform_outputs(
            encoding_path=args.encoding,
            out_dir=args.out_dir,
        )
        print(f"Wrote {len(result.meta)} transformed rule(s) to {args.out_dir}")

    elif args.command == "solve":
        violations = write_violations(
            instance_path=args.instance,
            omission_path=args.omission,
            cleaned_encoding_path=args.cleaned_encoding,
            relaxed_path=args.relaxed,
            out_dir=args.out_dir,
            mode=args.mode,
            max_models=args.max_models,
        )
        print(f"Wrote {len(violations)} violation(s) to {args.out_dir}")

    elif args.command == "overlay":
        write_overlay(
            meta_path=args.meta,
            violations_path=args.violations,
            out_path=args.out,
        )
        print(f"Wrote overlay to {args.out}")

    elif args.command == "render":
        render_graph(
            instance_path=args.instance,
            omission_path=args.omission,
            cleaned_encoding_path=args.cleaned_encoding,
            viz_path=args.viz,
            overlay_path=args.overlay,
            out_dir=args.out_dir,
            output_format=args.format,
        )
        print(f"Rendered graph to {args.out_dir}")

if __name__ == "__main__":
    main()