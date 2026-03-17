"""
HTML Preview Generator
======================
SlideData ro'yxatidan chiroyli HTML taqdimot yasaydi.
Brauzerda ko'rish va Mini App ichida preview uchun ishlatiladi.
"""

from typing import List

class SlideData:
    """Placeholder SlideData class - replace with actual import once module path is correct"""
    def __init__(self, title: str = "", slide_type: str = "content", bullets: List[str] = None, index: int = 0):
        self.title = title
        self.slide_type = slide_type
        self.bullets = bullets or []
        self.index = index

# Stil mavzulari
THEMES = {
    "professional": {
        "primary": "#1E2761",
        "secondary": "#CADCFC",
        "accent": "#4A90D9",
        "bg": "#0F1729",
        "text": "#FFFFFF",
        "card_bg": "#1a2a4a",
        "font": "Georgia, serif",
    },
    "creative": {
        "primary": "#F96167",
        "secondary": "#F9E795",
        "accent": "#FF6B35",
        "bg": "#2F3C7E",
        "text": "#FFFFFF",
        "card_bg": "#3d4f9e",
        "font": "Trebuchet MS, sans-serif",
    },
    "minimal": {
        "primary": "#36454F",
        "secondary": "#F2F2F2",
        "accent": "#028090",
        "bg": "#FFFFFF",
        "text": "#1a1a1a",
        "card_bg": "#f7f7f7",
        "font": "Calibri, Arial, sans-serif",
    },
}


def _slide_html(slide: SlideData, theme: dict, is_dark: bool) -> str:
    """Bitta slide uchun HTML."""
    bg = theme["bg"] if is_dark else theme["secondary"]
    text_color = "#FFFFFF" if is_dark else "#1a1a1a"
    card_bg = theme["card_bg"] if is_dark else "#FFFFFF"

    bullets_html = "".join(
        f'<li class="bullet">{b}</li>' for b in slide.bullets
    )

    if slide.slide_type == "title":
        return f"""
        <div class="slide title-slide" style="background:{theme['bg']}; color:#fff;">
          <div class="slide-number">01</div>
          <div class="title-content">
            <h1 class="main-title" style="color:{theme['secondary']}">{slide.title}</h1>
            <div class="title-line" style="background:{theme['accent']}"></div>
            {"<p class='subtitle'>" + slide.bullets[0] + "</p>" if slide.bullets else ""}
          </div>
        </div>"""

    elif slide.slide_type == "section":
        return f"""
        <div class="slide section-slide" style="background:{theme['primary']}; color:#fff;">
          <div class="section-number" style="color:{theme['accent']}">{slide.index + 1:02d}</div>
          <h2 class="section-title">{slide.title}</h2>
        </div>"""

    elif slide.slide_type == "conclusion":
        return f"""
        <div class="slide conclusion-slide" style="background:{theme['bg']}; color:#fff;">
          <div class="conclusion-icon">✦</div>
          <h2 class="conclusion-title" style="color:{theme['secondary']}">{slide.title}</h2>
          <ul class="bullet-list conclusion-bullets">
            {bullets_html}
          </ul>
        </div>"""

    else:  # content
        return f"""
        <div class="slide content-slide" style="background:{bg}; color:{text_color};">
          <div class="slide-accent" style="background:{theme['accent']}"></div>
          <div class="slide-inner">
            <div class="slide-header">
              <span class="slide-num" style="color:{theme['accent']}">{slide.index + 1:02d}</span>
              <h2 class="slide-title" style="color:{'#fff' if is_dark else theme['primary']}">{slide.title}</h2>
            </div>
            <div class="content-card" style="background:{card_bg}">
              <ul class="bullet-list">
                {bullets_html}
              </ul>
            </div>
          </div>
        </div>"""


