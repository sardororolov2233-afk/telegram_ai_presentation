import asyncio
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.services.design.prompt_enhancer import enhance_prompt
from app.services.design.image_generator import generate_image_with_flux, generate_image_fallback

async def main():
    prompt = "Muhriddin osh markazi uchun reklama banneri barakaloi jum aksiyasi narxlar 20 foiz arzon 33k so'm"
    print("Testing prompt enhancement...")
    enhanced = await enhance_prompt(prompt, "instagram", "photorealistic", "uz")
    print("\nEnhanced prompt:")
    print(enhanced)
    
    print("\nTesting image generation with FLUX.2 Pro...")
    filename = await generate_image_with_flux(enhanced, "instagram", 0)
    print(f"Result filename: {filename}")

if __name__ == "__main__":
    asyncio.run(main())
