"""Generate and validate only the prepared subject-template payload."""
import json
import re
import httpx
from app.core.config import settings
from app.services.presentation.subject_templates import (
    build_subject_schema, subject_instructions, validate_payload, load_manifest)


class AIContentGenerator:
    OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
    MODEL = settings.ACADEMIC_MODEL

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        if not self.api_key:
            raise RuntimeError('OPENROUTER_API_KEY sozlanmagan')

    async def generate_template_slides(self, topic, author, language, plan_count,
                                      bibliography_type='none', bibliography_text=None,
                                      subject='minimalizm', variant=1):
        schema = build_subject_schema(subject, variant, topic, author)
        languages = {'uz': 'Uzbek (Latin)', 'ru': 'Russian', 'en': 'English'}
        references = ('Only use the following user-supplied references: ' + json.dumps(bibliography_text)
            if bibliography_text else 'No sources were supplied. Use an honest short label; never invent citations or URLs.')
        prompt = (f'Write academic presentation content in {languages[language]}. Topic: {json.dumps(topic)}. '
            f'Return ONLY a JSON object matching this field schema: {json.dumps(schema, ensure_ascii=False)}. '
            'Respect every maximum character limit; keep each agenda item consistent with its three slides. '
            + references + '\n' + subject_instructions(subject, variant))
        messages = [{'role': 'user', 'content': prompt}]
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}
        result = None
        async with httpx.AsyncClient(timeout=240.0) as client:
            for attempt in range(2):
                response = await client.post(self.OPENROUTER_API_URL, headers=headers, json={
                    'model': self.MODEL, 'max_tokens': 12000, 'temperature': 0.3,
                    'messages': messages, 'response_format': {'type': 'json_object'}})
                response.raise_for_status()
                choice = response.json()['choices'][0]
                text = re.sub(r'<think>.*?</think>', '', choice['message'].get('content') or '', flags=re.S).strip()
                text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text).strip()
                try:
                    if choice.get('finish_reason') == 'length':
                        raise ValueError('AI javobi tugallanmagan')
                    result = json.loads(text)
                    if not isinstance(result, dict):
                        raise ValueError('JSON object kerak')
                    for author_key in ('muallif', 'ism_sharif', 'ism_familya'):
                        if author_key in schema:
                            result[author_key] = author
                    validate_payload(result, subject, variant)
                    break
                except (ValueError, TypeError) as exc:
                    if attempt == 1:
                        raise ValueError('Shablon mazmunini tekshirish muvaffaqiyatsiz') from exc
                    messages += [{'role': 'assistant', 'content': text}, {'role': 'user',
                        'content': f'Correct these field errors and return the complete JSON object: {exc}'}]
        keywords = result.pop('image_keywords', [])
        keywords = keywords if isinstance(keywords, list) else []
        slots = load_manifest(subject, variant)['image_slots'][:settings.PRESENTATION_MAX_IMAGES]
        keywords = [str(keywords[i]) if i < len(keywords) and keywords[i] else f'{topic} {subject} educational visual'
            for i in range(len(slots))]
        return result, keywords
