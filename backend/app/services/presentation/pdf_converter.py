import os
import sys
import subprocess

def convert_pptx_to_pdf(pptx_path: str) -> str:
    """
    Kiritilgan pptx fayli manzilini olib, uni PDF formatiga o'giradi
    va yaratilgan yangi PDF fayli manzilini qaytaradi.
    Windows da MS Office interfeysidan, Linuxda esa LibreOffice dan foydalanadi.
    """
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX fayli topilmadi: {pptx_path}")

    pdf_path = pptx_path.rsplit(".", 1)[0] + ".pdf"

    if sys.platform == "win32":
        try:
            import comtypes.client
            powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
            powerpoint.Visible = 1
            
            # Faylni COM uchun absolute path qilish talab etiladi
            abs_pptx = os.path.abspath(pptx_path)
            abs_pdf = os.path.abspath(pdf_path)
            
            deck = powerpoint.Presentations.Open(abs_pptx)
            # 32 = ppSaveAsPDF format
            deck.SaveAs(abs_pdf, 32)
            deck.Close()
            powerpoint.Quit()
            return pdf_path
        except Exception as e:
            print(f"Windows COM orqali PDF ga aylantirishda xatolik: {e}")
            raise RuntimeError(f"PDF ga aylantirish xatosi (MS Office o'rnatilgan yoki yo'qligini tekshiring): {e}")
    else:
        # Linux / MacOS - LibreOffice required
        out_dir = os.path.dirname(pptx_path)
        try:
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to',
                'pdf',
                pptx_path,
                '--outdir',
                out_dir
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise Exception(result.stderr.decode('utf-8'))
            return pdf_path
        except Exception as e:
            print(f"LibreOffice orqali PDF ga aylantirishda xatolik: {e}")
            raise RuntimeError(f"PDF ga aylantirish xatosi (Linux): LibreOffice o'rnatilmagan bo'lishi mumkin. {e}")
