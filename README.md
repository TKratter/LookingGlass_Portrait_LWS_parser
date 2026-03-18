# Looking Glass Portrait Tools

This repo contains two tools for a Looking Glass Portrait workflow:

- `LwsGeneratorGUI.py`: select a master `.lws` scene and generate the 48 `CAMERA_00.lws` to `CAMERA_47.lws` files.
- `QuiltMakerGUI.py`: select a folder of rendered images named like `PREFIX_CAMERA00_000.jpg` and generate Portrait quilts for every complete frame set.

## Easiest way to get the EXEs

This repo includes a GitHub Actions workflow that builds both Windows `.exe` files on every push to `main` and on manual runs.

1. Open the repo on GitHub.
2. Go to the `Actions` tab.
3. Open `Build Windows EXEs`.
4. Run the workflow or use the latest successful run.
5. Download the `lookingglass-windows-exes` artifact.

The artifact contains:

- `LookingGlassLwsGenerator.exe`
- `LookingGlassQuiltMaker.exe`

## Local Windows build in one step

If you want to build locally on Windows, install Python 3.9 or newer once, then run:

```bat
build_windows_release.bat
```

That script will:

1. Create a local virtual environment in `.venv`
2. Install the build dependencies
3. Build both `.exe` files with PyInstaller

The finished EXEs will be written to:

```text
dist\LookingGlassLwsGenerator.exe
dist\LookingGlassQuiltMaker.exe
```

## Manual local Windows build

If you want to run the steps yourself:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-build.txt
build_windows.bat
```

## Run the tools without building EXEs

After installing the regular dependencies:

```bat
pip install -r requirements.txt
python LwsGeneratorGUI.py
python QuiltMakerGUI.py
```

## CLI usage

Generate scene files:

```bat
python main.py "C:\path\to\MasterScene.lws" "C:\path\to\output"
```

Build quilts:

```bat
python QuiltMaker.py "C:\path\to\renders" "C:\path\to\quilts"
```

If the render folder contains multiple prefixes, pass `--sequence-prefix`.

## Expected render naming

The quilt tool scans for files matching this pattern:

```text
PREFIX_CAMERA00_000.jpg
```

For the Portrait workflow, it expects 48 camera renders per animation frame, using cameras `00` through `47`.
