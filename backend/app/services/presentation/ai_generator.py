"""Generate and validate only the prepared subject-template payload."""
import json
import re
import httpx
from app.core.config import settings
from app.services.presentation.subject_templates import (
    AUTHOR_FIELDS, PayloadValidationError, build_subject_schema, load_manifest,
    normalize_payload, representative_image_slots, subject_instructions, validate_payload)


class AIContentGenerator:
    OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
    MODEL = settings.ACADEMIC_MODEL
    JSON_ATTEMPTS = 2
    FIELD_REPAIR_ATTEMPTS = 2

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        if not self.api_key:
            raise RuntimeError('OPENROUTER_API_KEY sozlanmagan')

    async def _request_json(self, client, headers, messages, subject, variant):
        response = await client.post(self.OPENROUTER_API_URL, headers=headers, json={
            'model': self.MODEL, 'max_tokens': 12000, 'temperature': 0.3,
            'messages': messages, 'response_format': {'type': 'json_object'}})
        response.raise_for_status()
        try:
            choice = response.json()['choices'][0]
            finish_reason = choice.get('finish_reason')
            text = choice['message'].get('content')
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise PayloadValidationError([{'code': 'invalid_response'}], subject, variant) from None
        if finish_reason == 'length':
            raise PayloadValidationError([{'code': 'incomplete_json'}], subject, variant)
        if not isinstance(text, str):
            raise PayloadValidationError([{'code': 'invalid_response'}], subject, variant)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text).strip()
        try:
            result = json.loads(text)
        except (ValueError, TypeError):
            raise PayloadValidationError([{'code': 'invalid_json'}], subject, variant) from None
        if not isinstance(result, dict):
            raise PayloadValidationError([{'code': 'json_object_required'}], subject, variant)
        return result

    @staticmethod
    def _failure(issues, subject, variant):
        return PayloadValidationError(list(issues), subject, variant,
            message='Shablon mazmunini tekshirish muvaffaqiyatsiz')

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
        async with httpx.AsyncClient(timeout=240.0) as client:
            for attempt in range(self.JSON_ATTEMPTS):
                try:
                    result = await self._request_json(client, headers, messages, subject, variant)
                    break
                except PayloadValidationError as exc:
                    if attempt + 1 == self.JSON_ATTEMPTS:
                        raise self._failure(exc.issues, subject, variant) from None
                    messages = [{'role': 'user', 'content': prompt}, {'role': 'user', 'content':
                        'The previous response could not be parsed as a complete JSON object. '
                        'Return the complete object with all required fields. Failure codes: '
                        + json.dumps(exc.issues)}]

            for author_key in AUTHOR_FIELDS.intersection(schema):
                result[author_key] = author
            result = normalize_payload(result, subject, variant)
            last_response_issues = ()
            for attempt in range(self.FIELD_REPAIR_ATTEMPTS + 1):
                try:
                    validate_payload(result, subject, variant)
                    break
                except PayloadValidationError as exc:
                    # The exact supplied name is immutable; asking AI to rewrite it cannot fix it.
                    if attempt == self.FIELD_REPAIR_ATTEMPTS or any(
                            issue.get('field') in AUTHOR_FIELDS for issue in exc.issues):
                        raise self._failure((*exc.issues, *last_response_issues), subject, variant) from None
                    fields = [issue['field'] for issue in exc.issues]
                    constraints = {key: schema[key] for key in fields}
                    repair = (
                        'Repair ONLY the invalid fields listed below. Return a JSON object keyed directly '
                        'by these field names, with corrected string values. Do not return the full presentation '
                        'or change fields outside the requested keys. Preserve the author and image_keywords; '
                        'keep any repaired agenda item consistent with its related slides. '
                        'Preserve the topic, meaning and academic substance of each field. Rewrite overlong '
                        'text concisely with complete words; do not cut off words, sentences, or useful content. '
                        'Count every space and punctuation mark and stay below each maximum. '
                        f'Field constraints: {json.dumps(constraints, ensure_ascii=False)}. '
                        f'Validation errors: {json.dumps(exc.issues, ensure_ascii=False)}.')
                    repair_messages = [{'role': 'user', 'content': prompt},
                        {'role': 'assistant', 'content': json.dumps(result, ensure_ascii=False)},
                        {'role': 'user', 'content': repair}]
                    try:
                        patch = await self._request_json(client, headers, repair_messages, subject, variant)
                    except PayloadValidationError as repair_exc:
                        last_response_issues = repair_exc.issues
                        continue
                    last_response_issues = ()
                    # Even a model that returns the entire object may change only requested bad fields.
                    result.update({key: patch[key] for key in fields if key in patch})
                    result = normalize_payload(result, subject, variant)
        keywords = result.pop('image_keywords', [])
        keywords = keywords if isinstance(keywords, list) else []
        slots = representative_image_slots(load_manifest(subject, variant))
        keywords = [str(keywords[i]) if i < len(keywords) and keywords[i] else f'{topic} {subject} educational visual'
            for i in range(len(slots))]
        return result, keywords
