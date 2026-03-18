# prompt_templates/script_prompt.py

SCRIPT_GENERATION_PROMPT = """You are an expert science educator creating a visual explanation script.

Given a concept, create a STRUCTURED SCRIPT for a 30-45 second educational animation.

## OUTPUT FORMAT — Return ONLY valid JSON, no markdown fences, no explanation:

{{
  "title": "Concept Name",
  "subtitle": "A short tagline (max 8 words)",
  "definition": "One sentence plain-English definition",
  "equation": "LaTeX equation if applicable (or null)",
  "sections": [
    {{
      "id": 1,
      "type": "title_intro",
      "duration": 3,
      "visual_description": "Show title and subtitle, then fade to definition",
      "text_on_screen": ["Fourier Series", "Building signals from sine waves"],
      "narration": "Let's explore the Fourier series — a way to build any signal from simple sine waves.",
      "caption": "The Fourier series builds complex signals from sine waves."
    }},
    {{
      "id": 2,
      "type": "equation",
      "duration": 3,
      "visual_description": "Show the core equation with each part highlighted",
      "text_on_screen": [],
      "equation": "f(x) = \\\\sum_{{n=1}}^{{N}} a_n \\\\sin(nx)",
      "narration": "The core idea is this equation — a sum of sine waves with different frequencies.",
      "caption": "It's a sum of sine waves with different frequencies."
    }},
    {{
      "id": 3,
      "type": "visual_demo",
      "duration": 8,
      "visual_description": "Show axes with a target function, then overlay sine wave approximations with increasing N",
      "animation_steps": [
        "Draw coordinate axes",
        "Show N=1 term in blue",
        "Transform to N=3 in green",
        "Transform to N=5 in orange",
        "Transform to N=10 in red"
      ],
      "narration": "Watch as we add more sine waves. With just one term, it's a rough match. But with ten terms, the approximation becomes remarkably close.",
      "caption": "Adding more terms improves the approximation dramatically."
    }},
    {{
      "id": 4,
      "type": "summary",
      "duration": 3,
      "visual_description": "Fade to summary text with key takeaway",
      "text_on_screen": ["More terms = Better approximation!"],
      "narration": "The more terms we add, the better our approximation becomes. That's the power of Fourier series.",
      "caption": "More terms means a better approximation."
    }}
  ],
  "total_duration": 17,
  "color_scheme": {{
    "title": "YELLOW",
    "primary": "BLUE",
    "secondary": "GREEN",
    "highlight": "RED",
    "text": "WHITE"
  }}
}}

## RULES:
1. Keep total duration between 15-40 seconds
2. Maximum 5 sections
3. Each section must have narration text AND a caption
4. Narration should be conversational and clear
5. Captions should be SHORT (max 15 words per caption)
6. Visual descriptions should be specific and actionable
7. For math concepts, ALWAYS include an equation section
8. The visual_demo section is the most important — be very specific about what to animate
9. Return ONLY valid JSON

## CONCEPT TO SCRIPT:
"{concept}"
"""


CODE_FROM_SCRIPT_PROMPT = """You are an expert Manim (Community Edition v0.18+) programmer.

## YOUR TASK
Convert the following animation script into a complete, working Manim Python script.

## THE SCRIPT:
{script_json}

## LAYOUT ZONES (9:16 vertical video, 720x1280, frame ~8 wide x 14.2 tall)

The frame is divided into STRICT ZONES. Objects MUST stay in their zones:
+─────────────────────────+ y = +7.1 (top)
| TITLE ZONE | y: +5.5 to +7.0
| (title, subtitle) |
+─────────────────────────+
| EQUATION ZONE | y: +3.0 to +5.0
| (formulas, math) |
+─────────────────────────+
| |
| VISUAL ZONE | y: -2.0 to +2.5
| (axes, animations) |
| (graphs, diagrams) |
| |
+─────────────────────────+
| LABEL ZONE | y: -2.5 to -4.0
| (N=1, descriptions) |
+─────────────────────────+
| CAPTION ZONE | y: -5.0 to -6.5
| (summary text) |
| DO NOT place visuals|
+─────────────────────────+ y = -7.1 (bottom)

text


## ABSOLUTE RULES:

### Import Rules:
- ONLY: `from manim import *` and `import numpy as np`
- NEVER import scipy, matplotlib, sympy, or anything else

### Class Rules:
- Class MUST be named `ConceptScene` extending `Scene`
- MUST have `construct(self)` method
- NEVER override `__init__`

### API Rules:
| CORRECT | WRONG |
|---------|-------|
| `Create(obj)` | `ShowCreation(obj)` |
| `Write(text)` | `ShowCreation(text)` |
| `FadeIn(obj)` | `FadeInFrom(obj)` |
| `FadeOut(obj)` | `FadeOutAndShift(obj)` |
| `axes.plot(func)` | `axes.get_graph(func)` |
| `MathTex(r"x^2")` | `TexMobject(r"x^2")` |
| `Text("hi", font_size=36)` | `TextMobject("hi")` |

### Lambda / Function Rules:
- NEVER use recursive lambdas
- For sums/series, define helper functions OUTSIDE the class:
```python
def my_func(x, n):
    result = 0
    for i in range(1, n+1):
        result += np.sin(i * x) / i
    return result
Positioning Rules (CRITICAL - prevents overlap):
Title: .move_to(UP * 6) or .to_edge(UP, buff=0.5)
Subtitle: .move_to(UP * 5.2)
Equations: .move_to(UP * 3.8)
Axes center: .move_to(ORIGIN) or .move_to(DOWN * 0.5) with x_length=5.5, y_length=3.5
Labels below axes: .move_to(DOWN * 3)
Summary text: .move_to(DOWN * 5.5)
NEVER let any object go beyond x = +/-3.5
Font Sizes (CRITICAL - prevents overlap):
Title: font_size=42
Subtitle: font_size=28
Equations: font_size=30
Labels: font_size=26
Captions/Summary: font_size=24
Animation Rules:
Maximum 20 self.play() calls
Use self.wait(0.5) to self.wait(1.5) between steps
End with self.wait(2)
Use FadeOut(*self.mobjects) to clear between major sections
Color Constants:
Use ONLY: YELLOW, BLUE, GREEN, RED, ORANGE, PURPLE, WHITE, GREY, TEAL, PINK

OUTPUT:

Return ONLY valid Python code. No markdown fences. No explanations.
The code must be complete and runnable with: manim render scene.py ConceptScene

CRITICAL FINAL CHECK before outputting:

Are all objects within their layout zones?
Are all API calls correct for Manim CE v0.18+?
Are there any recursive lambdas?
Is the class named ConceptScene?
Does it end with self.wait()?
Is font_size set for every Text and MathTex?
"""