from __future__ import annotations

import argparse

from lookingglass_tools.lws_generator import (
    DEFAULT_NUM_CAMERA_CHANNELS,
    DEFAULT_NUM_VIEWS,
    generate_lws_files,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Looking Glass Portrait LightWave scene files."
    )
    parser.add_argument("source_lws", help="Path to the master .lws file")
    parser.add_argument("output_dir", help="Folder where CAMERA_00.lws ... CAMERA_47.lws will be written")
    parser.add_argument(
        "--views",
        type=int,
        default=DEFAULT_NUM_VIEWS,
        help=f"Number of view files to create (default: {DEFAULT_NUM_VIEWS})",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_NUM_CAMERA_CHANNELS,
        help=f"Number of camera motion channels to collapse (default: {DEFAULT_NUM_CAMERA_CHANNELS})",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = generate_lws_files(
        source_path=args.source_lws,
        output_dir=args.output_dir,
        num_channels=args.channels,
        num_views=args.views,
        progress_callback=print,
    )
    print(f"Created {len(result.output_paths)} scene files in {result.output_dir}")


if __name__ == "__main__":
    main()
