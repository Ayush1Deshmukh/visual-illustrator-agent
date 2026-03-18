# renderer.py

import subprocess
import os
import sys
import shutil
from datetime import datetime


class ManimRenderer:
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
        # Save the scene file
        scene_file = os.path.join(self.temp_dir, "scene.py")
        with open(scene_file, "w") as f:
            f.write(code)

        # Build manim command
        cmd = [
            sys.executable, "-m", "manim",
            "render",
            scene_file,
            "ConceptScene",
            "-ql",                          # low quality for fast rendering
            "--format", "mp4",
            "--resolution", "720,1280",     # 9:16 aspect ratio
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
                    safe_name = concept_name.replace(" ", "_").replace("'", "").lower()
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    final_name = f"{safe_name}_{timestamp}.mp4"
                    final_path = os.path.join(self.output_dir, final_name)

                    shutil.move(video_path, final_path)
                    print(f"   ✅ Video saved to: {final_path}")
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

    def _extract_error(self, stderr: str) -> str:
        """Extract the most useful error information from stderr."""
        lines = stderr.strip().split("\n")

        # Look for common Python error patterns
        error_lines = []
        capture = False

        for i, line in enumerate(lines):
            # Start capturing from Traceback
            if "Traceback" in line:
                capture = True
                error_lines = [line]
                continue

            if capture:
                error_lines.append(line)

        if error_lines:
            # Return last 20 lines of traceback
            return "\n".join(error_lines[-20:])

        # If no traceback found, return last 15 lines
        return "\n".join(lines[-15:])

    def _find_output_video(self) -> str:
        """Search for the rendered video file."""
        # Manim saves to: media_dir/videos/scene/quality/ConceptScene.mp4
        candidates = []

        for root, dirs, files in os.walk(self.temp_dir):
            for f in files:
                if f.endswith(".mp4"):
                    full_path = os.path.join(root, f)
                    candidates.append((full_path, os.path.getmtime(full_path)))

        if not candidates:
            return ""

        # Return the most recently created mp4
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def cleanup_temp(self):
        """Clean up temporary rendering files but keep the directory."""
        for item in os.listdir(self.temp_dir):
            item_path = os.path.join(self.temp_dir, item)
            try:
                if os.path.isfile(item_path) and not item_path.endswith('.py'):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception:
                pass