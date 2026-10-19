"""Build a self-contained local web server for the current OS/architecture."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "dist"


def main():
    import imageio_ffmpeg
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("首版发行包须在 macOS Apple 芯片环境构建。其他平台需要独立实测。")
    subprocess.run(["pnpm", "-C", str(ROOT / "frontend"), "run", "build"], check=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "smash-suite",
               "--paths", str(ROOT / "backend"), "--distpath", str(OUTPUT), "--workpath", str(OUTPUT / "build"),
               "--specpath", str(OUTPUT / "build"), "--add-data", f"{ROOT / 'frontend/dist'}:web",
               "--add-data", f"{ROOT / 'backend/app/algorithms/profiles.json'}:app/algorithms",
               "--add-data", f"{ROOT / 'backend/app/algorithms/provenance.json'}:app/algorithms",
               "--add-data", f"{ROOT / 'backend/app/algorithms/SoloShuttlePose-LICENSE.txt'}:licenses",
               "--add-binary", f"{imageio_ffmpeg.get_ffmpeg_exe()}:bin",
               "--collect-data", "ultralytics", "--collect-data", "certifi",
               "--hidden-import", "torchvision.models.detection.keypoint_rcnn",
               "--hidden-import", "app.worker", "--exclude-module", "pandas",
               "--exclude-module", "IPython", "--exclude-module", "tkinter", str(ROOT / "tools/package/entry.py")]
    OUTPUT.mkdir(exist_ok=True)
    subprocess.run(command, check=True, cwd=ROOT)
    package = OUTPUT / "smash-suite"
    # The Python wheel's static encoder has a versioned filename. The runtime
    # deliberately resolves one stable, application-owned executable name.
    binary_dir = package / "_internal/bin"
    binaries = list(binary_dir.glob("ffmpeg*"))
    if len(binaries) != 1:
        raise RuntimeError("发行包中未找到唯一的 FFmpeg。")
    if binaries[0].name != "ffmpeg":
        binaries[0].rename(binary_dir / "ffmpeg")
    shutil.copy2(ROOT / "docs/product-usage.txt", package / "使用说明.txt")
    shutil.copy2(ROOT / "docs/product-third-party.txt", package / "第三方声明.txt")
    (package / "build-info.json").write_text(json.dumps(dict(version="0.2.0", system=platform.system(),
                                                            architecture=platform.machine(), python=platform.python_version()), indent=2))
    archive = shutil.make_archive(str(OUTPUT / "SmashSuite-macos-arm64"), "zip", root_dir=OUTPUT, base_dir="smash-suite")
    print(archive)


if __name__ == "__main__":
    main()
