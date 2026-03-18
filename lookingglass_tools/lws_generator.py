from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, List, Sequence

DEFAULT_NUM_CAMERA_CHANNELS = 6
DEFAULT_NUM_VIEWS = 48
ProgressCallback = Callable[[str], None]


class LwsGeneratorError(ValueError):
    pass


@dataclass(frozen=True)
class Envelope:
    start_index: int
    end_index: int
    header_line: str
    key_count_line: str
    keys: Sequence[str]
    behaviors_line: str

    @classmethod
    def from_lines(
        cls,
        lines: Sequence[str],
        start_index: int,
        end_index: int,
    ) -> "Envelope":
        envelope_lines = list(lines[start_index:end_index])
        if len(envelope_lines) < 4:
            raise LwsGeneratorError(
                f"Envelope starting at line {start_index + 1} is too short to parse."
            )

        try:
            key_count = int(envelope_lines[1].strip())
        except ValueError as exc:
            raise LwsGeneratorError(
                f"Could not parse envelope key count at line {start_index + 2}."
            ) from exc

        behaviors_index = 2 + key_count
        if behaviors_index >= len(envelope_lines):
            raise LwsGeneratorError(
                f"Envelope starting at line {start_index + 1} does not contain enough key lines."
            )

        return cls(
            start_index=start_index,
            end_index=end_index,
            header_line=envelope_lines[0],
            key_count_line=envelope_lines[1],
            keys=envelope_lines[2:behaviors_index],
            behaviors_line=envelope_lines[behaviors_index],
        )

    def lines_for_key(self, key_index: int) -> List[str]:
        if key_index < 0 or key_index >= len(self.keys):
            raise LwsGeneratorError(
                f"Envelope only has {len(self.keys)} keys, requested key {key_index}."
            )

        return [
            self.header_line,
            _replace_numeric_value(self.key_count_line, "1"),
            self.keys[key_index],
            self.behaviors_line,
        ]


@dataclass(frozen=True)
class SceneGenerationResult:
    output_dir: Path
    output_paths: Sequence[Path]


def _replace_numeric_value(line: str, replacement: str) -> str:
    newline = "\r\n" if line.endswith("\r\n") else "\n"
    stripped = line.rstrip("\r\n")
    leading_whitespace = stripped[: len(stripped) - len(stripped.lstrip())]
    return f"{leading_whitespace}{replacement}{newline}"


def _find_line_with_substring(
    lines: Sequence[str],
    substring: str,
    start_index: int = 0,
) -> int:
    for index in range(start_index, len(lines)):
        if substring in lines[index]:
            return index
    raise LwsGeneratorError(f"Could not find '{substring}' in the scene file.")


def _find_envelope_end_index(lines: Sequence[str], start_index: int) -> int:
    for index in range(start_index, len(lines)):
        if "}" in lines[index]:
            return index
    raise LwsGeneratorError(
        f"Could not find the end of the envelope that starts at line {start_index + 1}."
    )


def _extract_envelopes(lines: Sequence[str], num_channels: int) -> List[Envelope]:
    camera_name_index = _find_line_with_substring(lines, "CameraName")
    camera_motion_index = _find_line_with_substring(lines, "CameraMotion", camera_name_index)

    envelopes: List[Envelope] = []
    search_index = camera_motion_index
    for channel_index in range(num_channels):
        channel_line_index = _find_line_with_substring(
            lines,
            f"Channel {channel_index}",
            search_index,
        )
        envelope_start_index = _find_line_with_substring(
            lines,
            "{ Envelope",
            channel_line_index,
        )
        envelope_end_index = _find_envelope_end_index(lines, envelope_start_index)
        envelopes.append(
            Envelope.from_lines(lines, envelope_start_index, envelope_end_index)
        )
        search_index = envelope_end_index

    shift_camera_index = _find_line_with_substring(lines, "ShiftCamera")
    shift_envelope_start = _find_line_with_substring(lines, "{ Envelope", shift_camera_index)
    shift_envelope_end = _find_envelope_end_index(lines, shift_envelope_start)
    envelopes.append(Envelope.from_lines(lines, shift_envelope_start, shift_envelope_end))

    return envelopes


def _update_rgb_prefix(lines: Sequence[str], view_index: int) -> List[str]:
    updated_lines = list(lines)
    rgb_prefix_index = _find_line_with_substring(updated_lines, "SaveRGBImagesPrefix")
    line = updated_lines[rgb_prefix_index]
    newline = "\r\n" if line.endswith("\r\n") else "\n"
    stripped = line.rstrip("\r\n")
    prefix_key, separator, prefix_value = stripped.partition(" ")
    if not separator:
        raise LwsGeneratorError("SaveRGBImagesPrefix line is malformed.")

    cleaned_prefix = re.sub(r"_CAMERA\d+_$", "", prefix_value)
    updated_lines[rgb_prefix_index] = (
        f"{prefix_key} {cleaned_prefix}_CAMERA{view_index:02d}_{newline}"
    )
    return updated_lines


def create_scene_lines_for_view(
    lines: Sequence[str],
    envelopes: Sequence[Envelope],
    view_index: int,
) -> List[str]:
    new_lines: List[str] = []
    start_line = 0

    for envelope in envelopes:
        new_lines.extend(lines[start_line:envelope.start_index])
        new_lines.extend(envelope.lines_for_key(view_index))
        start_line = envelope.end_index

    new_lines.extend(lines[start_line:])
    return _update_rgb_prefix(new_lines, view_index)


def generate_lws_files(
    source_path: Path | str,
    output_dir: Path | str,
    num_channels: int = DEFAULT_NUM_CAMERA_CHANNELS,
    num_views: int = DEFAULT_NUM_VIEWS,
    progress_callback: ProgressCallback | None = None,
) -> SceneGenerationResult:
    source_path = Path(source_path)
    output_dir = Path(output_dir)

    if not source_path.is_file():
        raise LwsGeneratorError(f"Scene file does not exist: {source_path}")
    if num_channels <= 0:
        raise LwsGeneratorError("Number of camera channels must be greater than zero.")
    if num_views <= 0:
        raise LwsGeneratorError("Number of views must be greater than zero.")

    with source_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        lines = handle.readlines()
    envelopes = _extract_envelopes(lines, num_channels)

    for envelope in envelopes:
        if len(envelope.keys) < num_views:
            raise LwsGeneratorError(
                "The scene does not contain enough animation keys for "
                f"{num_views} views. Found {len(envelope.keys)}."
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: List[Path] = []

    for view_index in range(num_views):
        scene_lines = create_scene_lines_for_view(lines, envelopes, view_index)
        output_path = output_dir / f"CAMERA_{view_index:02d}.lws"
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("".join(scene_lines))
        output_paths.append(output_path)
        if progress_callback is not None:
            progress_callback(f"Created {output_path.name}")

    return SceneGenerationResult(output_dir=output_dir, output_paths=output_paths)
