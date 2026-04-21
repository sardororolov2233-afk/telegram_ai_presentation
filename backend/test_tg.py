import asyncio
import os
import sys

from app.core.config import settings
from app.services.presentation.telegram_sender import send_presentation_to_telegram

async def test_telegram():
    pptx_path = "test.pptx"
    # Create dummy pptx file
    with open(pptx_path, "wb") as f:
        f.write(b"dummy pptx content")
    
    # Needs a real telegram id. Let's use an invalid one and we should get 400 Bad Request
    try:
        await send_presentation_to_telegram(
            telegram_id=123456789,
            topic="Test Topic \n with invalid chars \\ / : * ? \" < > |",
            pptx_path=pptx_path,
            slide_count=5
        )
        print("Success without error?")
    except Exception as e:
        print(f"Failed with error: {e}")
    finally:
        os.remove(pptx_path)

if __name__ == "__main__":
    asyncio.run(test_telegram())
