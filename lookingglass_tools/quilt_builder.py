from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, Dict, List, Mapping, Sequence

from PIL import Image

ProgressCallback = Callable[[str], None]
RENDER_FILENAME_PATTERN = re.compile(
    r"^(?P<prefix>.+)_(?P<scene>\d+)_(?P<frame>\d+)\.(?P<extension>jpe?g|png)$",
    re.IGNORECASE,
)


class QuiltBuilderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderSequence:
    prefix: str
    images_by_frame: Mapping[int, Mapping[int, Path]]
    scene_digits: int
    frame_digits: int
    extensions: Sequence[str]


@dataclass(frozen=True)
class QuiltBuildResult:
    output_dir: Path
    output_paths: Sequence[Path]
    skipped_frames: Sequence[int]
    sequence_prefix: str


@dataclass(frozen=True)
class SequenceValidation:
    expected_frames: Sequence[int]
    missing_frames: Sequence[int]
    missing_scenes_by_frame: Mapping[int, Sequence[int]]
    extra_scenes_by_frame: Mapping[int, Sequence[int]]

    @property
    def has_issues(self) -> bool:
        return bool(
            self.missing_frames or self.missing_scenes_by_frame or self.extra_scenes_by_frame
        )


def scan_render_sequences(images_dir: Path | str) -> Dict[str, RenderSequence]:
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        raise QuiltBuilderError(f"Images folder does not exist: {images_dir}")

    grouped_images: Dict[str, Dict[int, Dict[int, Path]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    scene_digits: Dict[str, int] = defaultdict(int)
    frame_digits: Dict[str, int] = defaultdict(int)
    extensions: Dict[str, set[str]] = defaultdict(set)

    for child in sorted(images_dir.iterdir()):
        if not child.is_file():
            continue

        match = RENDER_FILENAME_PATTERN.match(child.name)
        if match is None:
            continue

        prefix = match.group("prefix")
        scene_text = match.group("scene")
        frame_text = match.group("frame")
        scene = int(scene_text)
        frame = int(frame_text)

        if scene in grouped_images[prefix][frame]:
            raise QuiltBuilderError(
                f"Duplicate render found for prefix '{prefix}', frame {frame}, scene {scene}."
            )

        grouped_images[prefix][frame][scene] = child
        scene_digits[prefix] = max(scene_digits[prefix], len(scene_text))
        frame_digits[prefix] = max(frame_digits[prefix], len(frame_text))
        extensions[prefix].add(match.group("extension").lower())

    if not grouped_images:
        raise QuiltBuilderError(
            "No rendered images were found. Expected names like arbitrary_name_00_000.jpeg."
        )

    sequences: Dict[str, RenderSequence] = {}
    for prefix, frames in grouped_images.items():
        sequences[prefix] = RenderSequence(
            prefix=prefix,
            images_by_frame={frame: dict(scenes) for frame, scenes in frames.items()},
            scene_digits=scene_digits[prefix],
            frame_digits=frame_digits[prefix],
            extensions=sorted(extensions[prefix]),
        )

    return dict(sorted(sequences.items()))


def _format_float(value: float) -> str:
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _format_number_list(values: Sequence[int], digits: int) -> str:
    return ", ".join(str(value).zfill(digits) for value in values)


def _describe_frame_issue(
    frame: int,
    missing: Sequence[int],
    extra: Sequence[int],
    scene_digits: int,
    frame_digits: int,
) -> str:
    issues: List[str] = []
    if missing:
        issues.append(f"missing scenes {_format_number_list(missing, scene_digits)}")
    if extra:
        issues.append(f"unexpected scenes {_format_number_list(extra, scene_digits)}")
    return f"Frame {str(frame).zfill(frame_digits)}: {'; '.join(issues)}"


def validate_render_sequence(
    sequence: RenderSequence,
    expected_views: int,
) -> SequenceValidation:
    frame_numbers = sorted(sequence.images_by_frame)
    if not frame_numbers:
        return SequenceValidation([], [], {}, {})

    expected_frames = list(range(min(frame_numbers), max(frame_numbers) + 1))
    missing_frames = [
        frame for frame in expected_frames if frame not in sequence.images_by_frame
    ]

    expected_scenes = set(range(expected_views))
    missing_scenes_by_frame: Dict[int, Sequence[int]] = {}
    extra_scenes_by_frame: Dict[int, Sequence[int]] = {}

    for frame in frame_numbers:
        scenes = set(sequence.images_by_frame[frame])
        missing_scenes = sorted(expected_scenes - scenes)
        extra_scenes = sorted(scenes - expected_scenes)
        if missing_scenes:
            missing_scenes_by_frame[frame] = missing_scenes
        if extra_scenes:
            extra_scenes_by_frame[frame] = extra_scenes

    return SequenceValidation(
        expected_frames=expected_frames,
        missing_frames=missing_frames,
        missing_scenes_by_frame=missing_scenes_by_frame,
        extra_scenes_by_frame=extra_scenes_by_frame,
    )


def describe_validation_issues(
    sequence: RenderSequence,
    validation: SequenceValidation,
    limit: int = 12,
) -> str:
    lines: List[str] = []
    scene_digits = max(2, sequence.scene_digits)
    frame_digits = max(1, sequence.frame_digits)

    if validation.missing_frames:
        lines.append(
            "Missing frame numbers: "
            + _format_number_list(validation.missing_frames, frame_digits)
        )

    for frame in sorted(validation.missing_scenes_by_frame):
        lines.append(
            _describe_frame_issue(
                frame,
                validation.missing_scenes_by_frame[frame],
                validation.extra_scenes_by_frame.get(frame, []),
                scene_digits,
                frame_digits,
            )
        )

    for frame in sorted(validation.extra_scenes_by_frame):
        if frame in validation.missing_scenes_by_frame:
            continue
        lines.append(
            _describe_frame_issue(
                frame,
                [],
                validation.extra_scenes_by_frame[frame],
                scene_digits,
                frame_digits,
            )
        )

    if not lines:
        return "No missing scenes or frames detected."
    if len(lines) > limit:
        return "\n".join(lines[:limit] + ["..."])
    return "\n".join(lines)


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
    validation = validate_render_sequence(sequence, expected_views)
    complete_frames: List[int] = []
    skipped_frames: List[int] = []

    for frame in validation.expected_frames:
        if frame in validation.missing_frames:
            skipped_frames.append(frame)
            continue
        if frame in validation.missing_scenes_by_frame or frame in validation.extra_scenes_by_frame:
            skipped_frames.append(frame)
            continue
        complete_frames.append(frame)

    if validation.has_issues and not skip_incomplete:
        raise QuiltBuilderError(
            "The render folder is missing required scenes or frames.\n"
            + describe_validation_issues(sequence, validation)
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
