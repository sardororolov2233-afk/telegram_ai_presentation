"""Original Orzu prompt loading; Claude Haiku 5.5 only, without aiogram dependencies."""
import asyncio
import logging
import re
from pathlib import Path
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)
ACADEMIC_MODEL = "anthropic/claude-haiku-5.5"

def load_prompt(filename, **kwargs):
    """
    Prompts papkasidan faylni o'qiydi va formatlaydi.
    System Core va Context Rules alohida qaytariladi (system_content sifatida).
    """
    try:
        prompts_dir = Path(__file__).parent / "prompts"

        # Load System Core and Context Rules
        # Check if there's a course-specific system core
        course_system_path = prompts_dir / "course" / "00_system_core.txt"
        general_system_path = prompts_dir / "00_system_core.txt"
        context_rules_path = prompts_dir / "course" / "01_context_rules.txt"
        general_context_path = prompts_dir / "01_context_rules.txt"

        system_content = ""
        context_content = ""

        # Prefer course-specific system core if loading course prompts
        if filename.startswith("course/"):
            if course_system_path.exists():
                with open(course_system_path, "r", encoding="utf-8") as f:
                    system_content = f.read() + "\n\n"
            if context_rules_path.exists():
                with open(context_rules_path, "r", encoding="utf-8") as f:
                    context_content = f.read() + "\n\n"
        else:
            if general_system_path.exists():
                with open(general_system_path, "r", encoding="utf-8") as f:
                    system_content = f.read() + "\n\n"
            if general_context_path.exists():
                with open(general_context_path, "r", encoding="utf-8") as f:
                    context_content = f.read() + "\n\n"

        # Load Main Prompt
        path = prompts_dir / filename
        if not path.exists():
            logger.error(f"Prompt fayli topilmadi: {path}")
            return ""

        with open(path, "r", encoding="utf-8") as f:
            main_content = f.read()

        # Agar kwargs bo'lsa, formatlash
        if kwargs:
            try:
                main_content = main_content.format(**kwargs)
            except KeyError as e:
                logger.error(f"Prompt formatlashda kalit yetishmayapti: {e}")

        # Combine all parts
        final_prompt = f"{system_content}{context_content}TASK:\n{main_content}"
        return final_prompt

    except Exception as e:
        logger.error(f"Prompt yuklashda xatolik ({filename}): {e}")
        return ""

def load_system_prompt():
    """System roleni alohida yuklash (system message uchun)"""
    try:
        prompts_dir = Path(__file__).parent / "prompts"
        course_system_path = prompts_dir / "course" / "00_system_core.txt"
        context_rules_path = prompts_dir / "course" / "01_context_rules.txt"

        system_content = ""
        if course_system_path.exists():
            with open(course_system_path, "r", encoding="utf-8") as f:
                system_content = f.read()
        if context_rules_path.exists():
            with open(context_rules_path, "r", encoding="utf-8") as f:
                system_content += "\n\n" + f.read()

        return system_content
    except Exception as e:
        logger.error(f"System prompt yuklashda xatolik: {e}")
        return ""

def load_raw_prompt(filename, **kwargs):
    """
    Faqat prompt faylini o'qiydi, system core qo'shmasdan.
    Bu system/user role ajratish uchun ishlatiladi.
    """
    try:
        prompts_dir = Path(__file__).parent / "prompts"
        path = prompts_dir / filename
        if not path.exists():
            logger.error(f"Prompt fayli topilmadi: {path}")
            return ""

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if kwargs:
            try:
                content = content.format(**kwargs)
            except KeyError as e:
                logger.error(f"Prompt formatlashda kalit yetishmayapti: {e}")

        return content
    except Exception as e:
        logger.error(f"Raw prompt yuklashda xatolik ({filename}): {e}")
        return ""

async def ask_ai(prompt_text, retries=3, temperature=0.3, max_tokens=16384):
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError('OPENROUTER_API_KEY sozlanmagan')
    if not prompt_text:
        raise ValueError('AI topshirig‘i bo‘sh')
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=240.0) as client:
                response = await client.post('https://openrouter.ai/api/v1/chat/completions',
                    headers={'Authorization': 'Bearer ' + settings.OPENROUTER_API_KEY}, json={
                        'model': ACADEMIC_MODEL, 'messages': [
                            {'role': 'system', 'content': load_system_prompt()},
                            {'role': 'user', 'content': prompt_text}],
                        'temperature': temperature, 'max_tokens': max_tokens})
                response.raise_for_status()
                choice = response.json()['choices'][0]
            content = re.sub(r'<think>.*?</think>', '', choice['message'].get('content') or '', flags=re.S).strip()
            if content and choice.get('finish_reason') != 'length':
                return content
            raise ValueError('AI javobi bo‘sh yoki tugallanmagan')
        except Exception:
            if attempt + 1 == retries:
                raise RuntimeError('Claude Haiku 5.5 javob bermadi') from None
            await asyncio.sleep(2 ** attempt)
