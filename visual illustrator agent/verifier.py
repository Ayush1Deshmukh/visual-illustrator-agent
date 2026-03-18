# verifier.py

import cv2
import os
import json
import re
import numpy as np
from typing import Tuple, List


class VideoVerifier:
    """Verifies rendered video quality using frame analysis + optional vision model."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.client = None

        if api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=api_key)
                self.model = os.getenv("LLM_MODEL")
            except ImportError:
                print("  ⚠️  google-genai not installed, vision check disabled")

    def extract_frames(self, video_path: str, num_frames: int = 5) -> List[str]:
        """Extract evenly-spaced frames from video as PNG images."""
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames == 0:
            cap.release()
            return []

        # Skip first and last 10% to avoid blank intro/outro frames
        start_frame = int(total_frames * 0.1)
        end_frame = int(total_frames * 0.9)

        if end_frame <= start_frame:
            start_frame = 0
            end_frame = total_frames - 1

        frame_indices = np.linspace(
            start_frame, end_frame, num_frames, dtype=int
        )
        frame_paths = []

        os.makedirs("temp/frames", exist_ok=True)

        for i, idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                path = f"temp/frames/frame_{i}.png"
                cv2.imwrite(path, frame)
                frame_paths.append(path)

        cap.release()
        return frame_paths

    def basic_checks(self, video_path: str) -> Tuple[bool, List[str]]:
        """Run automated quality checks on the video."""
        issues = []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return False, ["Cannot open video file"]

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        print(f"  📐 Video: {width}x{height}, {duration:.1f}s, {fps:.0f}fps, {total_frames} frames")

        # Check 1: Duration
        if duration < 3:
            issues.append(f"Video too short: {duration:.1f}s (expected 15-40s)")
        elif duration > 120:
            issues.append(f"Video too long: {duration:.1f}s (expected 15-40s)")

        # Check 2: Aspect ratio
        if width > 0 and height > 0:
            aspect = height / width
            if aspect < 1.5 or aspect > 2.0:
                issues.append(
                    f"Wrong aspect ratio: {width}x{height} (expected ~9:16)"
                )

        # Check 3: Blank and static frame detection
        # IMPORTANT: Manim default background is dark (#1e1e1e ≈ RGB 30,30,30)
        # so we use a higher threshold than pure black
        sample_count = min(10, total_frames)

        # Sample from the middle 80% of the video (skip intro/outro)
        start_frame = int(total_frames * 0.1)
        end_frame = int(total_frames * 0.9)
        if end_frame <= start_frame:
            start_frame = 0
            end_frame = total_frames - 1

        sample_indices = np.linspace(
            start_frame, end_frame, sample_count, dtype=int
        )

        prev_frame = None
        blank_count = 0
        static_count = 0
        has_content_count = 0

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Manim background is ~30 gray value
            # A "blank" frame means ONLY background, no content at all
            # We check if there are ANY pixels significantly brighter than background
            bright_pixels = np.sum(gray > 50)  # pixels brighter than dark gray
            total_pixels = gray.shape[0] * gray.shape[1]
            content_ratio = bright_pixels / total_pixels

            if content_ratio < 0.005:
                # Less than 0.5% of pixels have content — truly blank
                blank_count += 1
            else:
                has_content_count += 1

            # Static detection
            if prev_frame is not None:
                diff = cv2.absdiff(gray, prev_frame)
                if np.mean(diff) < 0.5:
                    static_count += 1

            prev_frame = gray.copy()

        cap.release()

        print(f"  📊 Content analysis: {has_content_count}/{sample_count} frames have content, "
              f"{blank_count} blank, {static_count} static")

        if blank_count > sample_count * 0.7:
            issues.append(
                f"Too many blank frames: {blank_count}/{sample_count} "
                f"(content in only {has_content_count} frames)"
            )

        if static_count > sample_count * 0.9 and sample_count > 3:
            issues.append(
                f"Video appears mostly static: "
                f"{static_count}/{sample_count} unchanged frames"
            )

        # Check 4: Overlap detection via density analysis on a content-rich frame
        best_frame = self._get_content_rich_frame(video_path, total_frames)
        if best_frame is not None:
            density_issues = self._check_visual_density(best_frame)
            issues.extend(density_issues)

        passed = len(issues) == 0
        return passed, issues

    def _get_content_rich_frame(
        self,
        video_path: str,
        total_frames: int
    ) -> np.ndarray:
        """Find a frame with the most visual content for overlap analysis."""
        cap = cv2.VideoCapture(video_path)

        best_frame = None
        best_content = 0

        # Sample 5 frames from the middle portion
        candidates = np.linspace(
            int(total_frames * 0.3),
            int(total_frames * 0.8),
            5,
            dtype=int
        )

        for idx in candidates:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            content = np.sum(gray > 50)

            if content > best_content:
                best_content = content
                best_frame = frame.copy()

        cap.release()
        return best_frame

    def _check_visual_density(self, frame: np.ndarray) -> List[str]:
        """
        Check if visual elements are too densely packed in any zone.
        High density suggests potential overlap.
        """
        issues = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Define zones matching our layout system
        zones = {
            "title_zone (top 15%)": gray[0:int(h * 0.15), :],
            "equation_zone (15-35%)": gray[int(h * 0.15):int(h * 0.35), :],
            "visual_zone (35-70%)": gray[int(h * 0.35):int(h * 0.70), :],
            "label_zone (70-85%)": gray[int(h * 0.70):int(h * 0.85), :],
            "caption_zone (bottom 15%)": gray[int(h * 0.85):, :],
        }

        for zone_name, zone_pixels in zones.items():
            # Use threshold above Manim's dark background (~30)
            _, binary = cv2.threshold(zone_pixels, 50, 255, cv2.THRESH_BINARY)
            density = np.mean(binary) / 255.0

            if density > 0.65:
                issues.append(
                    f"High density in {zone_name}: {density:.0%} — possible overlap"
                )

        return issues

    def vision_verify(
        self,
        video_path: str,
        concept: str,
        script: dict = None
    ) -> Tuple[bool, str, List[str]]:
        """Use Gemini Vision to semantically verify the video content."""
        if not self.client:
            return True, "Vision verification skipped (no client)", []

        frame_paths = self.extract_frames(video_path, num_frames=4)
        if not frame_paths:
            return False, "Could not extract frames", ["No frames extracted"]

        prompt = f"""You are a quality checker for educational animation videos.

