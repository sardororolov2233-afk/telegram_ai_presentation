"""Claude Haiku translates the user's design request into a Seedream prompt."""
import json
import httpx
from app.core.config import settings

SYSTEM_PROMPT = (
    'You prepare professional English visual prompts for Seedream image generation. '
    'Return only a 100–180 word prompt. Preserve brand names, contact details, prices and numbers exactly. '
    'Distinguish visual instructions from requested visible advertising text. Only requested advertising '
    'text may appear in the image. Put each visible text string in quotation marks, with its placement '
    'and typography. Translate advertising prose to the requested language, without changing names or numbers. '
    'Respect the requested composition and style. Do not add products, contact details, prices or claims.'
)


async def enhance_prompt(description: str, format: str, style: str, lang: str = 'uz') -> str:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError('OPENROUTER_API_KEY sozlanmagan')
    request = json.dumps({'description': description, 'format': format, 'style': style,
        'text_language': lang}, ensure_ascii=False)
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}'},
            json={'model': settings.ACADEMIC_MODEL,
                'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': request}],
                'temperature': 0.3, 'max_tokens': 1500})
        response.raise_for_status()
    choice = response.json()['choices'][0]
    prompt = (choice['message'].get('content') or '').strip()
    if not prompt or choice.get('finish_reason') == 'length':
        raise ValueError('Dizayn topshirig‘i bo‘sh yoki tugallanmagan')
    return prompt
