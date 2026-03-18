# validator.py

import re
import ast
from typing import List, Tuple


class CodeValidator:
    """Validates and auto-fixes generated Manim code before rendering."""

    DEPRECATED_PATTERNS = [
        (r'\bShowCreation\b', 'Use Create() instead of ShowCreation()'),
        (r'\bFadeInFrom\b', 'Use FadeIn() instead of FadeInFrom()'),
        (r'\bFadeOutAndShift\b', 'Use FadeOut() instead of FadeOutAndShift()'),
        (r'\bget_graph\b', 'Use axes.plot() instead of axes.get_graph()'),
        (r'\bGraphScene\b', 'GraphScene is removed. Use Scene with Axes'),
        (r'\bTextMobject\b', 'Use Text() instead of TextMobject()'),
        (r'\bTexMobject\b', 'Use MathTex() instead of TexMobject()'),
        (r'\bself\.setup_axes\b', 'setup_axes removed. Create Axes() manually'),
        (r'import\s+matplotlib', 'Do not import matplotlib'),
        (r'import\s+scipy', 'Do not import scipy'),
        (r'import\s+sympy', 'Do not import sympy'),
    ]

    DEPRECATED_FIXES = {
        r'\bShowCreation\b': 'Create',
        r'\bFadeInFrom\b': 'FadeIn',
        r'\bFadeOutAndShift\b': 'FadeOut',
        r'\bget_graph\b': 'plot',
        r'\bTextMobject\b': 'Text',
        r'\bTexMobject\b': 'MathTex',
    }

    FORBIDDEN_IMPORT_PATTERNS = [
        r'^import\s+(matplotlib|scipy|sympy).*$',
        r'^from\s+(matplotlib|scipy|sympy)\s+import.*$',
        r'^from\s+manim\.utils\s+import.*$',
    ]

    def validate(self, code: str) -> Tuple[bool, List[str], str]:
        """
        Validate and auto-fix the code.
        Returns: (is_valid, list_of_issues, fixed_code)
        """
        issues = []
        fixed_code = code

        # 1. Ensure ConceptScene class exists
        if 'class ConceptScene' not in fixed_code:
            fixed_code = re.sub(
                r'class\s+(\w+)\s*\(\s*Scene\s*\)',
                'class ConceptScene(Scene)',
                fixed_code
            )
            if 'class ConceptScene' not in fixed_code:
                issues.append("CRITICAL: No ConceptScene(Scene) class found")

        # 2. Check for construct method
        if 'def construct(self)' not in fixed_code:
            issues.append("CRITICAL: No construct(self) method found")

        # 3. Ensure manim import
        if 'from manim import' not in fixed_code and 'import manim' not in fixed_code:
            fixed_code = 'from manim import *\nimport numpy as np\n\n' + fixed_code
            issues.append("FIXED: Added missing manim import")

        # 4. Ensure numpy import
        if 'import numpy' not in fixed_code:
            fixed_code = fixed_code.replace(
                'from manim import *',
                'from manim import *\nimport numpy as np',
                1
            )
            issues.append("FIXED: Added missing numpy import")

        # 5. Remove forbidden imports
        for pattern in self.FORBIDDEN_IMPORT_PATTERNS:
            if re.search(pattern, fixed_code, re.MULTILINE):
                fixed_code = re.sub(
                    pattern,
                    '# REMOVED: forbidden import',
                    fixed_code,
                    flags=re.MULTILINE
                )
                issues.append("FIXED: Removed forbidden import")

        # 6. Auto-fix deprecated API calls (do this BEFORE logging)
        for pattern, replacement in self.DEPRECATED_FIXES.items():
            if re.search(pattern, fixed_code):
                fixed_code = re.sub(pattern, replacement, fixed_code)
                issues.append(f"FIXED: Replaced {pattern} → {replacement}")

        # 7. Fix MovingCameraScene / ThreeDScene
        if 'MovingCameraScene' in fixed_code:
            fixed_code = fixed_code.replace('MovingCameraScene', 'Scene')
            issues.append("FIXED: Replaced MovingCameraScene with Scene")

        if 'ThreeDScene' in fixed_code:
            fixed_code = fixed_code.replace('ThreeDScene', 'Scene')
            issues.append("FIXED: Replaced ThreeDScene with Scene")

        # 8. Remove self.camera.frame references (causes errors in basic Scene)
        camera_frame_pattern = r'.*self\.camera\.frame.*\n?'
        if re.search(r'self\.camera\.frame', fixed_code):
            fixed_code = re.sub(camera_frame_pattern, '', fixed_code)
            issues.append("FIXED: Removed self.camera.frame references")

        # 9. Remove self.camera.background_color if present (use config instead)
        if 'self.camera.background_color' in fixed_code:
            fixed_code = re.sub(
                r'.*self\.camera\.background_color.*\n?', '', fixed_code
            )
            issues.append("FIXED: Removed self.camera.background_color")

        # 10. Fix ApplyMethod (deprecated)
        apply_method_pattern = r'ApplyMethod\((\w+)\.(\w+),\s*(.+?)\)'
        if re.search(apply_method_pattern, fixed_code):
            fixed_code = re.sub(
                apply_method_pattern,
                r'\1.animate.\2(\3)',
                fixed_code
            )
            issues.append("FIXED: Replaced ApplyMethod with .animate syntax")

        # 11. Syntax check
        try:
            ast.parse(fixed_code)
        except SyntaxError as e:
            issues.append(f"SYNTAX ERROR: {e.msg} at line {e.lineno}")

        # 12. Ensure final self.wait()
        lines = fixed_code.strip().split('\n')
        last_lines = [l.strip() for l in lines[-5:] if l.strip()]
        has_final_wait = any('self.wait' in l for l in last_lines)

        if not has_final_wait:
            indent = '        '
            for line in lines:
                if 'self.play' in line or 'self.wait' in line:
                    indent = line[:len(line) - len(line.lstrip())]
                    break
            fixed_code = fixed_code.rstrip() + f'\n{indent}self.wait(2)\n'
            issues.append("FIXED: Added final self.wait(2)")

        # 13. Deduplicate numpy imports
        import_lines = fixed_code.split('\n')
        seen_numpy = False
        clean_lines = []
        for line in import_lines:
            if 'import numpy' in line:
                if not seen_numpy:
                    seen_numpy = True
                    clean_lines.append(line)
                # skip duplicate
            else:
                clean_lines.append(line)
        fixed_code = '\n'.join(clean_lines)

        is_valid = not any(
            'CRITICAL' in i or 'SYNTAX ERROR' in i
            for i in issues
        )

        return is_valid, issues, fixed_code