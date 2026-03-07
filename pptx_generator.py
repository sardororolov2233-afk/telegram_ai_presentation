"""
PPTX Generator
==============
SlideData ro'yxatidan professional PPTX fayl yasaydi.
PptxGenJS (Node.js) ni subprocess orqali chaqiradi.
"""

import json
import asyncio
import os
import tempfile
from pathlib import Path
from app.services.presentation.ai_generator import SlideData

# Rang palitrasi: tema bo'yicha
PALETTES = {
    "professional": {
        "bg_title": "1E2761",
        "bg_content": "F5F7FA",
        "bg_section": "2E3A87",
        "accent": "4A90D9",
        "title_text": "CADCFC",
        "body_text": "1a2a4a",
        "bullet_text": "2d3e6e",
    },
    "creative": {
        "bg_title": "2F3C7E",
        "bg_content": "FFF9F0",
        "bg_section": "F96167",
        "accent": "F9E795",
        "title_text": "F9E795",
        "body_text": "2F3C7E",
        "bullet_text": "3a4a90",
    },
    "minimal": {
        "bg_title": "36454F",
        "bg_content": "FFFFFF",
        "bg_section": "F2F2F2",
        "accent": "028090",
        "title_text": "FFFFFF",
        "body_text": "1a1a1a",
        "bullet_text": "36454F",
    },
}


