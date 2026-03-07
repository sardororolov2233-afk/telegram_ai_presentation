import asyncio
from ai_generator import AIContentGenerator

async def main():
    generator = AIContentGenerator()
    slides = await generator.generate_slides(
        topic="Sun'iy intellekt kelajagi",
        language="uz",
        slide_count=5,
        style="professional"
    )
    for s in slides:
        print(f"Slide {s.index}: {s.title}")
        print(f"  Bullets: {s.bullets}")

if __name__ == "__main__":
    asyncio.run(main())
