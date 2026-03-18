from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from lookingglass_tools.lws_generator import generate_lws_files


def build_sample_scene() -> str:
    lines = [
        "LWSC\n",
        "5\n",
        "CameraName Camera\n",
        "CameraMotion\n",
        "NumChannels 6\n",
    ]

    for channel in range(6):
        lines.extend(
            [
                f"Channel {channel}\n",
                "{ Envelope\n",
                "  2\n",
                f"  Key channel{channel}_view0\n",
                f"  Key channel{channel}_view1\n",
                "  Behaviors 1 1\n",
                "}\n",
            ]
        )

    lines.extend(
        [
            "Plugin CameraHandler 1 ShiftCamera\n",
            "{ VariantParameter\n",
            "  3\n",
            "  0\n",
            "  { ParameterValue\n",
            "    0.90399998\n",
            "    1\n",
            "    { Envelope\n",
            "      2\n",
            "      Key shift_view0\n",
            "      Key shift_view1\n",
            "      Behaviors 1 1\n",
            "    }\n",
            "  }\n",
            "}\n",
            "SaveRGBImagesPrefix C:\\renders\\Matrix\n",
        ]
    )
    return "".join(lines)


class LwsGeneratorTests(unittest.TestCase):
    def test_generate_lws_files_creates_expected_camera_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "MasterScene.lws"
            output_dir = temp_path / "output"
            source_path.write_text(build_sample_scene(), encoding="utf-8")

            result = generate_lws_files(source_path, output_dir, num_channels=6, num_views=2)

            self.assertEqual(2, len(result.output_paths))
            self.assertTrue((output_dir / "CAMERA_00.lws").is_file())
            self.assertTrue((output_dir / "CAMERA_01.lws").is_file())

            camera_one_text = (output_dir / "CAMERA_01.lws").read_text(encoding="utf-8")
            self.assertIn("  Key channel0_view1\n", camera_one_text)
            self.assertIn("  Key channel5_view1\n", camera_one_text)
            self.assertIn("      Key shift_view1\n", camera_one_text)
            self.assertIn("SaveRGBImagesPrefix C:\\renders\\Matrix_CAMERA01_\n", camera_one_text)
            self.assertNotIn("channel0_view0", camera_one_text)

    def test_generate_lws_files_inserts_rgb_prefix_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "MasterScene.lws"
            output_dir = temp_path / "output"
            source_text = build_sample_scene().replace(
                "SaveRGBImagesPrefix C:\\renders\\Matrix\n",
                "",
            )
            source_path.write_text(source_text, encoding="utf-8")

            generate_lws_files(source_path, output_dir, num_channels=6, num_views=1)

            camera_zero_text = (output_dir / "CAMERA_00.lws").read_text(encoding="utf-8")
            self.assertIn(
                f"SaveRGBImagesPrefix {output_dir / source_path.stem}_CAMERA00_\n",
                camera_zero_text,
            )

    def test_generate_lws_files_uses_scene_number_for_render_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "Holo_H120_09t.lws"
            output_dir = temp_path / "output"
            source_text = build_sample_scene().replace(
                "  2\n",
                "  10\n",
            ).replace(
                "Key channel0_view0\n  Key channel0_view1",
                "\n".join([f"Key channel0_view{i}" for i in range(10)]),
            ).replace(
                "Key channel1_view0\n  Key channel1_view1",
                "\n".join([f"Key channel1_view{i}" for i in range(10)]),
            ).replace(
                "Key channel2_view0\n  Key channel2_view1",
                "\n".join([f"Key channel2_view{i}" for i in range(10)]),
            ).replace(
                "Key channel3_view0\n  Key channel3_view1",
                "\n".join([f"Key channel3_view{i}" for i in range(10)]),
            ).replace(
                "Key channel4_view0\n  Key channel4_view1",
                "\n".join([f"Key channel4_view{i}" for i in range(10)]),
            ).replace(
                "Key channel5_view0\n  Key channel5_view1",
                "\n".join([f"Key channel5_view{i}" for i in range(10)]),
            ).replace(
                "Key shift_view0\n      Key shift_view1",
                "\n".join([f"      Key shift_view{i}" for i in range(10)]),
            ).replace(
                "SaveRGBImagesPrefix C:\\renders\\Matrix\n",
                "SaveRGBImagesPrefix Z:\\3dHolo\\Renders\\H120\\H120\n",
            )
            source_text += (
                "BufferList\n"
                "{ BufferList\n"
                "  { Group\n"
                "    \"root\"\n"
                "    { List\n"
                "      \"Final_Render\"\n"
                "      \"\"\n"
                "      \"LW_JPEG(.jpg)\"\n"
                "      \"\"\n"
                "      \"Z:\\\\3dHolo\\\\Renders\\\\H120\"\n"
                "      \"H120\"\n"
                "      35\n"
                "      3\n"
                "    }\n"
                "  }\n"
                "}\n"
            )
            source_path.write_text(source_text, encoding="utf-8")

            result = generate_lws_files(source_path, output_dir, num_channels=6, num_views=10)
            text = result.output_paths[9].read_text(encoding="utf-8")
            self.assertIn("SaveRGBImagesPrefix Z:\\3dHolo\\Renders\\H120\\H120_09_\n", text)
            self.assertIn('      "H120_09_"\n', text)


if __name__ == "__main__":
    unittest.main()
