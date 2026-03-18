## 🧠 Detailed Methodology

This project follows a **modular, self-correcting AI pipeline** that transforms a single concept into a fully rendered animated explainer video. Below is a deep dive into how each component works internally.

---

### 🔄 End-to-End Flow

```

User Input → Script JSON → Manim Code → Validation → Rendering
→ Frame Analysis → (Retry Loop if needed)
→ Audio Generation → Caption Sync → Final Composition

````

---

## 1️⃣ Input Processing

- User provides a concept:
  ```bash
  python main.py "Fourier series"
* Input is normalized and passed to the **agent module**
* Optional: interactive mode allows iterative refinement
---

## 2️⃣ Script Generation (LLM - Gemini)

### Goal:

Convert concept → structured explanation

### Output Format:

A strict JSON schema:

```json
{
  "title": "...",
  "sections": [
    {
      "heading": "...",
      "narration": "...",
      "caption": "...",
      "visual_hint": "..."
    }
  ]
}
```

### Key Design Decisions:

* Enforces **chunked explanation** (not long paragraphs)
* Separates:

  * narration (audio)
  * captions (short readable text)
  * visuals (for animation guidance)

### Why JSON?

* Deterministic parsing
* Easy downstream transformation
* Enables validation before rendering

---

## 3️⃣ Code Generation (Script → Manim)

The script is converted into **Manim Python code** using prompt templates.

### Core Responsibilities:

* Map sections → scenes
* Convert math → `MathTex`
* Convert text → `Text`
* Create animations:

  * `Write()`
  * `Create()`
  * `FadeIn()`

---

### 🧱 Layout Enforcement System

A **strict coordinate-based layout system** is embedded in prompts:

| Zone     | Y-Range      | Purpose           |
| -------- | ------------ | ----------------- |
| Title    | +5.5 to +7.0 | Heading           |
| Equation | +3.0 to +5.0 | MathTex           |
| Visual   | -2.0 to +2.5 | Graphs / diagrams |
| Label    | -2.5 to -4.0 | Annotations       |
| Caption  | -5.0 to -6.5 | Subtitles         |

Constraints:

* All elements stay within `x ∈ [-3.5, 3.5]`
* Prevents overlap
* Ensures mobile-friendly layout

---

## 4️⃣ Validation & Auto-Fix Engine

Before rendering, generated code is validated.

### Checks Performed:

* ✅ Syntax errors
* ✅ Missing `Scene` class
* ✅ Invalid imports
* ✅ Deprecated Manim APIs:

  * `ShowCreation → Create`
  * `TextMobject → Text`
  * `get_graph → plot`

---

### 🔧 Auto-Fix Strategy

If issues are found:

1. Error is captured
2. Sent back to LLM with context
3. Code is regenerated/fixed

This creates a **self-healing loop**

---

## 5️⃣ Rendering (Manim Engine)

* Uses **Manim Community Edition**
* Output format: **MP4 (720×1280, 9:16)**

### Rendering Details:

* Each section becomes part of a continuous scene
* Frame rate optimized for smooth playback
* Temporary files stored in `/temp`

---

## 6️⃣ Video Verification System

After rendering, video quality is checked.

### 🧪 OpenCV Checks:

* Blank frames detection
* Static frame detection
* Pixel density per zone (overlap detection)

---

### 👁️ Vision LLM Checks (Optional):

* Content relevance
* Readability
* Layout correctness

---

### 🔁 Retry Mechanism

If verification fails:

* Feedback is sent to LLM
* Code is regenerated
* Pipeline retries (max 3 times)

---

## 7️⃣ Audio Generation (Edge-TTS)

* Converts narration → speech
* Uses **Microsoft Edge Neural Voices**

### Why Edge-TTS?

* Free
* No API key required
* High-quality natural voices

---

### Processing:

* Concatenates narration from all sections
* Generates `.mp3` or `.wav`

---

## 8️⃣ Caption Generation

* Extracts `caption` fields from script
* Converts to **SRT format**

### Timing Strategy:

* Proportional distribution based on:

  * narration length
  * video duration

---

## 9️⃣ Final Composition (FFmpeg)

Combines all assets into final video:

### Inputs:

* Rendered video (Manim)
* Audio (Edge-TTS)
* Captions (SRT)

### Output:

* Final MP4 with:

  * embedded audio
  * burned-in subtitles

---

## 🔁 Self-Healing Pipeline Design

One of the most powerful aspects:

```
Generate → Validate → Render → Verify
            ↑                    ↓
            ←──── Retry ────────
```

* Automatically fixes:

  * code errors
  * visual issues
  * layout problems
* Reduces manual debugging

---

## ⚙️ Configuration Impact

| Variable            | Effect                      |
| ------------------- | --------------------------- |
| ENABLE_VOICE        | Adds narration              |
| ENABLE_CAPTIONS     | Adds subtitles              |
| ENABLE_VISION_CHECK | Enables visual QA           |
| USE_SCRIPT_MODE     | Improves structure          |
| LLM_MODEL           | Controls generation quality |

---

## 🧩 Key Design Principles

* **Modularity** → each stage is independent
* **Determinism** → JSON-based structure
* **Resilience** → auto-fix + retries
* **Scalability** → can swap LLM, renderer, or TTS
* **User Simplicity** → single command execution

---

## 🚀 Summary

This project is not just a script generator — it's a **fully autonomous AI video production system** that:

* Understands concepts
* Designs visuals
* Writes animation code
* Fixes itself
* Produces polished educational videos

---

```
```
