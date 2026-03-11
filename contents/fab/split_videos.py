"""
フォルダ内の動画を5秒単位に自動分割するスクリプト（ffmpeg版）
=============================================================
moviepyの一時ファイル問題を解消。ffmpegを直接使用。

使い方：
  python split_videos.py                          # カレントフォルダ、5秒分割
  python split_videos.py --input C:/動画 --sec 5
  python split_videos.py --cleanup                # ゴミファイル削除してから実行
"""

import os, sys, argparse, subprocess, shutil
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".flv", ".webm"}


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    for c in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if Path(c).exists():
            return c
    return None


def cleanup_temp_files(folder: Path):
    removed = 0
    for f in list(folder.glob("*TEMP_MPY*")) + list(folder.glob("*wvf_snd*")):
        try:
            f.unlink()
            print(f"  🗑 削除: {f.name}")
            removed += 1
        except Exception as e:
            print(f"  ⚠ 削除失敗: {f.name} ({e})")
    return removed


def get_duration(ffmpeg: str, video_path: Path) -> float:
    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists():
        ffprobe = shutil.which("ffprobe") or ffmpeg
    r = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def split_video(ffmpeg: str, video_path: Path, output_dir: Path, clip_sec: int):
    print(f"\n▶ 処理中: {video_path.name}")
    duration = get_duration(ffmpeg, video_path)
    if duration <= 0:
        print(f"  ⚠ 長さ取得失敗、スキップ")
        return 0

    total_clips = int(duration // clip_sec) + (1 if duration % clip_sec > 0.5 else 0)
    print(f"  長さ: {duration:.1f}秒 → {total_clips}クリップ")

    video_out_dir = output_dir / video_path.stem
    video_out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for i in range(total_clips):
        start = i * clip_sec
        end   = min((i + 1) * clip_sec, duration)
        if end - start < 0.5:
            break

        out_name = f"{video_path.stem}_{i+1:03d}_{int(start):04d}-{int(end):04d}s{video_path.suffix}"
        out_path = video_out_dir / out_name

        cmd = [
            ffmpeg, "-y",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(end - start),
            "-c", "copy",
            "-avoid_negative_ts", "1",
            str(out_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            size_kb = out_path.stat().st_size // 1024
            print(f"  ✅ [{i+1:03d}/{total_clips}] {out_name}  ({size_kb}KB)")
            saved += 1
        else:
            print(f"  ⚠ [{i+1:03d}] 失敗")
    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",   "-i", default=".")
    parser.add_argument("--output",  "-o", default=None)
    parser.add_argument("--sec",     "-s", type=int, default=5)
    parser.add_argument("--cleanup", "-c", action="store_true", help="TEMP_MPYゴミファイルを先に削除")
    args = parser.parse_args()

    input_dir  = Path(args.input).resolve()
    output_dir = Path(args.output).resolve() if args.output else input_dir / "split_output"

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("❌ ffmpegが見つかりません。pip install imageio-ffmpeg を実行してください。")
        sys.exit(1)
    print(f"✅ ffmpeg: {ffmpeg}")

    if args.cleanup:
        print(f"\n🗑 ゴミファイル削除中: {input_dir}")
        n = cleanup_temp_files(input_dir)
        print(f"  {n}件削除完了\n")

    videos = sorted([p for p in input_dir.iterdir()
                     if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS])
    if not videos:
        print(f"⚠ 動画が見つかりません: {input_dir}")
        sys.exit(0)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📂 入力: {input_dir}")
    print(f"📂 出力: {output_dir}")
    print(f"✂️  分割: {args.sec}秒 / 🎬 動画: {len(videos)}本")
    print("=" * 50)

    total = sum(split_video(ffmpeg, v, output_dir, args.sec) for v in videos)
    print("\n" + "=" * 50)
    print(f"🎉 完了！合計 {total} クリップ保存 → {output_dir}")


if __name__ == "__main__":
    main()