def _build_pptxgenjs_script(slides: list[SlideData], style: str, output_path: str) -> str:
    """PptxGenJS Node.js skriptini yasaydi."""
    palette = PALETTES.get(style, PALETTES["professional"])
    slides_data = json.dumps([
        {
            "index": s.index,
            "type": s.slide_type,
            "title": s.title,
            "bullets": s.bullets,
            "notes": s.speaker_notes,
        }
        for s in slides
    ], ensure_ascii=False)

    return f"""
const pptxgen = require("pptxgenjs");

const palette = {json.dumps(palette)};
const slidesData = {slides_data};
const outputPath = {json.dumps(output_path)};

let pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI Generated Presentation";

const W = 10, H = 5.625;

slidesData.forEach((sd) => {{
  let slide = pres.addSlide();

  if (sd.type === "title") {{
    // ── Title slide ──────────────────────────────
    slide.background = {{ color: palette.bg_title }};

    // Left accent bar
    slide.addShape(pres.shapes.RECTANGLE, {{
      x: 0, y: 0, w: 0.35, h: H,
      fill: {{ color: palette.accent }}, line: {{ color: palette.accent }}
    }});

    // Main title
    slide.addText(sd.title, {{
      x: 0.7, y: 1.5, w: W - 1.2, h: 1.6,
      fontSize: 40, bold: true, color: palette.title_text,
      fontFace: "Georgia", valign: "middle"
    }});

    // Subtitle / bullet
    if (sd.bullets && sd.bullets[0]) {{
      slide.addText(sd.bullets[0], {{
        x: 0.7, y: 3.3, w: W - 1.4, h: 0.7,
        fontSize: 18, color: "AABBCC", fontFace: "Calibri", italic: true
      }});
    }}

    // Slide number
    slide.addText("01", {{
      x: W - 1.2, y: H - 0.6, w: 1, h: 0.5,
      fontSize: 11, color: "555577", align: "right"
    }});

  }} else if (sd.type === "section") {{
    // ── Section divider ──────────────────────────
    slide.background = {{ color: palette.bg_section }};

    slide.addText(String(sd.index + 1).padStart(2, "0"), {{
      x: 0.5, y: 0.3, w: 2, h: 1.5,
      fontSize: 72, bold: true, color: palette.accent, fontFace: "Georgia",
      transparency: 70
    }});

    slide.addText(sd.title, {{
      x: 0.8, y: 2.0, w: W - 1.6, h: 1.8,
      fontSize: 34, bold: true, color: "FFFFFF", fontFace: "Georgia",
      valign: "middle", align: "center"
    }});

  }} else if (sd.type === "conclusion") {{
    // ── Conclusion slide ─────────────────────────
    slide.background = {{ color: palette.bg_title }};

    slide.addShape(pres.shapes.RECTANGLE, {{
      x: 0, y: H - 0.5, w: W, h: 0.5,
      fill: {{ color: palette.accent }}, line: {{ color: palette.accent }}
    }});

    slide.addText("✦ " + sd.title, {{
      x: 0.7, y: 0.6, w: W - 1.4, h: 1.2,
      fontSize: 32, bold: true, color: palette.title_text, fontFace: "Georgia"
    }});

    if (sd.bullets.length > 0) {{
      const bulletItems = sd.bullets.map((b, i) => ({{
        text: b,
        options: {{ bullet: true, breakLine: i < sd.bullets.length - 1, fontSize: 15, color: "CCDDEE" }}
      }}));
      slide.addText(bulletItems, {{
        x: 0.9, y: 2.0, w: W - 1.8, h: H - 2.6,
        fontFace: "Calibri", valign: "top"
      }});
    }}

  }} else {{
    // ── Content slide ─────────────────────────────
    slide.background = {{ color: palette.bg_content }};

    // Top accent bar
    slide.addShape(pres.shapes.RECTANGLE, {{
      x: 0, y: 0, w: W, h: 0.08,
      fill: {{ color: palette.accent }}, line: {{ color: palette.accent }}
    }});

    // Left accent bar
    slide.addShape(pres.shapes.RECTANGLE, {{
      x: 0, y: 0.08, w: 0.06, h: H - 0.08,
      fill: {{ color: palette.accent }}, line: {{ color: palette.accent }}
    }});

    // Slide number badge
    slide.addShape(pres.shapes.RECTANGLE, {{
      x: 0.18, y: 0.22, w: 0.45, h: 0.37,
      fill: {{ color: palette.accent }}, line: {{ color: palette.accent }},
      shadow: {{ type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.2 }}
    }});
    slide.addText(String(sd.index + 1).padStart(2, "0"), {{
      x: 0.18, y: 0.22, w: 0.45, h: 0.37,
      fontSize: 13, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0
    }});

    // Title
    slide.addText(sd.title, {{
      x: 0.85, y: 0.2, w: W - 1.1, h: 0.7,
      fontSize: 22, bold: true, color: palette.body_text, fontFace: "Georgia",
      valign: "middle"
    }});

    // Divider line
    slide.addShape(pres.shapes.LINE, {{
      x: 0.85, y: 0.98, w: W - 1.2, h: 0,
      line: {{ color: palette.accent, width: 1.5 }}
    }});

    // Content card background
    slide.addShape(pres.shapes.RECTANGLE, {{
      x: 0.75, y: 1.1, w: W - 1.1, h: H - 1.5,
      fill: {{ color: "FFFFFF" }},
      shadow: {{ type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.08 }}
    }});

    // Bullet points
    if (sd.bullets.length > 0) {{
      const bulletItems = sd.bullets.map((b, i) => ({{
        text: b,
        options: {{
          bullet: true,
          breakLine: i < sd.bullets.length - 1,
          fontSize: 15,
          color: palette.bullet_text,
          paraSpaceAfter: 8,
        }}
      }}));
      slide.addText(bulletItems, {{
        x: 0.95, y: 1.25, w: W - 1.5, h: H - 1.8,
        fontFace: "Calibri", valign: "top"
      }});
    }}
  }}

  // Speaker notes
  if (sd.notes) {{
    slide.addNotes(sd.notes);
  }}
}});

pres.writeFile({{ fileName: outputPath }})
  .then(() => {{ console.log("PPTX_OK:" + outputPath); }})
  .catch(err => {{ console.error("PPTX_ERROR:" + err.message); process.exit(1); }});
"""


async def generate_pptx(slides: list[SlideData], output_path: str, style: str = "professional") -> str:
    """PPTX fayl yasaydi va yo'lini qaytaradi."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Vaqtinchalik JS fayl
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        script = _build_pptxgenjs_script(slides, style, output_path)
        f.write(script)
        script_path = f.name

    try:
        process = await asyncio.create_subprocess_exec(
            "node", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            raise RuntimeError(f"PPTX generatsiya xatosi: {error_msg}")

        output = stdout.decode().strip()
        if "PPTX_OK:" not in output:
            raise RuntimeError(f"PPTX yaratilmadi. Natija: {output}")

        return output_path

    finally:
        os.unlink(script_path)
