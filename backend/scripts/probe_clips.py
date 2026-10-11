"""Print fps, resolution, duration and codec of every .mp4 in data/.

With --transcode, re-encode non-H.264 clips to H.264 (browsers only play H.264).
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
H264_FOURCCS = {"avc1", "h264", "x264"}


def probe(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        code = int(cap.get(cv2.CAP_PROP_FOURCC))
    finally:
        cap.release()
    fourcc = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4)).strip().lower()
    return {
        "name": path.name,
        "fps": fps,
        "size": (w, h),
        "duration": frames / fps if fps else 0.0,
        "codec": fourcc,
        "h264": fourcc in H264_FOURCCS,
    }


def transcode(path: Path) -> Path:
    import imageio_ffmpeg

    tmp = path.with_suffix(".h264.mp4")
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", str(tmp),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    tmp.replace(path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcode", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = ap.parse_args()
    for clip in sorted(args.data_dir.glob("*.mp4")):
        info = probe(clip)
        print(
            f"{info['name']}: {info['fps']:.2f} fps, {info['size'][0]}x{info['size'][1]}, "
            f"{info['duration']:.1f} s, codec={info['codec']}, h264={info['h264']}"
        )
        if args.transcode and not info["h264"]:
            transcode(clip)
            print(f"  transcoded -> {probe(clip)['codec']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
