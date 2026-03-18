# agent.py

from google import genai
import re
import os
from prompt_templates.system_prompt import SYSTEM_PROMPT, RETRY_PROMPT
from validator import CodeValidator

class ConceptAgent:
    def __init__(self, api_key: str, max_retries: int = 3):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"
        self.max_retries = max_retries
        self.validator = CodeValidator()
    
    def _call_llm(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text

    def _clean_code(self, raw_response: str) -> str:
        """Extract clean Python code from LLM response."""
        text = raw_response.strip()

        # Remove markdown code blocks if present
        # Handle ```python ... ``` or ``` ... ```
        pattern = r"```(?:python)?\s*\n?(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        # Remove any leading text before 'from manim' or 'import'
        lines = text.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("from manim", "import manim", "import numpy", "def ", "class ")):
                start_idx = i
                break
        

        cleaned = "\n".join(lines[start_idx:])
        
        # Remove any trailing non-code text (after last class/function)
        # Find the last line that has actual code indentation
        code_lines = cleaned.split("\n")
        end_idx = len(code_lines)
        for i in range(len(code_lines) - 1, -1, -1):
            line = code_lines[i].strip()
            if line and not line.startswith("#") and not line.startswith("```"):
                end_idx = i + 1
                break

        cleaned = "\n".join(code_lines[:end_idx])

        return cleaned


    def generate_code(self, concept: str) -> str:
        """Generate Manim code for a concept."""
        prompt = SYSTEM_PROMPT + f'\nConcept: "{concept}"\n'

        print(f"\n🤖 Generating animation code for: {concept}")
        response = self._call_llm(prompt)
        code = self._clean_code(response)

        # Run through validator
        is_valid, issues, fixed_code = self.validator.validate(code)

        if issues:
            print(f"  🔍 Validator found {len(issues)} issue(s):")
            for issue in issues:
                print(f"     - {issue}")

        if fixed_code != code:
            print(f"  🔧 Validator auto-fixed some issues")

        return fixed_code

    def fix_code(self, code: str, error: str) -> str:
        """Ask LLM to fix broken code."""
        prompt = RETRY_PROMPT.format(previous_code=code, error_message=error)

        print(f"\n🔧 Asking LLM to fix error...")
        response = self._call_llm(prompt)
        fixed_code = self._clean_code(response)

        # Validate the fix too
        is_valid, issues, validated_code = self.validator.validate(fixed_code)

        if issues:
            print(f"  🔍 Validator found {len(issues)} issue(s) in fix:")
            for issue in issues:
                print(f"     - {issue}")

        return validated_code

    def generate_with_retries(self, concept: str) -> tuple:
        """Generate code with automatic retry on failure.
        Returns: (code, syntax_ok)
        """
        code = self.generate_code(concept)

        for attempt in range(self.max_retries):
            print(f"\n📝 Attempt {attempt + 1}/{self.max_retries}")

            # Save code to temp file
            temp_path = os.path.join("temp", "temp_scene.py")
            os.makedirs("temp", exist_ok=True)
            with open(temp_path, "w") as f:
                f.write(code)

            # Syntax check
            try:
                compile(code, temp_path, "exec")
                print("  ✅ Syntax check passed")

                # Additional validation
                is_valid, issues, fixed_code = self.validator.validate(code)

                critical_issues = [i for i in issues if 'CRITICAL' in i]
                if critical_issues:
                    error_msg = "; ".join(critical_issues)
                    print(f"  ⚠️  Critical issues found: {error_msg}")
                    if attempt < self.max_retries - 1:
                        code = self.fix_code(code, error_msg)
                        continue
                else:
                    return fixed_code, True

            except SyntaxError as e:
                error_msg = f"SyntaxError: {e.msg} at line {e.lineno}: {e.text}"
                print(f"  ❌ {error_msg}")
                if attempt < self.max_retries - 1:
                    code = self.fix_code(code, error_msg)
                continue

        return code, False