#!/usr/bin/env python3
"""
Cross-platform build script for BrainBoost File Search tools.
Generates standalone executables using PyInstaller for Windows, macOS, and Linux.

Usage:
    python build.py                  # Build the main search_index app
    python build.py --app time_viewer  # Build the time_viewer app
    python build.py --app all        # Build both apps
    python build.py --clean          # Remove previous build artifacts
"""

import subprocess
import sys
import platform
import shutil
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

APPS = {
    "search_index": {
        "script": SCRIPT_DIR / "brainboost_data_tools_search_index.py",
        "name": "BrainBoostFileSearch",
        "icon_svg": SCRIPT_DIR / "brainboost_search_icon.svg",
    },
    "time_viewer": {
        "script": SCRIPT_DIR / "brainboost_data_tools_time_viewer.py",
        "name": "BrainBoostTimeViewer",
        "icon_svg": None,
    },
}

HIDDEN_IMPORTS = [
    "PyQt5",
    "PyQt5.QtWidgets",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtSvg",
    "sqlite3",
]

# Legacy import path used by the tool entries (shim under desktop native).
_DESKTOP_ROOT = SCRIPT_DIR.parent.parent / "desktop" / "subjective_desktop_native"
_CHROME_HIDDEN_IMPORTS = (
    "com_subjective_tools",
    "com_subjective_tools.window_chrome",
    "com_subjective_ui",
    "com_subjective_ui.window_chrome",
)

EXTRA_DATA = [
    # (source, destination_in_bundle)
    (SCRIPT_DIR / "database_client.py", "."),
]


def get_platform():
    """Return a normalised platform name."""
    s = platform.system().lower()
    if s == "darwin":
        return "macos"
    return s  # "windows" or "linux"


def ensure_pyinstaller():
    """Install PyInstaller if it is not already available."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found — installing …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean(dist_dir: Path, build_dir: Path):
    """Remove previous build artefacts."""
    for d in (dist_dir, build_dir):
        if d.exists():
            print(f"Removing {d}")
            shutil.rmtree(d)
    spec_files = list(SCRIPT_DIR.glob("*.spec"))
    for f in spec_files:
        print(f"Removing {f}")
        f.unlink()
    print("Clean complete.")


def build_app(app_key: str, one_file: bool = True):
    """Build a single application with PyInstaller."""
    app = APPS[app_key]
    script = app["script"]
    name = app["name"]
    plat = get_platform()

    if not script.exists():
        print(f"ERROR: entry-point not found: {script}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Building {name} for {plat} ({platform.machine()})")
    print(f"{'='*60}\n")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--windowed",          # no console window (GUI app)
        "--name", name,
    ]

    if one_file:
        cmd.append("--onefile")

    if _DESKTOP_ROOT.is_dir():
        cmd.extend(["--paths", str(_DESKTOP_ROOT)])

    # Hidden imports
    for mod in (*HIDDEN_IMPORTS, *_CHROME_HIDDEN_IMPORTS):
        cmd.extend(["--hidden-import", mod])

    # Extra data files
    sep = ";" if plat == "windows" else ":"
    for src, dst in EXTRA_DATA:
        if Path(src).exists():
            cmd.extend(["--add-data", f"{src}{sep}{dst}"])

    # Icon handling — convert SVG to ICO/ICNS if possible, otherwise skip
    icon_path = _resolve_icon(app.get("icon_svg"), plat)
    if icon_path:
        cmd.extend(["--icon", str(icon_path)])

    # Entry-point script
    cmd.append(str(script))

    print("Running:", " ".join(str(c) for c in cmd), "\n")
    subprocess.check_call(cmd, cwd=str(SCRIPT_DIR))

    # Report result
    dist_dir = SCRIPT_DIR / "dist"
    if plat == "windows":
        exe = dist_dir / f"{name}.exe"
    elif plat == "macos":
        exe = dist_dir / f"{name}.app" if not one_file else dist_dir / name
    else:
        exe = dist_dir / name

    if exe.exists():
        print(f"\nBuild successful: {exe}")
    else:
        print(f"\nBuild finished — output in {dist_dir}")


def _resolve_icon(svg_path, plat):
    """Try to produce a platform-appropriate icon file from the SVG.

    Returns the path to the icon file, or None if conversion is not available.
    ICO/ICNS files placed next to the SVG are reused automatically so you can
    also provide them manually.
    """
    if svg_path is None or not Path(svg_path).exists():
        return None

    # Check for pre-existing converted icons
    ico = svg_path.with_suffix(".ico")
    icns = svg_path.with_suffix(".icns")

    if plat == "windows" and ico.exists():
        return ico
    if plat == "macos" and icns.exists():
        return icns

    # Attempt conversion via Pillow + cairosvg (best-effort)
    try:
        import cairosvg
        from PIL import Image
        import io

        png_data = cairosvg.svg2png(url=str(svg_path), output_width=256, output_height=256)
        img = Image.open(io.BytesIO(png_data))

        if plat == "windows":
            img.save(str(ico), format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            return ico
        elif plat == "macos":
            # macOS .icns is complex; just skip and let PyInstaller handle PNG
            png_path = svg_path.with_suffix(".png")
            img.save(str(png_path))
            return png_path
        else:
            png_path = svg_path.with_suffix(".png")
            img.save(str(png_path))
            return png_path
    except ImportError:
        print("Note: Install 'cairosvg' and 'Pillow' to auto-convert the SVG icon.")
        print("      Continuing build without a custom icon.\n")
        return None


def main():
    parser = argparse.ArgumentParser(description="Build BrainBoost File Search executables")
    parser.add_argument(
        "--app",
        choices=["search_index", "time_viewer", "all"],
        default="search_index",
        help="Which application to build (default: search_index)",
    )
    parser.add_argument("--clean", action="store_true", help="Remove previous build artifacts and exit")
    parser.add_argument("--onedir", action="store_true", help="Produce a one-directory bundle instead of a single file")
    args = parser.parse_args()

    dist_dir = SCRIPT_DIR / "dist"
    build_dir = SCRIPT_DIR / "build"

    if args.clean:
        clean(dist_dir, build_dir)
        return

    ensure_pyinstaller()

    one_file = not args.onedir

    if args.app == "all":
        for key in APPS:
            build_app(key, one_file=one_file)
    else:
        build_app(args.app, one_file=one_file)


if __name__ == "__main__":
    main()
