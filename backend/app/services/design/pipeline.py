"""Claude Haiku prepares a design prompt; Seedream renders up to three variants."""
from pathlib import Path
from app.services.design.prompt_enhancer import enhance_prompt
from app.services.design.image_generator import generate_image_with_seedream, STATIC_DIR


async def run_design_pipeline(description: str, format: str, style: str,
                              lang: str = 'uz', variant_count: int = 3) -> list[str]:
    if not 1 <= variant_count <= 3:
        raise ValueError('Dizayn variantlari soni 1–3 oralig‘ida bo‘lsin')
    prompt = await enhance_prompt(description, format, style, lang)
    filenames = []
    try:
        for index in range(variant_count):
            filenames.append(await generate_image_with_seedream(prompt, format, index))
        return filenames
    except BaseException:
        for filename in filenames:
            (Path(STATIC_DIR) / filename).unlink(missing_ok=True)
        raise
