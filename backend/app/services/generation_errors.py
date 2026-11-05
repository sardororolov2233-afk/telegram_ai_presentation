"""Stable public generation errors, without provider responses or credentials."""
MESSAGES = {
    'presentation_content_invalid': 'Taqdimot matnini shablonga moslab bo‘lmadi. Qayta urinib ko‘ring.',
    'pdf_unavailable': 'PDF hozir mavjud emas. PPTX formatini tanlang.',
    'pdf_conversion_failed': 'PDF yaratib bo‘lmadi. PPTX formatida qayta urinib ko‘ring.',
    'image_auth_error': 'Rasm xizmati sozlamalarida xato bor. Adminga murojaat qiling.',
    'image_credit_exhausted': 'Rasm xizmati vaqtincha to‘xtagan. Adminga murojaat qiling.',
    'image_rate_limit': 'Rasm xizmati band. Birozdan so‘ng qayta urinib ko‘ring.',
    'image_timeout': 'Rasm yaratish vaqti tugadi. Birozdan so‘ng qayta urinib ko‘ring.',
    'image_network_error': 'Rasm xizmatiga ulanib bo‘lmadi. Birozdan so‘ng qayta urinib ko‘ring.',
    'image_provider_error': 'Rasm xizmati javob bermadi. Birozdan so‘ng qayta urinib ko‘ring.',
    'image_model_unavailable': 'Rasm xizmati vaqtincha mavjud emas. Adminga murojaat qiling.',
    'image_request_error': 'Rasm topshirig‘ini bajarib bo‘lmadi. Adminga murojaat qiling.',
    'image_invalid_response': 'Rasm xizmatidan yaroqli javob olinmadi. Qayta urinib ko‘ring.',
    'image_invalid_data': 'Yaratilgan rasmni o‘qib bo‘lmadi. Qayta urinib ko‘ring.',
    'image_storage_error': 'Rasmni saqlab bo‘lmadi. Adminga murojaat qiling.',
    'generation_failed': 'Ishni tayyorlash yakunlanmadi. Qayta urinib ko‘ring.',
}


def error_code(error):
    code = getattr(error, 'code', None)
    if isinstance(code, str) and code in MESSAGES:
        return code
    text = str(error or '')
    prefix = text.split(':', 1)[0]
    if prefix in MESSAGES:
        return prefix
    # Existing jobs predate structured errors; retain useful diagnostics for them.
    if 'Shablon mazmunini tekshirish' in text or 'Shablon ma’lumotlari mos emas' in text:
        return 'presentation_content_invalid'
    if 'libreoffice' in text.lower() and ('Permission denied' in text or 'No such file' in text):
        return 'pdf_unavailable'
    if 'PDF konvertatsiyasi' in text:
        return 'pdf_conversion_failed'
    if 'Taqdimot rasmlarini yaratib bo‘lmadi' in text:
        return 'image_provider_error'
    return 'generation_failed'


def persisted_error(error):
    code = error_code(error)
    return f'{code}: {MESSAGES[code]}'


def public_error(error):
    code = error_code(error)
    return code, MESSAGES[code]
