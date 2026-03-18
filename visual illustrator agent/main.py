
# main.py

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

from agent import ConceptAgent
from renderer import ManimRenderer
from verifier import VideoVerifier
from audio_generator import AudioGenerator
from composer import VideoComposer

load_dotenv()


def print_banner(concept: str, flags: dict):
    """Print startup banner."""
    print(f"\n{'='*60}")
    print(f"  🎨 Concept Visualizer POC v2")
    print(f"  📚 Concept: {concept}")
    print(f"{'─'*60}")
    for key, label in [
        ("voice", "🎙️  Voice"),
        ("captions", "📝 Captions"),
        ("vision", "👁️  Vision Check"),
        ("script", "📋 Script Mode"),
    ]:
        status = "ON" if flags[key] else "OFF"
        print(f"  {label}:{'  ' * (15 - len(label))}{status}")
    print(f"{'='*60}")


def print_result(success: bool, paths: dict):
    """Print final result."""
    print(f"\n{'='*60}")
    if success:
        print(f"  ✅ SUCCESS!")
    else:
        print(f"  ❌ FAILED")
    for label, path in paths.items():
        if path:
            print(f"  {label}: {path}")
    print(f"{'='*60}")


def main():
    # ─── Configuration ──────────────────────────────────────────
    API_KEY = os.getenv("GEMINI_API_KEY", "")

    if not API_KEY:
        print("❌ Set GEMINI_API_KEY in .env or environment:")
        print("   export GEMINI_API_KEY='your-key-here'")
        sys.exit(1)

    flags = {
        "voice": os.getenv("ENABLE_VOICE", "true").lower() == "true",
        "captions": os.getenv("ENABLE_CAPTIONS", "true").lower() == "true",
        "vision": os.getenv("ENABLE_VISION_CHECK", "true").lower() == "true",
        "script": os.getenv("USE_SCRIPT_MODE", "true").lower() == "true",
    }

    # ─── Get Concept ────────────────────────────────────────────
    if len(sys.argv) > 1:
        concept = " ".join(sys.argv[1:])
    else:
        concept = input("\n🧠 Enter a scientific/mathematical concept: ").strip()

    if not concept:
        print("❌ No concept provided.")
        sys.exit(1)

    print_banner(concept, flags)

    # ─── Initialize ─────────────────────────────────────────────
    agent = ConceptAgent(api_key=API_KEY, max_retries=3)
    renderer = ManimRenderer()
    verifier = VideoVerifier(api_key=API_KEY if flags["vision"] else None)
    audio_gen = AudioGenerator()
    composer = VideoComposer()

    # ─── Stage 1 & 2: Generate Code ────────────────────────────
    code, syntax_ok, script = agent.generate_with_retries(
        concept, use_script=flags["script"]
    )

    if not syntax_ok:
        print("\n❌ Failed to generate valid code after all retries.")
        with open("temp/failed_scene.py", "w") as f:
            f.write(code)
        print_result(False, {"📄 Last code": "temp/failed_scene.py"})
        sys.exit(1)

    with open("temp/scene.py", "w") as f:
        f.write(code)
    print("\n📄 Code saved to temp/scene.py")

    # ─── Stage 3 & 4: Render with Retries ──────────────────────
    MAX_RENDER_RETRIES = 3
    raw_video_path = None

    for attempt in range(MAX_RENDER_RETRIES):
        print(f"\n{'─'*60}")
        print(f"🎬 Render attempt {attempt + 1}/{MAX_RENDER_RETRIES}")
        print(f"{'─'*60}")

        output_path, success, error = renderer.render(code, concept)

        if success:
            raw_video_path = output_path

            # ─── Stage 5: Verify ────────────────────────────────
            print(f"\n{'─'*60}")
            print(f"🔍 Verification")
            print(f"{'─'*60}")

            verify_pass, verify_issues = verifier.full_verify(
                output_path, concept, script
            )

            if not verify_pass and attempt < MAX_RENDER_RETRIES - 1:
                print(f"\n  🔄 Verification failed, fixing...")
                code = agent.fix_code_with_visual_feedback(
                    code, verify_issues, ""
                )
                with open("temp/scene.py", "w") as f:
                    f.write(code)
                continue
            else:
                if verify_issues:
                    print(f"  ℹ️  Minor issues ({len(verify_issues)}), proceeding")
                break
        else:
            # Print more error context
            print(f"\n   Render error:")
            for line in error.split('\n')[-10:]:
                print(f"   {line}")

            if attempt < MAX_RENDER_RETRIES - 1:
                code = agent.fix_code(code, error)
                with open("temp/scene.py", "w") as f:
                    f.write(code)

    if not raw_video_path:
        print_result(False, {
            "📄 Code": "temp/scene.py",
            "💡 Manual": "manim render temp/scene.py ConceptScene -ql"
        })
        sys.exit(1)

    # ─── Stage 6: Audio ────────────────────────────────────────
    audio_path = None
    if flags["voice"] and script:
        print(f"\n{'─'*60}")
        print(f"🎙️  Audio Generation")
        print(f"{'─'*60}")
        audio_path, vtt_path = audio_gen.generate_narration(script)

    # ─── Stage 7: Captions ─────────────────────────────────────
    srt_path = None
    if flags["captions"] and script:
        print(f"\n{'─'*60}")
        print(f"📝 Caption Generation")
        print(f"{'─'*60}")
        video_duration = renderer.get_video_duration(raw_video_path)
        srt_path = audio_gen.generate_srt_from_script(script, video_duration)

    # ─── Stage 8: Compose ──────────────────────────────────────
    final_video_path = raw_video_path

    if audio_path or srt_path:
        print(f"\n{'─'*60}")
        print(f"🎬 Final Composition")
        print(f"{'─'*60}")

        safe_name = concept.lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')
        safe_name = safe_name[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_output = os.path.join("output", f"{safe_name}_final_{timestamp}.mp4")

        comp_path, comp_ok, comp_err = composer.compose(
            video_path=raw_video_path,
            output_path=final_output,
            audio_path=audio_path,
            srt_path=srt_path,
        )

        if comp_ok:
            final_video_path = comp_path
            print(f"  ✅ Final: {comp_path}")
        else:
            print(f"  ⚠️  Composition issue: {comp_err}")
            print(f"  📹 Using raw video: {raw_video_path}")

    # ─── Done ───────────────────────────────────────────────────
    result_paths = {"📹 Video": final_video_path, "📄 Code": "temp/scene.py"}
    if script:
        result_paths["📋 Script"] = "temp/script.json"
    if srt_path:
        result_paths["📝 Captions"] = srt_path

    print_result(True, result_paths)

    # Open video
    if sys.platform == "darwin":
        os.system(f'open "{final_video_path}"')
    elif sys.platform == "linux":
        os.system(f'xdg-open "{final_video_path}" 2>/dev/null &')
    elif sys.platform == "win32":
        os.startfile(final_video_path)


if __name__ == "__main__":
    main()