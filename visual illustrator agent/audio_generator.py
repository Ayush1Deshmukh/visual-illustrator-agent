# audio_generator.py

import asyncio
import os
import subprocess
from typing import Optional, Tuple

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️  edge-tts not installed. Run: pip install edge-tts")


class AudioGenerator:
    """Generates voice narration using Edge-TTS and creates SRT captions."""

    def __init__(
        self,
        voice: str = "en-US-AriaNeural",
        output_dir: str = "temp"
    ):
        self.voice = voice
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    async def _generate_audio_async(
        self,
        text: str,
        output_path: str,
        subtitle_path: str = None
    ):
        """Generate audio and optionally save word-level subtitles."""
        communicate = edge_tts.Communicate(text, self.voice)

        # Method 1: Use communicate.save() for audio — most reliable
        await communicate.save(output_path)

        # Method 2: Generate subtitles separately if needed
        if subtitle_path:
            try:
                submaker = edge_tts.SubMaker()
                communicate2 = edge_tts.Communicate(text, self.voice)

                async for chunk in communicate2.stream():
                    if chunk["type"] == "WordBoundary":
                        submaker.create_sub(
                            (chunk["offset"], chunk["duration"]),
                            chunk["text"]
                        )

                # Try different SubMaker output methods (API varies by version)
                subs_content = None
                for method_name in ["generate_subs", "get_subs", "generate"]:
                    method = getattr(submaker, method_name, None)
                    if method and callable(method):
                        try:
                            subs_content = method()
                            break
                        except Exception:
                            continue

                # Fallback: try converting submaker to string
                if subs_content is None:
                    try:
                        subs_content = str(submaker)
                        if len(subs_content) < 10:
                            subs_content = None
                    except Exception:
                        pass

                if subs_content:
                    with open(subtitle_path, "w", encoding="utf-8") as f:
                        f.write(subs_content)
                    print(f"  📝 Word-level subtitles saved: {subtitle_path}")
                else:
                    print(f"  ⚠️  Could not generate word-level subtitles (SubMaker API changed)")

            except Exception as e:
                print(f"  ⚠️  Subtitle generation failed: {e}")

    def generate_narration(self, script: dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate narration audio from script sections.
        Returns: (audio_path, vtt_path) or (None, None) on failure
        """
        if not EDGE_TTS_AVAILABLE:
            print("  ⚠️  edge-tts not available, skipping audio generation")
            return None, None

        # Collect narration from all sections
        narration_parts = []
        for section in script.get("sections", []):
            narration = section.get("narration", "")
            if narration:
                narration_parts.append(narration.strip())

        full_narration = " ".join(narration_parts)

        if not full_narration.strip():
            print("  ⚠️  No narration text found in script")
            return None, None

        audio_path = os.path.join(self.output_dir, "narration.mp3")
        vtt_path = os.path.join(self.output_dir, "narration.vtt")

        print(f"  🎙️  Generating narration ({len(full_narration)} chars)...")
        print(f"  📝 Preview: \"{full_narration[:80]}...\"")
        print(f"  🗣️  Voice: {self.voice}")

        try:
            # Handle event loop for Python 3.9 compatibility
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're inside an existing event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(
                        asyncio.run,
                        self._generate_audio_async(full_narration, audio_path, vtt_path)
                    ).result()
            else:
                asyncio.run(
                    self._generate_audio_async(full_narration, audio_path, vtt_path)
                )

            # Verify the audio was created and has content
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                duration = self._get_audio_duration(audio_path)
                print(f"  ✅ Audio saved: {audio_path} ({duration:.1f}s)")
                return audio_path, vtt_path if os.path.exists(vtt_path) else None
            else:
                print("  ❌ Audio file is empty or too small")
                return None, None

        except Exception as e:
            print(f"  ❌ Audio generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def generate_srt_from_script(
        self,
        script: dict,
        video_duration: float
    ) -> Optional[str]:
        """
        Generate SRT caption file from script sections.
        Captions are timed to match video duration proportionally.
        Returns: path to SRT file
        """
        srt_path = os.path.join(self.output_dir, "captions.srt")
        srt_lines = []

        sections = script.get("sections", [])
        if not sections:
            print("  ⚠️  No sections in script for captions")
            return None

        # Calculate time scaling
        total_script_duration = sum(s.get("duration", 3) for s in sections)
        if total_script_duration <= 0:
            total_script_duration = len(sections) * 5

        scale = video_duration / total_script_duration

        current_time = 0.0
        caption_idx = 1

        for section in sections:
            caption = section.get("caption", "")
            section_duration = section.get("duration", 3) * scale

            if caption:
                start_ts = self._format_srt_time(current_time + 0.2)
                end_ts = self._format_srt_time(
                    current_time + section_duration - 0.2
                )

                srt_lines.append(str(caption_idx))
                srt_lines.append(f"{start_ts} --> {end_ts}")
                srt_lines.append(caption)
                srt_lines.append("")

                caption_idx += 1

            current_time += section_duration

        if not srt_lines:
            print("  ⚠️  No captions generated from script")
            return None

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))

        print(f"  📝 Captions saved: {srt_path} ({caption_idx - 1} entries)")
        return srt_path

    def _format_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp: HH:MM:SS,mmm"""
        seconds = max(0, seconds)
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path
                ],
                capture_output=True,
                text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0