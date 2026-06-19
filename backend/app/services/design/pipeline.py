"""
Design Pipeline — Butun dizayn yaratish jarayonini boshqaradi.

Oqim:
  1. Groq (Llama 3) → foydalanuvchi promptini ingliz tiliga tarjima + optimallashtirish (BEPUL)
  2. FLUX.2 Klein 4B → optimallashtirilgan prompt asosida 3 ta rasm yaratish (~$0.045)
  3. Telegram → yaratilgan rasmlarni foydalanuvchiga yuborish
  
Jami xarajat: ~580 so'm | Foydalanuvchi to'lovi: 2000 so'm | Foyda: ~1420 so'm
"""
import asyncio
import os
from typing import Optional

from app.services.design.prompt_enhancer import enhance_prompt
from app.services.design.image_generator import (
    generate_image_with_flux,
    generate_image_fallback,
    STATIC_DIR,
)


async def run_design_pipeline(
    description: str,
    format: str,
    style: str,
    lang: str = "uz",
    variant_count: int = 3,
) -> list[str]:
    """
    To'liq dizayn pipeline'ni ishga tushiradi.
    
    Args:
        description: Foydalanuvchining tavsifi (o'zbek/rus/ingliz)
        format: Banner formati (instagram, telegram, story)
        style: Dizayn uslubi (infographic, photorealistic, 3d, minimalism)
        lang: Reklama matni tili (uz, kaa, ru, en)
        variant_count: Nechta variant yaratish (default: 3)
    
    Returns:
        Yaratilgan rasm fayl nomlari ro'yxati (filename)
    """
    
    # ═══════════════════════════════════════════════
    # BOSQICH 1: Prompt optimallashtirish (Groq — BEPUL)
    # ═══════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"[Pipeline] 🚀 Dizayn pipeline boshlandi")
    print(f"[Pipeline] 📝 Tavsif: {description[:100]}...")
    print(f"[Pipeline] 📐 Format: {format} | 🎨 Uslub: {style} | 🌐 Til: {lang}")
    print(f"{'='*60}\n")
    
    print("[Pipeline] 1️⃣  Prompt optimallashtirish (Groq Llama 3)...")
    enhanced_prompt = await enhance_prompt(description, format, style, lang)
    print(f"[Pipeline] ✅ Optimallashtirilgan prompt: {enhanced_prompt[:150]}...")
    
    # ═══════════════════════════════════════════════
    # BOSQICH 2: Rasm generatsiya (FLUX.2 Klein 4B)
    # ═══════════════════════════════════════════════
    print(f"\n[Pipeline] 2️⃣  {variant_count} ta rasm yaratilmoqda (FLUX.2 Klein 4B)...")
    
    filenames: list[str] = []
    
    # Rasmlarni ketma-ket yaratamiz (rate-limit va barqarorlik uchun)
    for i in range(variant_count):
        print(f"[Pipeline]    → Variant #{i + 1}/{variant_count}...")
        
        # FLUX bilan urinish
        filename = await generate_image_with_flux(enhanced_prompt, format, i)
        
        if filename:
            filenames.append(filename)
        else:
            # Fallback: Pollinations
            print(f"[Pipeline]    ⚠️ FLUX ishlamadi, Pollinations fallback ishlatilmoqda...")
            fallback_filename = await generate_image_fallback(enhanced_prompt, format, i)
            if fallback_filename:
                filenames.append(fallback_filename)
            else:
                print(f"[Pipeline]    ❌ Variant #{i + 1} yaratib bo'lmadi!")
        
        # Rate-limit uchun kichik pauza (FLUX ning har bir so'rovi orasida)
        if i < variant_count - 1:
            await asyncio.sleep(1)
    
    # ═══════════════════════════════════════════════
    # NATIJA
    # ═══════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"[Pipeline] 📊 Natija: {len(filenames)}/{variant_count} ta rasm yaratildi")
    for fname in filenames:
        fpath = os.path.join(STATIC_DIR, fname)
        size_kb = os.path.getsize(fpath) / 1024 if os.path.exists(fpath) else 0
        print(f"[Pipeline]    📁 {fname} ({size_kb:.1f} KB)")
    print(f"{'='*60}\n")
    
    return filenames
