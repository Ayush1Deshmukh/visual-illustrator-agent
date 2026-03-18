# renderer.py

import subprocess
import os
import sys
import shutil
from datetime import datetime


class ManimRenderer:
    """Renders Manim code to 9:16 vertical video."""

    def __init__(self, output_dir: str = "output", temp_dir: str = "temp"):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

    def render(self, code: str, concept_name: str) -> tuple:
        """
        Render Manim code to a 9:16 video.
        Returns: (output_path, success, error_message)
        """
        scene_file = os.path.join(self.temp_dir, "scene.py")
        with open(scene_file, "w") as f:
            f.write(code)

        cmd = [
            sys.executable, "-m", "manim",
            "render",
            scene_file,
            "ConceptScene",
            "-ql",
            "--format", "mp4",
            "--resolution", "720,1280",
            "--media_dir", self.temp_dir,
        ]

        print(f"\n🎬 Rendering video...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                cwd=os.getcwd(),
            )

            if result.returncode == 0:
                video_path = self._find_output_video()
                if video_path:
                    safe_name = self._safe_filename(concept_name)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    final_name = f"{safe_name}_{timestamp}.mp4"
                    final_path = os.path.join(self.output_dir, final_name)

                    shutil.copy2(video_path, final_path)
                    print(f"   ✅ Video rendered: {final_path}")
                    return final_path, True, ""
                else:
                    return "", False, "Video file not found after rendering"
            else:
                error = self._extract_error(result.stderr)
                print(f"   ❌ Render failed")
                return "", False, error

        except subprocess.TimeoutExpired:
            return "", False, "Rendering timed out (>3 minutes)"
        except Exception as e:
            return "", False, str(e)

    def _safe_filename(self, name: str) -> str:
        """Convert concept name to safe filename."""
        safe = name.lower().replace(" ", "_")
        safe = "".join(c for c in safe if c.isalnum() or c == '_')
        return safe[:50]

    def _extract_error(self, stderr: str) -> str:
        """Extract the full traceback from stderr."""
        lines = stderr.strip().split("\n")
        error_lines = []
        capture = False

        for line in lines:
            if "Traceback" in line:
                capture = True
                error_lines = [line]
                continue
            if capture:
                error_lines.append(line)

        if error_lines:
            # Return more context — up to 30 lines
            return "\n".join(error_lines[-30:])

        # No traceback found — return last 20 lines
        return "\n".join(lines[-20:])

    def _find_output_video(self) -> str:
        """Find the most recently created mp4 in temp directory."""
        candidates = []
        for root, dirs, files in os.walk(self.temp_dir):
            for f in files:
                if f.endswith(".mp4"):
                    full_path = os.path.join(root, f)
                    candidates.append(
                        (full_path, os.path.getmtime(full_path))
                    )

        if not candidates:
            return ""

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path
                ],
                capture_output=True,
                text=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 20.0

    def cleanup_temp(self):
        """Clean up temp files but keep the directory."""
        for item in os.listdir(self.temp_dir):
            item_path = os.path.join(self.temp_dir, item)
            try:
                if os.path.isfile(item_path) and not item_path.endswith('.py'):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception:
                pass