def generate_html_preview(slides: list[SlideData], topic: str, style: str = "professional") -> str:
    """To'liq HTML sahifa — brauzerda va Mini App'da ko'rish uchun."""
    theme = THEMES.get(style, THEMES["professional"])
    is_dark = style != "minimal"

    slides_html = "\n".join(
        _slide_html(slide, theme, is_dark) for slide in slides
    )

    dots_html = "".join(
        f'<span class="dot" onclick="goTo({i})" id="dot-{i}"></span>'
        for i in range(len(slides))
    )

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{topic}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: {theme['font']}; background: #0a0a0a; display:flex; flex-direction:column; align-items:center; min-height:100vh; padding: 20px; }}

  .header {{ color: #fff; text-align:center; margin-bottom: 24px; }}
  .header h1 {{ font-size: 1.4rem; opacity:.8; }}
  .header p {{ font-size:.9rem; opacity:.5; margin-top:6px; }}

  .slideshow {{ width:100%; max-width:900px; position:relative; }}

  .slide {{ 
    display: none; width:100%; aspect-ratio:16/9; border-radius:16px; 
    overflow:hidden; position:relative; padding: 48px; 
    box-shadow: 0 20px 60px rgba(0,0,0,.5);
  }}
  .slide.active {{ display: flex; flex-direction:column; justify-content:center; }}

  /* Title slide */
  .title-slide {{ align-items:center; text-align:center; }}
  .main-title {{ font-size: clamp(1.8rem, 4vw, 3rem); font-weight:700; line-height:1.2; margin-bottom:20px; }}
  .title-line {{ width:80px; height:4px; border-radius:2px; margin:0 auto 24px; }}
  .subtitle {{ font-size:1.2rem; opacity:.75; }}
  .slide-number {{ position:absolute; top:20px; right:28px; font-size:.85rem; opacity:.3; letter-spacing:2px; }}

  /* Section slide */
  .section-slide {{ align-items:center; justify-content:center; text-align:center; }}
  .section-number {{ font-size:5rem; font-weight:900; opacity:.15; position:absolute; top:20px; left:40px; }}
  .section-title {{ font-size:clamp(1.6rem, 3.5vw, 2.4rem); font-weight:700; z-index:1; }}

  /* Content slide */
  .content-slide {{ padding:0; }}
  .slide-accent {{ position:absolute; left:0; top:0; bottom:0; width:6px; }}
  .slide-inner {{ padding: 40px 48px; display:flex; flex-direction:column; height:100%; }}
  .slide-header {{ display:flex; align-items:center; gap:16px; margin-bottom:28px; }}
  .slide-num {{ font-size:1rem; font-weight:700; min-width:28px; }}
  .slide-title {{ font-size:clamp(1.2rem, 2.5vw, 1.8rem); font-weight:700; line-height:1.3; }}
  .content-card {{ flex:1; border-radius:12px; padding:28px 32px; }}

  /* Conclusion */
  .conclusion-slide {{ align-items:center; text-align:center; }}
  .conclusion-icon {{ font-size:3rem; margin-bottom:20px; opacity:.6; }}
  .conclusion-title {{ font-size:clamp(1.5rem, 3vw, 2.2rem); font-weight:700; margin-bottom:28px; }}
  .conclusion-bullets {{ text-align:left; max-width:500px; }}

  /* Bullets */
  .bullet-list {{ list-style:none; display:flex; flex-direction:column; gap:12px; }}
  .bullet {{ font-size:clamp(.9rem, 1.6vw, 1.05rem); line-height:1.5; padding-left:20px; position:relative; opacity:.9; }}
  .bullet::before {{ content:"▸"; position:absolute; left:0; color:{theme['accent']}; }}

  /* Navigation */
  .nav {{ display:flex; justify-content:center; align-items:center; gap:20px; margin-top:24px; }}
  .nav-btn {{ 
    background: {theme['primary']}; color:#fff; border:none; border-radius:50%; 
    width:44px; height:44px; font-size:1.2rem; cursor:pointer; 
    transition:.2s; display:flex; align-items:center; justify-content:center;
  }}
  .nav-btn:hover {{ background:{theme['accent']}; transform:scale(1.1); }}
  .dots {{ display:flex; gap:8px; align-items:center; }}
  .dot {{ width:8px; height:8px; border-radius:50%; background:rgba(255,255,255,.3); cursor:pointer; transition:.2s; }}
  .dot.active {{ background:{theme['accent']}; width:24px; border-radius:4px; }}
  .counter {{ color:rgba(255,255,255,.5); font-size:.9rem; min-width:50px; text-align:center; }}

  /* Download bar */
  .download-bar {{ 
    display:flex; gap:12px; justify-content:center; margin-top:16px; flex-wrap:wrap;
  }}
  .dl-btn {{ 
    padding:10px 24px; border-radius:8px; border:none; cursor:pointer; font-weight:600;
    font-size:.9rem; transition:.2s; text-decoration:none; display:inline-flex; align-items:center; gap:8px;
  }}
  .dl-pptx {{ background:{theme['accent']}; color:#fff; }}
  .dl-pdf {{ background:{theme['primary']}; color:#fff; border:1px solid {theme['accent']}; }}
  .dl-btn:hover {{ transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.3); }}
</style>
</head>
<body>

<div class="header">
  <h1>{topic}</h1>
  <p>{len(slides)} ta slayd</p>
</div>

<div class="slideshow">
  {slides_html}
</div>

<div class="nav">
  <button class="nav-btn" onclick="changeSlide(-1)">‹</button>
  <div class="dots">{dots_html}</div>
  <span class="counter" id="counter">1 / {len(slides)}</span>
  <button class="nav-btn" onclick="changeSlide(1)">›</button>
</div>

<div class="download-bar">
  <a class="dl-btn dl-pptx" id="pptx-link" href="#" download>⬇ PPTX yuklab olish</a>
  <a class="dl-btn dl-pdf" id="pdf-link" href="#" download>⬇ PDF yuklab olish</a>
</div>

<script>
let current = 0;
const slides = document.querySelectorAll('.slide');
const dots = document.querySelectorAll('.dot');
const counter = document.getElementById('counter');

function show(n) {{
  slides.forEach(s => s.classList.remove('active'));
  dots.forEach(d => d.classList.remove('active'));
  current = (n + slides.length) % slides.length;
  slides[current].classList.add('active');
  dots[current].classList.add('active');
  counter.textContent = (current + 1) + ' / ' + slides.length;
}}

function changeSlide(dir) {{ show(current + dir); }}
function goTo(n) {{ show(n); }}

// Keyboard navigation
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === ' ') changeSlide(1);
  if (e.key === 'ArrowLeft') changeSlide(-1);
}});

// Swipe support
let touchX = 0;
document.addEventListener('touchstart', e => touchX = e.touches[0].clientX);
document.addEventListener('touchend', e => {{
  const diff = touchX - e.changedTouches[0].clientX;
  if (Math.abs(diff) > 50) changeSlide(diff > 0 ? 1 : -1);
}});

// Set download links from URL params
const params = new URLSearchParams(window.location.search);
const pid = params.get('id');
if (pid) {{
  document.getElementById('pptx-link').href = `/api/v1/presentations/download/${{pid}}/pptx`;
  document.getElementById('pdf-link').href = `/api/v1/presentations/download/${{pid}}/pdf`;
}}

show(0);
</script>
</body>
</html>"""