The video is supposed to illustrate the concept: "{concept}"

I'm showing you 4 frames from the video (sampled from different points in the video).

Please evaluate:
1. **Relevance**: Do the visuals relate to "{concept}"? (score 1-10)
2. **Overlap**: Are any text or visual elements overlapping or colliding? (yes/no, describe if yes)
3. **Readability**: Is text readable and properly sized? (score 1-10)
4. **Layout**: Are elements well-organized in the vertical frame? (score 1-10)
5. **Completeness**: Does it appear to show a meaningful explanation? (score 1-10)

Return your evaluation as JSON only:
{{
  "relevance": 8,
  "overlap_detected": false,
  "overlap_details": "",
  "readability": 7,
  "layout": 8,
  "completeness": 7,
  "overall_pass": true,
  "issues": [],
  "suggestions": []
}}

Return ONLY valid JSON, no markdown fences, no extra text.
"""

        try:
            from google.genai import types

            parts = [types.Part.from_text(prompt)]
            for fp in frame_paths:
                with open(fp, "rb") as f:
                    image_data = f.read()
                parts.append(
                    types.Part.from_bytes(
                        data=image_data, mime_type="image/png"
                    )
                )

            response = self.client.models.generate_content(
                model=self.model,
                contents=parts
            )

            result_text = response.text.strip()

            # Clean markdown fences if present
            if "```" in result_text:
                match = re.search(
                    r'```(?:json)?\s*\n?(.*?)```',
                    result_text,
                    re.DOTALL
                )
                if match:
                    result_text = match.group(1).strip()

            result = json.loads(result_text)

            overall_pass = result.get("overall_pass", True)
            vis_issues = result.get("issues", [])
            suggestions = result.get("suggestions", [])

            summary = (
                f"Relevance: {result.get('relevance', '?')}/10, "
                f"Readability: {result.get('readability', '?')}/10, "
                f"Layout: {result.get('layout', '?')}/10, "
                f"Overlap: {'YES' if result.get('overlap_detected') else 'No'}"
            )

            if result.get("overlap_detected"):
                detail = result.get("overlap_details", "detected")
                vis_issues.insert(0, f"Overlap detected: {detail}")

            print(f"  👁️  Vision: {summary}")

            if suggestions:
                print(f"  💡 Suggestions:")
                for s in suggestions[:3]:
                    print(f"     - {s}")

            return overall_pass, summary, vis_issues

        except json.JSONDecodeError as e:
            print(f"  ⚠️  Vision response parse error: {e}")
            return True, f"Vision parse error: {e}", []
        except Exception as e:
            print(f"  ⚠️  Vision verification error: {e}")
            return True, f"Vision error: {e}", []

    def full_verify(
        self,
        video_path: str,
        concept: str,
        script: dict = None
    ) -> Tuple[bool, List[str]]:
        """Run all verification steps."""
        all_issues = []

        # Step 1: Basic automated checks
        print("\n  🔍 Running basic video checks...")
        basic_pass, basic_issues = self.basic_checks(video_path)
        all_issues.extend(basic_issues)

        if basic_issues:
            for issue in basic_issues:
                print(f"     ⚠️  {issue}")

        if not basic_pass:
            critical = any(
                "blank" in i.lower() or "cannot open" in i.lower()
                for i in basic_issues
            )
            if critical:
                return False, all_issues

        # Step 2: Vision model verification
        if self.client:
            print("  🔍 Running vision verification...")
            vision_pass, summary, vision_issues = self.vision_verify(
                video_path, concept, script
            )
            all_issues.extend(vision_issues)
            if not vision_pass:
                return False, all_issues

        if not all_issues:
            print("  ✅ All verification checks passed")
        else:
            print(f"  ⚠️  {len(all_issues)} issue(s) noted")

        has_critical = any(
            "overlap detected" in i.lower() or "blank" in i.lower()
            for i in all_issues
        )
        return not has_critical, all_issues