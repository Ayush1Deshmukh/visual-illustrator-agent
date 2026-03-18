# agent.py

import re
import os
import json
from google import genai
from prompt_templates.system_prompt import SYSTEM_PROMPT, RETRY_PROMPT
from prompt_templates.script_prompt import (
    SCRIPT_GENERATION_PROMPT,
    CODE_FROM_SCRIPT_PROMPT,
)
from validator import CodeValidator


class ConceptAgent:
    """
    Two-stage agent:
      Stage 1: Concept → Structured Script (JSON)
      Stage 2: Script  → Manim Code
    With validation, auto-fix, and visual-feedback repair.
    """

    def __init__(self, api_key: str, max_retries: int = 3):
        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("LLM_MODEL")
        self.max_retries = max_retries
        self.validator = CodeValidator()

    # ─── LLM Helpers ────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """Call Gemini and return text response."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        # Handle the thought_signature warning gracefully
        try:
            return response.text
        except Exception:
            # Fallback: concatenate text parts manually
            parts = response.candidates[0].content.parts
            text_parts = [p.text for p in parts if hasattr(p, 'text') and p.text]
            return "\n".join(text_parts)

    def _clean_code(self, raw_response: str) -> str:
        """Extract clean Python code from LLM response."""
        text = raw_response.strip()

        # Remove markdown code blocks
        pattern = r"```(?:python)?\s*\n?(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        # Find start of actual Python code
        lines = text.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith((
                "from manim", "import manim", "import numpy",
                "def ", "class "
            )):
                start_idx = i
                break

        cleaned = "\n".join(lines[start_idx:])

        # Remove trailing non-code text
        code_lines = cleaned.split("\n")
        end_idx = len(code_lines)
        for i in range(len(code_lines) - 1, -1, -1):
            line = code_lines[i].strip()
            if line and not line.startswith("#") and not line.startswith("```"):
                end_idx = i + 1
                break

        return "\n".join(code_lines[:end_idx])

    def _clean_json(self, raw_response: str) -> str:
        """Extract clean JSON from LLM response."""
        text = raw_response.strip()

        # Remove markdown fences
        pattern = r"```(?:json)?\s*\n?(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        # Find outermost JSON object
        start = text.find('{')
        if start == -1:
            return text

        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

        return text[start:]

    # ─── Stage 1: Script Generation ─────────────────────────────

    def generate_script(self, concept: str) -> dict:
        """Generate a structured animation script as JSON."""
        prompt = SCRIPT_GENERATION_PROMPT.format(concept=concept)

        print(f"\n📋 Stage 1: Generating animation script...")
        response = self._call_llm(prompt)
        json_str = self._clean_json(response)

        try:
            script = json.loads(json_str)
            sections = script.get("sections", [])
            total_dur = script.get("total_duration", "?")

            print(f"  ✅ Script: {len(sections)} sections, ~{total_dur}s")
            for s in sections:
                stype = s.get('type', '?')
                sdur = s.get('duration', '?')
                print(f"     [{s.get('id')}] {stype} ({sdur}s)")

            # Save for debugging
            os.makedirs("temp", exist_ok=True)
            with open("temp/script.json", "w") as f:
                json.dump(script, f, indent=2)

            return script

        except json.JSONDecodeError as e:
            print(f"  ⚠️  Script JSON parse error: {e}")
            print(f"  📝 Raw (first 300 chars): {json_str[:300]}")
            return self._fallback_script(concept)

    def _fallback_script(self, concept: str) -> dict:
        """Minimal fallback script when JSON parsing fails."""
        return {
            "title": concept,
            "subtitle": f"Understanding {concept}",
            "definition": f"An overview of {concept}.",
            "equation": None,
            "sections": [
                {
                    "id": 1,
                    "type": "title_intro",
                    "duration": 4,
                    "visual_description": "Show title and subtitle",
                    "narration": f"Let's explore {concept}.",
                    "caption": f"Exploring {concept}."
                },
                {
                    "id": 2,
                    "type": "visual_demo",
                    "duration": 12,
                    "visual_description": f"Visual demonstration of {concept}",
                    "narration": f"Here is a visual demonstration of {concept}.",
                    "caption": f"Visual demonstration of {concept}."
                },
                {
                    "id": 3,
                    "type": "summary",
                    "duration": 4,
                    "visual_description": "Summary text",
                    "narration": f"That's {concept} in a nutshell.",
                    "caption": f"Key takeaway about {concept}."
                }
            ],
            "total_duration": 20
        }

    # ─── Stage 2: Code Generation ───────────────────────────────

    def generate_code_from_script(self, script: dict) -> str:
        """Convert structured script into Manim code."""
        script_json = json.dumps(script, indent=2)
        prompt = CODE_FROM_SCRIPT_PROMPT.format(script_json=script_json)

        print(f"\n🎨 Stage 2: Converting script to Manim code...")
        response = self._call_llm(prompt)
        code = self._clean_code(response)

        # Validate and auto-fix
        is_valid, issues, fixed_code = self.validator.validate(code)

        if issues:
            # Deduplicate
            unique = list(dict.fromkeys(issues))
            print(f"  🔍 Validator: {len(unique)} issue(s)")
            for issue in unique[:7]:
                print(f"     - {issue}")

        return fixed_code

    def generate_code(self, concept: str) -> str:
        """Direct code generation (fallback when script mode fails)."""
        prompt = SYSTEM_PROMPT + f'\nConcept: "{concept}"\n'

        print(f"\n🤖 Direct code generation for: {concept}")
        response = self._call_llm(prompt)
        code = self._clean_code(response)

        _, issues, fixed_code = self.validator.validate(code)
        if issues:
            print(f"  🔍 Validator: {len(issues)} issue(s)")
            for issue in issues[:5]:
                print(f"     - {issue}")

        return fixed_code

    # ─── Error Repair ───────────────────────────────────────────

    def fix_code(self, code: str, error: str) -> str:
        """Fix code based on a render error."""
        prompt = RETRY_PROMPT.format(
            previous_code=code,
            error_message=error
        )

        print(f"\n🔧 Asking LLM to fix render error...")
        print(f"   Error summary: {error[:150]}...")
        response = self._call_llm(prompt)
        fixed_code = self._clean_code(response)

        _, issues, validated = self.validator.validate(fixed_code)
        if issues:
            unique = list(dict.fromkeys(issues))
            print(f"  🔍 Validator: {len(unique)} issue(s) in fix")
            for issue in unique[:3]:
                print(f"     - {issue}")

        return validated

    def fix_code_with_visual_feedback(
        self,
        code: str,
        visual_issues: list,
        render_error: str = ""
    ) -> str:
        """Fix code using visual verification feedback."""
        issues_text = "\n".join(f"- {issue}" for issue in visual_issues)

        error_section = ""
        if render_error:
            error_section = f"\n## Render Error:\n{render_error}\n"

        prompt = f"""The Manim code rendered but has visual quality issues.

## Visual Issues Detected:
{issues_text}
{error_section}
## Current Code:
```python
{code}
Layout Zones (MUST respect to fix overlap):

TITLE ZONE: y = +5.5 to +7.0 (title, subtitle ONLY)
EQUATION ZONE: y = +3.0 to +5.0 (math formulas ONLY)
VISUAL ZONE: y = -2.0 to +2.5 (axes, graphs, main animation)
LABEL ZONE: y = -2.5 to -4.0 (labels like "N=5")
CAPTION ZONE: y = -5.0 to -6.5 (summary text)
Font Sizes:

Title: font_size=42
Subtitle: font_size=28
Equations: font_size=30
Labels: font_size=26
Summary: font_size=24
API Reminders:

Create() not ShowCreation()
axes.plot() not axes.get_graph()
Text() not TextMobject()
MathTex() not TexMobject()
FadeIn() not FadeInFrom()
Scene not MovingCameraScene
Fix Instructions:

Address each visual issue listed above

Ensure NO elements overlap — keep objects in their assigned zones

Keep all x-coordinates in [-3.5, 3.5]

Axes: x_length=5.5, y_length=3.5 max

Class must be named ConceptScene

Return ONLY the complete fixed Python code, no markdown, no explanations
"""
        response = self._call_llm(prompt)
        fixed_code = self._clean_code(response)



        _, _, validated = self.validator.validate(fixed_code)
        return validated
    

        # ─── Main Entry Point ───────────────────────────────────────

    def generate_with_retries(
    self,
    concept: str,
    use_script: bool = True
    ) -> tuple:
        """
        Full generation pipeline with retries.
        Returns: (code, syntax_ok, script_dict_or_None)
        """
        script = None

        if use_script:
            try:
                script = self.generate_script(concept)
                code = self.generate_code_from_script(script)
            except Exception as e:
                print(f"  ⚠️  Script mode failed ({e}), falling back to direct")
                code = self.generate_code(concept)
        else:
            code = self.generate_code(concept)

        # Retry loop for syntax validation
        for attempt in range(self.max_retries):
            print(f"\n📝 Syntax check {attempt + 1}/{self.max_retries}")

            os.makedirs("temp", exist_ok=True)
            temp_path = os.path.join("temp", "temp_scene.py")
            with open(temp_path, "w") as f:
                f.write(code)

            try:
                compile(code, temp_path, "exec")
                print("  ✅ Syntax OK")

                is_valid, issues, fixed_code = self.validator.validate(code)
                critical = [i for i in issues if 'CRITICAL' in i]

                if critical:
                    error_msg = "; ".join(critical)
                    print(f"  ⚠️  Critical: {error_msg}")
                    if attempt < self.max_retries - 1:
                        code = self.fix_code(code, error_msg)
                        continue
                else:
                    return fixed_code, True, script

            except SyntaxError as e:
                error_msg = (
                    f"SyntaxError: {e.msg} at line {e.lineno}: "
                    f"{e.text.strip() if e.text else 'unknown'}"
                )
                print(f"  ❌ {error_msg}")
                if attempt < self.max_retries - 1:
                    code = self.fix_code(code, error_msg)
                continue

        return code, False, script