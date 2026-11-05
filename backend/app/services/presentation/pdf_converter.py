"""Discover a usable converter and publish only a newly generated PDF."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from app.core.config import settings

PDF_UNAVAILABLE_MESSAGE = 'PDF hozir mavjud emas. PPTX formatini tanlang.'


class PdfUnavailableError(RuntimeError):
    code = 'pdf_unavailable'

    def __init__(self):
        super().__init__(PDF_UNAVAILABLE_MESSAGE)


class PdfConversionError(RuntimeError):
    code = 'pdf_conversion_failed'


def _executable(path):
    try:
        candidate = Path(path).expanduser().resolve()
        return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    except (OSError, ValueError, RuntimeError):
        return None


def libreoffice_binary():
    """An explicit path is authoritative; never spawn a bare PATH command."""
    configured = settings.LIBREOFFICE_PATH.strip()
    if configured:
        return _executable(configured)
    for name in ('libreoffice', 'soffice'):
        candidate = shutil.which(name)
        if candidate and (resolved := _executable(candidate)):
            return resolved
    return None


def _powerpoint_available():
    # Keep the previous Windows Office route without launching Office during
    # public capability checks. Linux/macOS always use LibreOffice.
    if sys.platform != 'win32' or settings.LIBREOFFICE_PATH.strip():
        return False
    try:
        import winreg
        if importlib.util.find_spec('comtypes') is None:
            return False
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'PowerPoint.Application\CLSID'):
            return True
    except (ImportError, OSError, ValueError):
        return False


def pdf_available():
    return bool(libreoffice_binary() or _powerpoint_available())


def _convert_powerpoint(source, target):
    import comtypes.client
    application = deck = None
    try:
        application = comtypes.client.CreateObject('Powerpoint.Application')
        deck = application.Presentations.Open(str(source), WithWindow=False)
        deck.SaveAs(str(target), 32)
    finally:
        if deck is not None:
            deck.Close()
        if application is not None:
            application.Quit()


def _valid_pdf(path):
    if not path.is_file() or path.stat().st_size < 20:
        return False
    with path.open('rb') as file:
        if file.read(5) != b'%PDF-':
            return False
        file.seek(max(0, path.stat().st_size - 1024))
        return b'%%EOF' in file.read()


def convert_pptx_to_pdf(pptx_path: str) -> str:
    source = Path(pptx_path).resolve()
    if not source.is_file():
        raise FileNotFoundError('PPTX fayli topilmadi')
    binary = libreoffice_binary()
    powerpoint = not binary and _powerpoint_available()
    if not binary and not powerpoint:
        raise PdfUnavailableError()
    destination = source.with_suffix('.pdf')
    # A separate output directory prevents a stale PDF beside the source from
    # being mistaken for this conversion's result. Same filesystem permits an
    # atomic final rename. Each conversion also owns a separate Office profile.
    with tempfile.TemporaryDirectory(prefix='.orzu-pdf-', dir=source.parent) as temporary:
        directory = Path(temporary)
        output = directory / destination.name
        if powerpoint:
            try:
                _convert_powerpoint(source, output)
            except Exception:
                raise PdfConversionError('PDF konvertatsiyasi yakunlanmadi') from None
        else:
            profile = directory / 'profile'
            profile.mkdir()
            try:
                result = subprocess.run([
                    binary, f'-env:UserInstallation={profile.as_uri()}', '--headless',
                    '--convert-to', 'pdf', '--outdir', str(directory), str(source),
                ], capture_output=True, timeout=120, check=False)
            except subprocess.TimeoutExpired:
                raise PdfConversionError('PDF konvertatsiyasi uchun kutish vaqti tugadi') from None
            except OSError:
                raise PdfUnavailableError() from None
            if result.returncode:
                raise PdfConversionError('PDF konvertatsiyasi yakunlanmadi')
        if not _valid_pdf(output):
            raise PdfConversionError('Yangi PDF fayli yaratilmadi yoki fayl noto‘g‘ri')
        os.replace(output, destination)
    return str(destination)
