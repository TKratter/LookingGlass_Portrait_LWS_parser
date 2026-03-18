from __future__ import annotations

import argparse

from lookingglass_tools.quilt_builder import build_quilts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Looking Glass Portrait quilts from rendered camera images."
    )
    parser.add_argument("images_dir", help="Folder containing files like PREFIX_CAMERA00_000.jpg")
    parser.add_argument("output_dir", help="Folder where quilt images will be written")
    parser.add_argument(
        "--sequence-prefix",
        help="Sequence prefix to use when the folder contains multiple render sets",
    )
    parser.add_argument(
        "--output-name",
        help="Base name for the generated quilt files. Defaults to the detected sequence prefix.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=6,
        help="Number of rows in the quilt (default: 6)",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=8,
        help="Number of columns in the quilt (default: 8)",
    )
    parser.add_argument(
        "--aspect",
        type=float,
        default=0.75,
        help="Quilt aspect value used in the output filename (default: 0.75)",
    )
    parser.add_argument(
        "--format",
        default="jpg",
        choices=("jpg", "png"),
        help="Output image format (default: jpg)",
    )
    parser.add_argument(
        "--skip-incomplete",
        action="store_true",
        help="Skip incomplete frame sets instead of failing",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = build_quilts(
        images_dir=args.images_dir,
        output_dir=args.output_dir,
        sequence_prefix=args.sequence_prefix,
        output_name=args.output_name,
        rows=args.rows,
        columns=args.columns,
        aspect=args.aspect,
        output_format=args.format,
        skip_incomplete=args.skip_incomplete,
        progress_callback=print,
    )

    print(f"Created {len(result.output_paths)} quilt files in {result.output_dir}")
    if result.skipped_frames:
        print(f"Skipped {len(result.skipped_frames)} incomplete frame sets.")


if __name__ == "__main__":
    main()
