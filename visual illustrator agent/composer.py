# composer.py

import subprocess
import os
import shutil
from typing import Optional, Tuple


class VideoComposer:
    """Composes final video: animation + audio + burned-in captions via FFmpeg."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def compose(
        self,
        video_path: str,
        output_path: str,
        audio_path: Optional[str] = None,
        srt_path: Optional[str] = None,
    ) -> Tuple[str, bool, str]:
        """
        Compose final video with optional audio and burned-in captions.
        Returns: (final_path, success, error_message)
        """
        if not os.path.exists(video_path):
            return "", False, f"Video not found: {video_path}"

        # Check FFmpeg availability
        if not self._check_ffmpeg():
            print("  ⚠️  FFmpeg not found, copying raw video")
            shutil.copy2(video_path, output_path)
            return output_path, True, "FFmpeg not available"

        has_audio = audio_path and os.path.exists(audio_path)
        has_captions = srt_path and os.path.exists(srt_path)

        if not has_audio and not has_captions:
            shutil.copy2(video_path, output_path)
            return output_path, True, ""

        try:
            if has_audio and has_captions:
                return self._compose_all(
                    video_path, audio_path, srt_path, output_path
                )
            elif has_audio:
                return self._add_audio(video_path, audio_path, output_path)
            elif has_captions:
                return self._add_captions(video_path, srt_path, output_path)
        except Exception as e:
            # Fallback: just copy the video
            print(f"  ⚠️  Composition error: {e}, using raw video")
            shutil.copy2(video_path, output_path)
            return output_path, True, f"Composition failed: {e}"

        return "", False, "Unknown composition error"

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _add_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str
    ) -> Tuple[str, bool, str]:
        """Merge audio track into video."""
        print("  🔊 Adding audio track...")

        video_dur = self._get_duration(video_path)
        audio_dur = self._get_duration(audio_path)
        print(f"     Video: {video_dur:.1f}s, Audio: {audio_dur:.1f}s")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"  ✅ Audio merged")
            return output_path, True, ""
        else:
            error = result.stderr[-500:] if result.stderr else "Unknown error"
            print(f"  ❌ Audio merge failed")
            return "", False, error

    def _add_captions(
        self,
        video_path: str,
        srt_path: str,
        output_path: str
    ) -> Tuple[str, bool, str]:
        """Burn SRT captions into video using FFmpeg."""
        print("  📝 Burning captions into video...")

        # Convert SRT path to absolute path to avoid escaping issues
        abs_srt = os.path.abspath(srt_path)

        # Method 1: Use absolute path with proper escaping for the subtitles filter
        # FFmpeg subtitle filter needs special escaping on all platforms
        # Safest approach: use the subtitles filter with proper path handling

        # For the subtitles filter, we need to escape: \ : '
        # On macOS/Linux, colons and backslashes need escaping
        escaped_srt = abs_srt.replace("\\", "/")
        escaped_srt = escaped_srt.replace(":", "\\\\:")
        escaped_srt = escaped_srt.replace("'", "\\'")

        style = (
            "FontName=Arial,"
            "FontSize=20,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "Outline=2,"
            "Shadow=1,"
            "MarginV=80,"
            "Alignment=2"
        )

        # Try method 1: subtitles filter with force_style
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_srt}':force_style='{style}'",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"  ✅ Captions burned in (styled)")
            return output_path, True, ""

        print(f"  ⚠️  Styled subtitles failed, trying method 2...")

        # Method 2: simpler subtitles filter
        cmd2 = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={escaped_srt}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]

        result2 = subprocess.run(cmd2, capture_output=True, text=True)

        if result2.returncode == 0:
            print(f"  ✅ Captions burned in (simple)")
            return output_path, True, ""

        print(f"  ⚠️  Subtitles filter failed, trying drawtext method...")

        # Method 3: Use drawtext as fallback (reads SRT manually)
        captions = self._parse_srt(srt_path)
        if captions:
            return self._burn_captions_drawtext(
                video_path, captions, output_path
            )

        # Last resort: copy without captions
        print(f"  ⚠️  All caption methods failed. Using video without captions.")
        shutil.copy2(video_path, output_path)
        return output_path, True, "Captions could not be burned in"

    def _burn_captions_drawtext(
        self,
        video_path: str,
        captions: list,
        output_path: str
    ) -> Tuple[str, bool, str]:
        """Burn captions using drawtext filter as fallback."""
        drawtext_parts = []

        for cap in captions:
            start = cap["start"]
            end = cap["end"]
            text = cap["text"].replace("'", "\\'").replace(":", "\\:")

            part = (
                f"drawtext=text='{text}':"
                f"fontcolor=white:fontsize=28:"
                f"borderw=2:bordercolor=black:"
                f"x=(w-text_w)/2:y=h-100:"
                f"enable='between(t,{start},{end})'"
            )
            drawtext_parts.append(part)

        if not drawtext_parts:
            shutil.copy2(video_path, output_path)
            return output_path, True, "No captions to draw"

        filter_str = ",".join(drawtext_parts)

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"  ✅ Captions burned in (drawtext)")
            return output_path, True, ""
        else:
            print(f"  ⚠️  drawtext also failed. Copying raw video.")
            shutil.copy2(video_path, output_path)
            return output_path, True, "All caption methods failed"

    def _parse_srt(self, srt_path: str) -> list:
        """Parse SRT file into list of {start, end, text}."""
        captions = []
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            blocks = content.split("\n\n")
            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) >= 3:
                    # Parse timestamp line
                    ts_line = lines[1]
                    if "-->" in ts_line:
                        parts = ts_line.split("-->")
                        start = self._srt_to_seconds(parts[0].strip())
                        end = self._srt_to_seconds(parts[1].strip())
                        text = " ".join(lines[2:])
                        captions.append({
                            "start": start,
                            "end": end,
                            "text": text
                        })
        except Exception as e:
            print(f"  ⚠️  SRT parse error: {e}")

        return captions

    def _srt_to_seconds(self, ts: str) -> float:
        """Convert SRT timestamp to seconds."""
        try:
            ts = ts.replace(",", ".")
            parts = ts.split(":")
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except Exception:
            return 0.0

    def _compose_all(
        self,
        video_path: str,
        audio_path: str,
        srt_path: str,
        output_path: str
    ) -> Tuple[str, bool, str]:
        """Compose video + audio + captions in two steps."""
        temp_with_audio = os.path.join(self.output_dir, "_temp_audio.mp4")

        # Step 1: Add audio
        path, success, error = self._add_audio(
            video_path, audio_path, temp_with_audio
        )
        if not success:
            # Try without audio, just captions
            print(f"  ⚠️  Audio failed, trying captions only")
            return self._add_captions(video_path, srt_path, output_path)

        # Step 2: Burn captions
        path, success, error = self._add_captions(
            temp_with_audio, srt_path, output_path
        )

        # Cleanup
        try:
            if os.path.exists(temp_with_audio):
                os.remove(temp_with_audio)
        except Exception:
            pass

        return path, success, error

    def _get_duration(self, file_path: str) -> float:
        """Get media file duration using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    file_path
                ],
                capture_output=True,
                text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 30.0