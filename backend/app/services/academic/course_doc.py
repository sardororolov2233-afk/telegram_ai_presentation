import re
from docx import Document
from docx.shared import Pt, Inches, Mm
from docx.oxml import OxmlElement, ns
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from datetime import datetime
from pathlib import Path
import logging
from lxml import etree

logger = logging.getLogger(__name__)



def create_course_word_document(tema: str, sahifa: int, uslub: str, text: str,
                        universitet: str, fakultet: str, muallif: str,
                        kurs_guruh: str, doc_type: str = "KURS ISHI", plan: str = None, user_id: int = None, output_path: str = None) -> str:
    """Word formatida KURS ISHI yaratish (Jadvallar va Maxsus sarlavhalar bilan)"""
    try:
        doc = Document()

        # 1. Hashiyalar: Chap 30mm, O'ng 15mm, Yuqori/Past 20mm
        sections = doc.sections
        for section in sections:
            section.top_margin = Mm(20)
            section.bottom_margin = Mm(20)
            section.left_margin = Mm(30)
            section.right_margin = Mm(15)

        style = doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(14)
        font.bold = False
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.space_before = Pt(0)

        # ---------------------------------------------------------
        # HELPER: Page Numbers
        # ---------------------------------------------------------
        def add_page_number(paragraph):
            """Paragrafga sahifa raqami maydonini qo'shadi"""
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Joriy sahifa raqami (PAGE)
            fldSimple = OxmlElement('w:fldSimple')
            fldSimple.set(ns.qn('w:instr'), 'PAGE')
            paragraph._p.append(fldSimple)

        # ---------------------------------------------------------
        # 1. TITUL VARAQ
        # ---------------------------------------------------------
        def add_titul_para(content, bold=False, size=14, space_after=0):
            p = doc.add_paragraph(content)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            p.paragraph_format.space_after = Pt(space_after)
            for run in p.runs:
                run.font.bold = bold
                run.font.size = Pt(size)
                run.font.name = 'Times New Roman'
            return p

        add_titul_para("O‘ZBEKISTON RESPUBLIKASI", bold=True)
        add_titul_para("OLIY TA’LIM, FAN VA INNOVATSIYALAR VAZIRLIGI", bold=True)

        if universitet and universitet != '-':
            add_titul_para(universitet.upper(), bold=True)
        if fakultet and fakultet != '-':
            add_titul_para(fakultet.upper(), bold=True)

        add_titul_para("“___________________________________” FANIDAN")

        for _ in range(2): doc.add_paragraph()

        add_titul_para(doc_type.upper(), bold=True, size=18)
        add_titul_para(f"MAVZU: “{tema}”", bold=True, size=16)

        for _ in range(3): doc.add_paragraph()

        indent = Inches(3.5)
        p_b = doc.add_paragraph(f"Bajardi: {muallif}")
        p_b.paragraph_format.left_indent = indent

        if kurs_guruh:
            p_g = doc.add_paragraph(f"{kurs_guruh}")
            p_g.paragraph_format.left_indent = indent

        label = "Ilmiy rahbar: "
        p_t = doc.add_paragraph(f"{label} __________________")
        p_t.paragraph_format.left_indent = indent

        for _ in range(2): doc.add_paragraph()
        for _ in range(2): doc.add_paragraph()

        doc.add_page_break()

        # ---------------------------------------------------------
        # 2. MUNDARIJA
        # ---------------------------------------------------------
        if plan:
            p_m = doc.add_paragraph("MUNDARIJA")
            p_m.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p_m.runs:
                run.font.bold = True

            clean_plan = plan.replace('**', '').replace('##', '').strip()
            plan_lines = clean_plan.split('\n')

            for line in plan_lines:
                line = line.strip()
                if not line or line.upper() == 'MUNDARIJA': continue

                if re.search(r'^\d+[\)\.]\s', line) or "Mavzuning " in line:
                    continue

                p = doc.add_paragraph(line)
                p.paragraph_format.line_spacing = 1.5
                for run in p.runs:
                    run.font.name = 'Times New Roman'
                    if "BOB" in line.upper() or line.upper() == "KIRISH" or "XULOSA" in line.upper():
                        run.font.bold = True

            doc.add_page_break()

        # ---------------------------------------------------------
        # 3. ASOSIY MATN
        # ---------------------------------------------------------

        lines = text.split('\n')
        i = 0
        first_content_line = True

        while i < len(lines):
            line = lines[i].strip()

            # --- JADVAL LOGIKASI ---
            if line.startswith('|') and i + 1 < len(lines) and '|' in lines[i+1]:
                table_data = []
                while i < len(lines) and '|' in lines[i]:
                    if '---' not in lines[i]:
                        row = [cell.strip() for cell in lines[i].split('|') if cell.strip()]
                        if row:
                            table_data.append(row)
                    i += 1

                if table_data:
                    try:
                        rows = len(table_data)
                        cols = max(len(row) for row in table_data)
                        table = doc.add_table(rows=rows, cols=cols)
                        table.style = 'Table Grid'

                        for r in range(rows):
                            for c in range(len(table_data[r])):
                                if c < cols:
                                    table.cell(r, c).text = table_data[r][c]
                    except Exception as e:
                        logger.error(f"Error creating table: {e}")
                continue

            if not line:
                i += 1
                continue

            # Clean Markdown
            clean_text = line.replace('**', '').replace('##', '').strip()
            upper_text = clean_text.upper()

            # Identify Headers
            is_header = False
            needs_page_break = False

            clean_upper = re.sub(r'[.:;]$', '', upper_text).strip()

            if clean_upper == 'KIRISH':
                is_header = True
                if not first_content_line:
                    needs_page_break = True

            elif 'BOB' in clean_upper and len(clean_upper) < 100:
                if re.search(r'^\d+[\.\-]\s*BOB', clean_upper) or re.search(r'^[IVX]+\s*BOB', clean_upper) or 'BOB' in clean_upper:
                     is_header = True
                     needs_page_break = True

            elif clean_upper == 'XULOSA':
                is_header = True
                needs_page_break = True

            elif 'FOYDALANILGAN ADABIYOTLAR' in clean_upper or clean_upper == 'ADABIYOTLAR':
                is_header = True
                needs_page_break = True

            if needs_page_break:
                doc.add_page_break()

            if is_header:
                heading = doc.add_paragraph(clean_text)
                heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
                heading.paragraph_format.space_before = Pt(12)
                heading.paragraph_format.space_after = Pt(12)
                for run in heading.runs:
                    run.font.size = Pt(14)
                    run.font.bold = True
                    run.font.name = 'Times New Roman'
            else:
                # --- COURSE WORK SPECIAL FORMATTING ---
                # 1. Check for Subsection headers like "1.1.", "2.3." or "I-BO'LIM" if they appear in text body
                # The user's snippet logic:
                is_subsection = False
                if any(clean_text.startswith(prefix) for prefix in ["I-BO'LIM", "II-BO'LIM", "1.", "2.", "3.", "4."]):
                     # Check if it looks like a header (short length, no end punctuation mostly)
                     if len(clean_text) < 100 and not clean_text.endswith('.'):
                         is_subsection = True

                if is_subsection:
                     p = doc.add_paragraph()
                     run = p.add_run(clean_text)
                     run.bold = True
                     run.font.size = Pt(14)
                     run.font.name = 'Times New Roman'
                else:
                    # Normal Text
                    para = doc.add_paragraph()
                    para_format = para.paragraph_format
                    para_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    para_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
                    para_format.first_line_indent = Inches(0.49)

                    if '**' in line:
                        parts = re.split(r'(\*\*.*?\*\*)', line)
                        for part in parts:
                            if part.startswith('**') and part.endswith('**'):
                                text_part = part.replace('**', '')
                                if text_part:
                                    run = para.add_run(text_part)
                                    run.font.bold = True
                            else:
                                if part:
                                    run = para.add_run(part)
                                    run.font.bold = False

                            if run:
                                run.font.name = 'Times New Roman'
                                run.font.size = Pt(14)
                    else:
                        run = para.add_run(clean_text)
                        run.font.size = Pt(14)
                        run.font.name = 'Times New Roman'
                        run.font.bold = False

            first_content_line = False
            i += 1

        # Sahifa raqamlash (footer)
        section = doc.sections[0]
        footer = section.footer

        if footer.paragraphs:
            p_foot = footer.paragraphs[0]
            # Clear existing content if any
            p_foot.text = ""
        else:
            p_foot = footer.add_paragraph()

        add_page_number(p_foot)

        # Add author info on a new line or keep it clean?
        # User requested specifically: add_page_number(footer_para)
        # We will strictly follow the user's snippet logic which replaces/appends to the paragraph.
        # But we also want to keep the author info if possible, or just replace it as per instruction?
        # The user instruction says:
        # footer_para = footer.paragraphs[0]
        # add_page_number(footer_para)
        # So it appends page number to whatever is there or sets it.
        # My implementation of add_page_number sets alignment and appends runs.
        # If I want to keep "Mavzu | Muallif" maybe I should add it before?
        # User instruction implies this is THE footer.
        # I will replace the old static footer with this dynamic one.

        # p_foot.text = f"{tema} | {muallif}" # Removing this old static footer
        # p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Save
        clean_tema = "".join([c for c in tema if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).strip()
        folder_name = "kurs_ishlari"

        if user_id:
            filepath = Path("documents") / str(user_id) / folder_name
        else:
            filepath = Path(folder_name)

        if output_path:
            filepath = Path(output_path).parent
        filepath.mkdir(parents=True, exist_ok=True)

        filename = f"{folder_name}_{clean_tema[:20]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        full_path = Path(output_path) if output_path else filepath / filename
        doc.save(str(full_path))

        if user_id:
            try:
                info_filename = f"{folder_name}_{clean_tema[:20]}_info.txt"
                info_path = filepath / info_filename
                with open(info_path, "w", encoding="utf-8") as f:
                    f.write(f"Mavzu: {tema}\n")
                    f.write(f"Muallif: {muallif}\n")
                    f.write(f"Turi: {doc_type}\n")
                    f.write(f"Sahifa: {sahifa}\n")
                    f.write(f"Universitet: {universitet}\n")
                    f.write(f"Fakultet: {fakultet}\n")
                    f.write(f"Kurs/Guruh: {kurs_guruh}\n")
                    f.write(f"Uslub: {uslub}\n")
                    f.write(f"Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if plan:
                        f.write(f"\nReja:\n{plan}\n")
            except Exception as e:
                logger.error(f"Error saving metadata info: {e}")

        return str(full_path)

    except Exception as e:
        logger.error(f"❌ Kurs ishi yaratishda xatolik: {str(e)}")
        return None
