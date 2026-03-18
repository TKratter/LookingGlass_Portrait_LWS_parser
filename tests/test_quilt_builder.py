from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from PIL import Image

from lookingglass_tools.quilt_builder import QuiltBuilderError, build_quilts, scan_render_sequences


def camera_color(camera: int) -> tuple[int, int, int]:
    return ((camera * 5) % 256, (camera * 3) % 256, (camera * 7) % 256)


class QuiltBuilderTests(unittest.TestCase):
    def test_build_quilts_creates_bottom_to_top_portrait_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "renders"
            output_dir = Path(temp_dir) / "quilts"
            input_dir.mkdir()

            for frame in range(2):
                for camera in range(48):
                    image = Image.new("RGB", (2, 2), camera_color(camera))
                    image.save(input_dir / f"Matrix_CAMERA{camera:02d}_{frame:03d}.png")

            sequences = scan_render_sequences(input_dir)
            self.assertEqual(["Matrix"], list(sequences))

            result = build_quilts(
                images_dir=input_dir,
                output_dir=output_dir,
                sequence_prefix="Matrix",
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

            for camera in range(47):
                image = Image.new("RGB", (2, 2), camera_color(camera))
                image.save(input_dir / f"Matrix_CAMERA{camera:02d}_000.png")

            with self.assertRaises(QuiltBuilderError):
                build_quilts(
                    images_dir=input_dir,
                    output_dir=output_dir,
                    sequence_prefix="Matrix",
                    output_format="png",
                )


if __name__ == "__main__":
    unittest.main()
