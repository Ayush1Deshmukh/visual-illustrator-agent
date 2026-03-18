# validator.py

import re
import ast
from typing import List, Tuple


class CodeValidator:
    """Validates generated Manim code before attempting to render."""

    # Known deprecated/wrong API calls
    DEPRECATED_PATTERNS = [
        (r'\bShowCreation\b', 'Use Create() instead of ShowCreation()'),
        (r'\bFadeInFrom\b', 'Use FadeIn() instead of FadeInFrom()'),
        (r'\bFadeOutAndShift\b', 'Use FadeOut() instead of FadeOutAndShift()'),
        (r'\bget_graph\b', 'Use axes.plot() instead of axes.get_graph()'),
        (r'\bGraphScene\b', 'GraphScene is removed. Use Scene with Axes'),
        (r'\bTextMobject\b', 'Use Text() instead of TextMobject()'),
        (r'\bTexMobject\b', 'Use MathTex() instead of TexMobject()'),
        (r'\bself\.camera\.frame\b', 'Do not use self.camera.frame in basic Scene'),
        (r'\bMovingCameraScene\b', 'Use Scene instead of MovingCameraScene'),
        (r'\bThreeDScene\b', 'Use Scene instead of ThreeDScene'),
        (r'\bself\.setup_axes\b', 'setup_axes is removed. Create Axes() manually'),
        (r'\bplay\(.*ShowCreation', 'Use Create() instead of ShowCreation()'),
        (r'import\s+matplotlib', 'Do not import matplotlib'),
        (r'import\s+scipy', 'Do not import scipy'),
        (r'import\s+sympy', 'Do not import sympy'),
        (r'from\s+manim\.utils', 'Do not import from manim.utils directly'),
    ]

    # Patterns that cause recursion or runtime errors
    DANGEROUS_PATTERNS = [
        (r'lambda.*lambda', 'Nested lambdas detected — can cause issues'),
        (r'always_redraw\(.*axes\.plot', 'always_redraw with axes.plot can cause recursion'),
        (r'def\s+construct.*def\s+construct', 'Multiple construct methods detected'),
    ]

    def validate(self, code: str) -> Tuple[bool, List[str], str]:
        """
        Validate the code.
        Returns: (is_valid, list_of_warnings, fixed_code)
        """
        issues = []
        fixed_code = code

        # 1. Check for ConceptScene class
        if 'class ConceptScene' not in code:
            # Try to fix by renaming
            fixed_code = re.sub(
                r'class\s+(\w+)\s*\(\s*Scene\s*\)',
                'class ConceptScene(Scene)',
                fixed_code
            )
            if 'class ConceptScene' not in fixed_code:
                issues.append("CRITICAL: No ConceptScene class found")

        # 2. Check for construct method
        if 'def construct(self)' not in code:
            issues.append("CRITICAL: No construct(self) method found")

        # 3. Check imports
        if 'from manim import' not in code and 'import manim' not in code:
            fixed_code = 'from manim import *\nimport numpy as np\n\n' + fixed_code
            issues.append("FIXED: Added missing manim import")

        # 4. Check deprecated patterns and auto-fix
        for pattern, message in self.DEPRECATED_PATTERNS:
            if re.search(pattern, fixed_code):
                issues.append(f"DEPRECATED: {message}")
                # Auto-fix common ones
                fixed_code = self._auto_fix_deprecated(fixed_code, pattern, message)

        # 5. Check dangerous patterns
        for pattern, message in self.DANGEROUS_PATTERNS:
            if re.search(pattern, fixed_code, re.DOTALL):
                issues.append(f"WARNING: {message}")

        # 6. Syntax check
        try:
            ast.parse(fixed_code)
        except SyntaxError as e:
            issues.append(f"SYNTAX ERROR: {e.msg} at line {e.lineno}")

        # 7. Check for self.wait at end
        lines = fixed_code.strip().split('\n')
        last_meaningful_lines = [l.strip() for l in lines[-5:] if l.strip()]
        has_final_wait = any('self.wait' in l or 'self.play' in l for l in last_meaningful_lines)
        if not has_final_wait:
            # Add a final wait
            indent = '        '
            fixed_code = fixed_code.rstrip() + f'\n{indent}self.wait(1)\n'

        is_valid = not any('CRITICAL' in i or 'SYNTAX ERROR' in i for i in issues)

        return is_valid, issues, fixed_code

    def _auto_fix_deprecated(self, code: str, pattern: str, message: str) -> str:
        """Auto-fix known deprecated patterns."""
        fixes = {
            r'\bShowCreation\b': 'Create',
            r'\bFadeInFrom\b': 'FadeIn',
            r'\bFadeOutAndShift\b': 'FadeOut',
            r'\bget_graph\b': 'plot',
            r'\bTextMobject\b': 'Text',
            r'\bTexMobject\b': 'MathTex',
        }

        for pat, replacement in fixes.items():
            if re.search(pat, code):
                code = re.sub(pat, replacement, code)

        return code