from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, Dict, List, Mapping, Sequence

from PIL import Image

ProgressCallback = Callable[[str], None]
RENDER_FILENAME_PATTERN = re.compile(
    r"^(?P<prefix>.+?)_CAMERA(?P<camera>\d+)_(?P<frame>\d+)\.(?P<extension>[^.]+)$",
    re.IGNORECASE,
)


class QuiltBuilderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderSequence:
    prefix: str
    images_by_frame: Mapping[int, Mapping[int, Path]]
    camera_digits: int
    frame_digits: int
    extensions: Sequence[str]


@dataclass(frozen=True)
class QuiltBuildResult:
    output_dir: Path
    output_paths: Sequence[Path]
    skipped_frames: Sequence[int]
    sequence_prefix: str


def scan_render_sequences(images_dir: Path | str) -> Dict[str, RenderSequence]:
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        raise QuiltBuilderError(f"Images folder does not exist: {images_dir}")

    grouped_images: Dict[str, Dict[int, Dict[int, Path]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    camera_digits: Dict[str, int] = defaultdict(int)
    frame_digits: Dict[str, int] = defaultdict(int)
    extensions: Dict[str, set[str]] = defaultdict(set)

    for child in sorted(images_dir.iterdir()):
        if not child.is_file():
            continue

        match = RENDER_FILENAME_PATTERN.match(child.name)
        if match is None:
            continue

        prefix = match.group("prefix")
        camera_text = match.group("camera")
        frame_text = match.group("frame")
        camera = int(camera_text)
        frame = int(frame_text)

        if camera in grouped_images[prefix][frame]:
            raise QuiltBuilderError(
                f"Duplicate render found for prefix '{prefix}', frame {frame}, camera {camera}."
            )

        grouped_images[prefix][frame][camera] = child
        camera_digits[prefix] = max(camera_digits[prefix], len(camera_text))
        frame_digits[prefix] = max(frame_digits[prefix], len(frame_text))
        extensions[prefix].add(match.group("extension").lower())

    if not grouped_images:
        raise QuiltBuilderError(
            "No rendered images were found. Expected names like PREFIX_CAMERA00_000.jpg."
        )

    sequences: Dict[str, RenderSequence] = {}
    for prefix, frames in grouped_images.items():
        sequences[prefix] = RenderSequence(
            prefix=prefix,
            images_by_frame={frame: dict(cameras) for frame, cameras in frames.items()},
            camera_digits=camera_digits[prefix],
            frame_digits=frame_digits[prefix],
            extensions=sorted(extensions[prefix]),
        )

    return dict(sorted(sequences.items()))


def _format_float(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _describe_frame_issue(frame: int, missing: Sequence[int], extra: Sequence[int]) -> str:
    issues: List[str] = []
    if missing:
        issues.append(f"missing cameras {', '.join(str(value) for value in missing)}")
    if extra:
        issues.append(f"unexpected cameras {', '.join(str(value) for value in extra)}")
    return f"Frame {frame}: {'; '.join(issues)}"


def build_quilts(
    images_dir: Path | str,
    output_dir: Path | str,
    sequence_prefix: str | None = None,
    output_name: str | None = None,
    rows: int = 6,
    columns: int = 8,
    aspect: float = 0.75,
    output_format: str = "jpg",
    skip_incomplete: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> QuiltBuildResult:
    if rows <= 0 or columns <= 0:
        raise QuiltBuilderError("Rows and columns must both be greater than zero.")

    sequences = scan_render_sequences(images_dir)
    if sequence_prefix is None:
        if len(sequences) != 1:
            available = ", ".join(sequences)
            raise QuiltBuilderError(
                "Multiple render sequences were found. Choose one of: " + available
            )
        sequence = next(iter(sequences.values()))
    else:
        try:
            sequence = sequences[sequence_prefix]
        except KeyError as exc:
            available = ", ".join(sequences)
            raise QuiltBuilderError(
                f"Sequence '{sequence_prefix}' was not found. Available sequences: {available}"
            ) from exc

    expected_views = rows * columns
    expected_cameras = set(range(expected_views))
    complete_frames: List[int] = []
    skipped_frames: List[int] = []
    issues: List[str] = []

    for frame in sorted(sequence.images_by_frame):
        cameras = set(sequence.images_by_frame[frame])
        missing = sorted(expected_cameras - cameras)
        extra = sorted(cameras - expected_cameras)
        if missing or extra:
            skipped_frames.append(frame)
            issues.append(_describe_frame_issue(frame, missing, extra))
        else:
            complete_frames.append(frame)

    if issues and not skip_incomplete:
        sample = "\n".join(issues[:10])
        if len(issues) > 10:
            sample += "\n..."
        raise QuiltBuilderError(
            "The render folder contains incomplete frame sets.\n" + sample
        )

    if not complete_frames:
        raise QuiltBuilderError("No complete frame sets were found to convert into quilts.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_name = output_name or sequence.prefix
    normalized_format = output_format.lower().lstrip(".")
    if normalized_format == "jpeg":
        normalized_format = "jpg"
    if normalized_format not in {"jpg", "png"}:
        raise QuiltBuilderError("Output format must be either 'jpg' or 'png'.")

    first_image_path = sequence.images_by_frame[complete_frames[0]][0]
    with Image.open(first_image_path) as first_image:
        tile_width, tile_height = first_image.size
        canvas_mode = "RGB" if normalized_format == "jpg" else first_image.mode
        if canvas_mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
            canvas_mode = "RGBA" if "A" in first_image.mode else "RGB"

    output_paths: List[Path] = []
    frame_digits = len(str(max(complete_frames)))
    quilt_width = tile_width * columns
    quilt_height = tile_height * rows
    aspect_text = _format_float(aspect)

    for frame in complete_frames:
        canvas = Image.new(canvas_mode, (quilt_width, quilt_height))

        for row in range(rows):
            for column in range(columns):
                camera = (row * columns) + column
                image_path = sequence.images_by_frame[frame][camera]
                with Image.open(image_path) as image:
                    if image.size != (tile_width, tile_height):
                        raise QuiltBuilderError(
                            f"Image size mismatch in {image_path.name}. "
                            f"Expected {(tile_width, tile_height)}, found {image.size}."
                        )
                    rendered_image = image.convert(canvas_mode) if image.mode != canvas_mode else image.copy()

                x_position = column * tile_width
                y_position = (rows - 1 - row) * tile_height
                canvas.paste(rendered_image, (x_position, y_position))

        frame_text = str(frame).zfill(frame_digits)
        output_path = output_dir / (
            f"{output_name}_f{expected_views}_qs{columns}x{rows}"
            f"a{aspect_text}-{quilt_width}x{quilt_height}_{frame_text}.{normalized_format}"
        )

        canvas.save(output_path)
        output_paths.append(output_path)
        if progress_callback is not None:
            progress_callback(f"Created {output_path.name}")

    return QuiltBuildResult(
        output_dir=output_dir,
        output_paths=output_paths,
        skipped_frames=skipped_frames,
        sequence_prefix=sequence.prefix,
    )
