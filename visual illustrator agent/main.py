# main.py

import os
import sys
from agent import ConceptAgent
from renderer import ManimRenderer
from dotenv import load_dotenv

load_dotenv()



def main():
    # --- Configuration ---
    API_KEY = os.getenv("GEMINI_API_KEY", "")

    if not API_KEY:
        print("❌ Please set your Gemini API key:")
        print("   export GEMINI_API_KEY='your-key-here'")
        sys.exit(1)

    # --- Get user input ---
    if len(sys.argv) > 1:
        concept = " ".join(sys.argv[1:])
    else:
        concept = input("\n🧠 Enter a scientific/mathematical concept: ").strip()

    if not concept:
        print("❌ No concept provided.")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  🎨 Concept Visualizer POC")
    print(f"  📚 Concept: {concept}")
    print(f"{'='*50}")

    # --- Initialize ---
    agent = ConceptAgent(api_key=API_KEY, max_retries=3)
    renderer = ManimRenderer()

    # --- Step 1: Generate code ---
    code, syntax_ok = agent.generate_with_retries(concept)

    if not syntax_ok:
        print("\n❌ Failed to generate syntactically valid code after all retries.")
        save_path = "temp/failed_scene.py"
        with open(save_path, "w") as f:
            f.write(code)
        print(f"   Last attempt saved to: {save_path}")
        sys.exit(1)

    # Save valid code
    with open("temp/scene.py", "w") as f:
        f.write(code)
    print("\n📄 Generated code saved to temp/scene.py")

    # --- Step 2: Render with retries ---
    max_render_retries = 3

    for attempt in range(max_render_retries):
        print(f"\n{'─'*40}")
        print(f"🎬 Render attempt {attempt + 1}/{max_render_retries}")
        print(f"{'─'*40}")

        output_path, success, error = renderer.render(code, concept)

        if success:
            print(f"\n{'='*50}")
            print(f"  ✅ SUCCESS!")
            print(f"  📹 Video: {output_path}")
            print(f"  📄 Code:  temp/scene.py")
            print(f"{'='*50}")

            # Open video on Mac
            os.system(f'open "{output_path}"')
            return

        else:
            print(f"\n   Error details:\n   {error[:300]}")

            if attempt < max_render_retries - 1:
                # Ask LLM to fix
                code = agent.fix_code(code, error)

                # Save fixed code
                with open("temp/scene.py", "w") as f:
                    f.write(code)

    # All retries exhausted
    print(f"\n{'='*50}")
    print(f"  ❌ FAILED after {max_render_retries} render attempts")
    print(f"  📄 Last code: temp/scene.py")
    print(f"  💡 Try: manim render temp/scene.py ConceptScene -ql")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()