from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from PIL import Image

from lookingglass_tools.quilt_builder import (
    QuiltBuilderError,
    build_quilts,
    describe_validation_issues,
    scan_render_sequences,
    validate_render_sequence,
)


def camera_color(camera: int) -> tuple[int, int, int]:
    return ((camera * 5) % 256, (camera * 3) % 256, (camera * 7) % 256)


class QuiltBuilderTests(unittest.TestCase):
    def test_build_quilts_creates_bottom_to_top_portrait_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "renders"
            output_dir = Path(temp_dir) / "quilts"
            input_dir.mkdir()

            for frame in range(2):
                for scene in range(48):
                    image = Image.new("RGB", (2, 2), camera_color(scene))
                    image.save(input_dir / f"My_Matrix_{scene:02d}_{frame:03d}.png")

            sequences = scan_render_sequences(input_dir)
            self.assertEqual(["My_Matrix"], list(sequences))

            result = build_quilts(
                images_dir=input_dir,
                output_dir=output_dir,
                sequence_prefix="My_Matrix",
                output_format="png",
            )

            self.assertEqual(2, len(result.output_paths))
            with Image.open(result.output_paths[0]) as quilt:
                self.assertEqual((16, 12), quilt.size)
                self.assertEqual(camera_color(40), quilt.getpixel((0, 0)))
                self.assertEqual(camera_color(47), quilt.getpixel((15, 0)))
                self.assertEqual(camera_color(0), quilt.getpixel((0, 11)))
                self.assertEqual(camera_color(7), quilt.getpixel((15, 11)))

    def test_build_quilts_fails_on_incomplete_frame_sets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "renders"
            output_dir = Path(temp_dir) / "quilts"
            input_dir.mkdir()

            for scene in range(47):
                image = Image.new("RGB", (2, 2), camera_color(scene))
                image.save(input_dir / f"H120_{scene:02d}_000.jpeg")

            with self.assertRaises(QuiltBuilderError):
                build_quilts(
                    images_dir=input_dir,
                    output_dir=output_dir,
                    sequence_prefix="H120",
                    output_format="png",
                )

    def test_validation_reports_missing_frames_and_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "renders"
            input_dir.mkdir()

            for scene in range(48):
                if scene == 7:
                    continue
                image = Image.new("RGB", (2, 2), camera_color(scene))
                image.save(input_dir / f"H120_{scene:02d}_000.jpeg")

            for scene in range(48):
                image = Image.new("RGB", (2, 2), camera_color(scene))
                image.save(input_dir / f"H120_{scene:02d}_002.jpeg")

            sequence = scan_render_sequences(input_dir)["H120"]
            validation = validate_render_sequence(sequence, expected_views=48)
            report = describe_validation_issues(sequence, validation)

            self.assertIn("Missing frame numbers: 001", report)
            self.assertIn("Frame 000: missing scenes 07", report)


if __name__ == "__main__":
    unittest.main()
