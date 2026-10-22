import hashlib
import uuid
from pathlib import Path
from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, Form, File, UploadFile, Header, HTTPException, Request
from pydantic import BaseModel
from supabase import Client
from app.core.config import settings
from app.core.database import get_db
from app.routes.deps import get_current_user
from app.services.commerce import rpc
from app.services.presentation.subject_templates import canonical_subject, load_manifest, list_subject_templates

router = APIRouter(prefix='/presentations', tags=['Presentations'])


@router.get('/templates')
@router.get('/pro-templates', include_in_schema=False)  # Read-only URL retained for an older Mini App.
async def templates():
    return {'subjects': list_subject_templates()}


class PresentationResponse(BaseModel):
    id: str
    status: str = 'queued'
    telegram_sent: bool = False
    slide_count: int


@router.post('/generate', response_model=PresentationResponse, status_code=202)
async def generate_presentation(
    request: Request,
    topic: str = Form(..., min_length=3, max_length=500),
    author: str = Form('', max_length=150),
    language: Literal['uz', 'ru', 'en'] = Form('uz'),
    subject: str = Form('minimalizm'),
    variant: int = Form(1, ge=1),
    document_format: Literal['ppt', 'pdf'] = Form('ppt'),
    bibliography_text: Optional[str] = Form(None, max_length=10000),
    send_to_telegram: bool = Form(True),
    images: List[UploadFile] = File(default=[]),
    idempotency_key: uuid.UUID = Header(...),
    db: Client = Depends(get_db), user: dict = Depends(get_current_user),
):
    if len(topic.strip()) < 3:
        raise HTTPException(400, 'Mavzuni kamida 3 ta belgi bilan kiriting')
    # Some FastAPI versions treat a missing bool form field as an unchecked checkbox.
    if 'send_to_telegram' not in await request.form():
        send_to_telegram = True
    subject = canonical_subject(subject)
    try:
        manifest = load_manifest(subject, variant)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if len(images) > settings.PRESENTATION_MAX_IMAGES:
        raise HTTPException(400, 'Ko‘pi bilan 3 ta rasm yuklang; qo‘shimcha rasm joylarida ular qayta ishlatiladi')
    uploads = Path(settings.JOB_STORAGE_DIR) / 'uploads'
    uploads.mkdir(parents=True, exist_ok=True)
    paths = []
    hashes = []
    try:
        for image in images:
            if not image.filename:
                continue
            if image.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
                raise HTTPException(400, 'JPEG, PNG yoki WEBP rasmini yuklang')
            data = await image.read(5 * 1024 * 1024 + 1)
            if len(data) > 5 * 1024 * 1024:
                raise HTTPException(400, 'Har bir rasm 5 MB dan kichik bo‘lsin')
            # Validate the actual bytes, not just an attacker-supplied file extension.
            import io
            from PIL import Image
            try:
                with Image.open(io.BytesIO(data)) as picture:
                    if picture.width * picture.height > 20_000_000:
                        raise ValueError('Rasm o‘lchami juda katta')
                    picture.verify()
            except Exception as exc:
                raise HTTPException(400, 'Rasm fayli noto‘g‘ri') from exc
            hashes.append(hashlib.sha256(data).hexdigest())
            path = uploads / f'{uuid.uuid4()}.img'
            path.write_bytes(data)
            paths.append(str(path))
        payload = {'topic': topic.strip(), 'author': author, 'language': language, 'subject': subject,
            'variant': variant, 'document_format': document_format,
            'bibliography_text': bibliography_text, 'bibliography_type': 'user' if bibliography_text else 'none',
            'send_to_telegram': send_to_telegram, 'user_images': paths, 'image_hashes': hashes}
        charge = await rpc(db, 'commerce_enqueue', p_user_id=user['telegram_id'], p_service='presentation',
            p_request_id=str(idempotency_key), p_payload=payload)
    except BaseException:
        for path in paths:
            Path(path).unlink(missing_ok=True)
        raise
    if not charge['created']:
        for path in paths:
            Path(path).unlink(missing_ok=True)
    return PresentationResponse(id=str(idempotency_key), slide_count=manifest['slide_count'],
        status='queued' if charge['status'] == 'reserved' else charge['status'])
