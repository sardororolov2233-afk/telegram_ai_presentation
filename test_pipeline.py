import asyncio
import sys
import os

# Project root ni path ga qo'shamiz
sys.path.insert(0, os.path.dirname(__file__))

from app.services.presentation.pipeline import PresentationPipeline

async def test_pipeline():
    pipeline = PresentationPipeline()
    
    # 1. Pipeline orqali to'liq generatsiya (AI + Image Fetching + PPTX)
    print("=== Pipeline Test ===")
    try:
        topic = "Süni intellekt va ta'lim"
        out_path = os.path.join(os.path.expanduser("~"), "presentations_cache")
        os.makedirs(out_path, exist_ok=True)
        
        # Test uchun dummy rasm yaratamiz
        dummy_img = os.path.join(out_path, "dummy_test.jpg")
        if not os.path.exists(dummy_img):
            with open(dummy_img, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9")
        
        result = await pipeline.run(
            topic=topic,
            language="uz",
            slide_count=5, # Tezroq generatsiya bo'lishi uchun 5 ta slayd
            style="creative",
            extra_context="O'quvchilar asosan bolalar",
            telegram_id=None, # botga yubormaymiz
            design_template=2,
            user_images=[dummy_img]
        )
        
        print("\nPipeline natijasi:")
        print(f"Hujjat ID: {result['id']}")
        print(f"Slaydlar soni: {result['slide_count']}")
        
        pptx_file = os.path.join(out_path, f"{result['id']}.pptx")
        
        if os.path.exists(pptx_file):
            size = os.path.getsize(pptx_file)
            print(f"✓ PPTX yaratildi: {pptx_file} ({size // 1024} KB)")
        else:
            print("✗ PPTX fayl topilmadi!")
            
    except Exception as e:
        print(f"\n✗ Xatolik yuz berdi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipeline())
