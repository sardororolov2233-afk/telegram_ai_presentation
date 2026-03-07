import sys, asyncio, traceback, os
sys.path.insert(0, 'backend')

# .env ni qo'lda yuklash
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

async def main():
    try:
        from app.services.presentation.pipeline import PresentationPipeline
        p = PresentationPipeline()

        print("[1] _generate_theme...")
        theme = await p._generate_theme("Qadimgi Rim tarixi", "antik")
        print(f"[1 OK] {theme}")

        print("[2] _generate_slides...")
        slides = await p._generate_slides("Qadimgi Rim tarixi", "uz", 3, "professional", None, "antik")
        print(f"[2 OK] {len(slides)} ta slayd")

        print("[3] run()...")
        result = await p.run(
            topic="Qadimgi Rim tarixi",
            language="uz",
            slide_count=3,
            style="professional",
            extra_context=None,
            telegram_id=None,
            user_prompt="antik"
        )
        print(f"\n✅ OK! id={result['id']}, slide_count={result['slide_count']}")

    except Exception as e:
        print(f"\n❌ XATO: {type(e).__name__}: {e}")
        traceback.print_exc()

asyncio.run(main())
