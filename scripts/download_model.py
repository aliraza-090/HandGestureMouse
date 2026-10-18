"""Download the MediaPipe hand landmarker model used by HandGestureMouse.

The application runs fully offline; the model file is fetched only once,
either during development or bundling.  It is stored inside the package so it
can be shipped inside the PyInstaller build.

Usage:
    python scripts/download_model.py [--force] [--url URL]
"""

import argparse
import os
import sys
import urllib.request

DEFAULT_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_NAME = "hand_landmarker.task"


def target_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "src", "handgesturemouse", "resources", "models", MODEL_NAME)


def _progress(block_num, block_size, total_size):
    if total_size <= 0:
        return
    downloaded = min(block_num * block_size, total_size)
    percent = downloaded * 100 // total_size
    sys.stdout.write(f"\rDownloading model: {percent:3d}% ({downloaded // 1024} KiB)")
    sys.stdout.flush()


def download(url: str, dest: str, force: bool = False) -> str:
    dest = os.path.abspath(dest)
    if os.path.isfile(dest) and not force:
        print(f"Model already present: {dest}")
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"Downloading {url}")
    tmp = dest + ".part"
    urllib.request.urlretrieve(url, tmp, _progress)
    print()
    with open(tmp, "rb") as fh:
        magic = fh.read(4)
    if magic[:2] != b"PK":
        os.remove(tmp)
        raise SystemExit("Downloaded file does not look like a valid MediaPipe task bundle")
    if os.path.exists(dest):
        os.remove(dest)
    os.replace(tmp, dest)
    print(f"Saved model to {dest}")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the MediaPipe hand landmarker model")
    parser.add_argument("--url", default=DEFAULT_URL, help="model URL")
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args()
    download(args.url, target_path(), force=args.force)


if __name__ == "__main__":
    main()