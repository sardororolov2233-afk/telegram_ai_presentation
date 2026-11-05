"""Strict, bounded text repairs use HTTP fixtures; no model requests are made."""
import json

import httpx
import pytest

from app.core.config import settings
from app.services.presentation.ai_generator import AIContentGenerator
from app.services.presentation.subject_templates import (
    PayloadValidationError, load_manifest, normalize_payload, validate_payload)


def payload():
    data = {key: 'Matn' for key in load_manifest('bolalar', 1)['fields']}
    data['muallif'] = 'Model author'
    data['image_keywords'] = ['A classroom', 'Letter cards', 'A reading lesson']
    return data


def model_responses(monkeypatch, *responses):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        text, finish_reason = responses[len(requests) - 1]
        if not isinstance(text, str):
            text = json.dumps(text)
        return httpx.Response(200, json={'choices': [
            {'finish_reason': finish_reason, 'message': {'content': text}}]})

    original = httpx.AsyncClient
    monkeypatch.setattr(settings, 'OPENROUTER_API_KEY', 'test-key')
    monkeypatch.setattr(httpx, 'AsyncClient',
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    return requests


async def generate(author='Ergasheva Sarvinoz'):
    return await AIContentGenerator().generate_template_slides(
        topic='Savod o‘rgatish: ilmiy asoslar va metodlar', author=author,
        language='uz', plan_count=4, subject='bolalar', variant=1)


async def test_repairs_real_overflow_shape_without_regenerating_valid_content(monkeypatch):
    original = payload()
    # The production failure was one body field at 375 characters with a strict 361 limit.
    assert load_manifest('bolalar', 1)['fields']['s16_text_1']['max_chars'] == 361
    original['s16_text_1'] = 'A' * 375
    patch = {'s16_text_1': 'Mazmunni saqlagan ixcham matn.', 'topic': 'Changed',
             'muallif': 'Changed', 'image_keywords': ['Changed']}
    requests = model_responses(monkeypatch, (original, 'stop'), (patch, 'stop'))

    content, keywords = await generate()

    assert len(requests) == 2
    assert content['s16_text_1'] == patch['s16_text_1']
    for key, value in original.items():
        if key not in {'s16_text_1', 'muallif', 'image_keywords'}:
            assert content[key] == value
    assert content['muallif'] == 'Ergasheva Sarvinoz'
    assert keywords == original['image_keywords']
    repair_prompt = requests[1]['messages'][-1]['content']
    assert 'Repair ONLY' in repair_prompt
    assert 's16_text_1' in repair_prompt and '375' in repair_prompt and '361' in repair_prompt
    assert {request['model'] for request in requests} == {settings.ACADEMIC_MODEL}
    validate_payload(content, 'bolalar', 1)


async def test_repairs_only_remaining_fields_and_rejects_new_changes(monkeypatch):
    original = payload()
    original.update(s03_title='Sarlavha juda uzun', s16_text_1='A' * 375)
    first_patch = {'s03_title': 'Kirish'}
    second_patch = {'s16_text_1': 'Amaliyot uchun mazmunli matn.', 's03_title': 'Mutated'}
    requests = model_responses(monkeypatch, (original, 'stop'),
        (first_patch, 'stop'), (second_patch, 'stop'))

    content, _ = await generate()

    assert len(requests) == 3
    assert content['s03_title'] == 'Kirish'
    assert content['s16_text_1'] == second_patch['s16_text_1']
    final_prompt = requests[2]['messages'][-1]['content']
    assert 's03_title' not in final_prompt
    assert 's16_text_1' in final_prompt


async def test_malformed_initial_response_gets_bounded_full_json_retry(monkeypatch):
    requests = model_responses(monkeypatch, ('{"unfinished":', 'stop'), (payload(), 'stop'))

    content, _ = await generate()

    assert len(requests) == 2
    assert content['muallif'] == 'Ergasheva Sarvinoz'
    assert 'complete object with all required fields' in requests[1]['messages'][-1]['content']


@pytest.mark.parametrize('first_response,code', [
    ('{"unfinished":', 'invalid_json'),
    ('[]', 'json_object_required'),
    ('{}', 'incomplete_json'),
])
async def test_invalid_json_failures_are_bounded_and_structured(monkeypatch, first_response, code):
    reason = 'length' if code == 'incomplete_json' else 'stop'
    requests = model_responses(monkeypatch, (first_response, reason), (first_response, reason))

    with pytest.raises(PayloadValidationError) as caught:
        await generate()

    assert len(requests) == 2
    assert caught.value.code == 'presentation_content_invalid'
    assert caught.value.issues == ({'code': code},)


async def test_malformed_patch_does_not_discard_valid_content(monkeypatch):
    original = payload()
    original['s16_text_1'] = 'A' * 375
    requests = model_responses(monkeypatch, (original, 'stop'),
        ('{"broken":', 'stop'), ({'s16_text_1': 'To‘g‘ri matn.'}, 'stop'))

    content, _ = await generate()

    assert len(requests) == 3
    assert content['s16_text_1'] == 'To‘g‘ri matn.'
    assert content['topic'] == original['topic']


async def test_exhausted_repairs_do_not_truncate_or_expose_input(monkeypatch):
    original = payload()
    private_text = 'Private customer content ' * 20
    original['s16_text_1'] = private_text
    requests = model_responses(monkeypatch, (original, 'stop'),
        ({'s16_text_1': private_text}, 'stop'), ({'s16_text_1': private_text}, 'stop'))

    with pytest.raises(PayloadValidationError) as caught:
        await generate(author='Private customer name')

    assert len(requests) == 3
    assert caught.value.issues == ({'field': 's16_text_1', 'code': 'max_chars',
        'actual_chars': len(private_text.strip()), 'max_chars': 361},)
    error = str(caught.value)
    assert 'Private customer' not in error
    assert 'test-key' not in error
    assert 's16_text_1' in error and '361' in error


def test_whitespace_normalization_preserves_text_and_exact_author():
    data = payload()
    data['s16_text_1'] = '  Mazmunli\t matn.  \r\n  Ikkinchi   qator.  '
    data['muallif'] = '  Ergasheva   Sarvinoz  '
    normalized = normalize_payload(data, 'bolalar', 1)
    assert normalized['s16_text_1'] == 'Mazmunli matn.\nIkkinchi qator.'
    assert normalized['muallif'] == data['muallif']
    assert data['s16_text_1'].startswith('  ')
    data['s16_text_1'] = 'A' * 375
    assert normalize_payload(data, 'bolalar', 1)['s16_text_1'] == data['s16_text_1']


def test_validation_retains_author_and_all_body_limits():
    data = payload()
    data['muallif'] = 'A' * 60
    validate_payload(data, 'bolalar', 1)
    data['s16_text_1'] = 'A' * 375
    with pytest.raises(PayloadValidationError) as caught:
        validate_payload(data, 'bolalar', 1)
    assert caught.value.issues[0]['actual_chars'] == 375
    assert caught.value.issues[0]['max_chars'] == 361
