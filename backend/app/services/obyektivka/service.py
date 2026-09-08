import os
import io
import copy
import uuid
from typing import List, Dict, Any, Optional
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from PIL import Image, ImageDraw, ImageFont

class ObyektivkaService:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_path = os.path.join(current_dir, "namuna", "namuna.docx")
        
        # Static folder for output files
        self.static_dir = os.path.abspath(os.path.join(current_dir, "../../../static/obyektivkalar"))
        os.makedirs(self.static_dir, exist_ok=True)

    def _prepare_photo_bytes(self, photo_bytes: Optional[bytes]) -> bytes:
        """Process and resize photo to 3.5x4.5 standard ratio, or create a clean placeholder."""
        target_size = (350, 450) # 3.5 x 4.5 aspect ratio
        
        if photo_bytes:
            try:
                img = Image.open(io.BytesIO(photo_bytes))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Fit into target_size with cropping or resizing
                img_ratio = img.width / img.height
                target_ratio = target_size[0] / target_size[1]
                
                if img_ratio > target_ratio:
                    # image is wider, crop sides
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    # image is taller, crop top/bottom
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                    
                img = img.resize(target_size, Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG", quality=95)
                return buf.getvalue()
            except Exception as e:
                print(f"[ObyektivkaService] Error processing photo: {e}")

        # If no photo or error, create empty white box with soft border
        img = Image.new('RGB', target_size, color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(1, 1), (target_size[0]-2, target_size[1]-2)], outline=(200, 200, 200), width=2)
        # Add hint text
        draw.text((target_size[0]//2 - 35, target_size[1]//2 - 10), "3.5 x 4.5", fill=(180, 180, 180))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def generate(
        self,
        full_name: str,
        current_position: str,
        birth_date: str = "",
        birth_place: str = "",
        living_address: str = "",
        nationality: str = "O'zbek",
        party: str = "Partiyasiz",
        education_level: str = "Oliy",
        university: str = "",
        education_form: str = "kunduzgi",
        specialty: str = "",
        academic_degree: str = "Yo'q",
        academic_title: str = "Yo'q",
        qualification_level: str = "Yo'q",
        phone: str = "",
        email: str = "",
        languages: Optional[List[str]] = None,
        awards: str = "Yo'q",
        deputy: str = "Yo'q",
        work_history: Optional[List[Dict[str, Any]]] = None,
        relatives: Optional[List[Dict[str, Any]]] = None,
        photo_bytes: Optional[bytes] = None,
    ) -> Dict[str, str]:
        """
        Generate completed .docx document from the namuna template.
        Returns dictionary with local file path and static download URL.
        """
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Namuna docx template not found at: {self.template_path}")

        doc = docx.Document(self.template_path)

        # ── 1. Replace 3x4 Photo ─────────────────────────────────
        try:
            if 'rId8' in doc.part.related_parts:
                processed_img_bytes = self._prepare_photo_bytes(photo_bytes)
                doc.part.related_parts['rId8']._blob = processed_img_bytes
        except Exception as e:
            print(f"[ObyektivkaService] Photo replacement warning: {e}")

        # ── 2. Page 1: Personal and Career Data ───────────────────
        
        # P[2]: Full Name
        if len(doc.paragraphs) > 2:
            p_name = doc.paragraphs[2]
            p_name.text = ""
            r_name = p_name.add_run(full_name.strip())
            r_name.font.name = "Times New Roman"
            r_name.font.size = Pt(14)
            r_name.bold = True
            p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # P[4]: Current Position
        if len(doc.paragraphs) > 4:
            p_pos = doc.paragraphs[4]
            p_pos.text = ""
            r_pos = p_pos.add_run(current_position.strip() or "-")
            r_pos.font.name = "Times New Roman"
            r_pos.font.size = Pt(14)
            r_pos.bold = True

        TAB_COL2 = Pt(210)  # Standard column 2 position for 100% stable alignment

        # P[6]: Header for Birth Date / Place
        if len(doc.paragraphs) > 6:
            p_bhead = doc.paragraphs[6]
            p_bhead.text = ""
            p_bhead.paragraph_format.tab_stops.clear_all()
            p_bhead.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_bh1 = p_bhead.add_run("Tug'ilgan yili:")
            r_bh1.font.name = "Times New Roman"
            r_bh1.font.size = Pt(14)
            r_bh1.bold = True
            r_bht = p_bhead.add_run("\t")
            r_bh2 = p_bhead.add_run("Tug'ilgan joyi:")
            r_bh2.font.name = "Times New Roman"
            r_bh2.font.size = Pt(14)
            r_bh2.bold = True

        # P[7]: Birth Date and Birth Place values
        if len(doc.paragraphs) > 7:
            p_birth = doc.paragraphs[7]
            p_birth.text = ""
            p_birth.paragraph_format.tab_stops.clear_all()
            p_birth.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_bd = p_birth.add_run(birth_date.strip() or "-")
            r_bd.font.name = "Times New Roman"
            r_bd.font.size = Pt(14)
            r_tab1 = p_birth.add_run("\t")
            r_bp = p_birth.add_run(birth_place.strip() or "-")
            r_bp.font.name = "Times New Roman"
            r_bp.font.size = Pt(14)

        # P[8]: Header for Nationality / Party
        if len(doc.paragraphs) > 8:
            p_nhead = doc.paragraphs[8]
            p_nhead.text = ""
            p_nhead.paragraph_format.tab_stops.clear_all()
            p_nhead.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_nh1 = p_nhead.add_run("Millati:")
            r_nh1.font.name = "Times New Roman"
            r_nh1.font.size = Pt(14)
            r_nh1.bold = True
            r_nht = p_nhead.add_run("\t")
            r_nh2 = p_nhead.add_run("Partiyaviyligi:")
            r_nh2.font.name = "Times New Roman"
            r_nh2.font.size = Pt(14)
            r_nh2.bold = True

        # P[9]: Nationality and Party values
        if len(doc.paragraphs) > 9:
            p_nat = doc.paragraphs[9]
            p_nat.text = ""
            p_nat.paragraph_format.tab_stops.clear_all()
            p_nat.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_nat = p_nat.add_run(nationality.strip() or "O'zbek")
            r_nat.font.name = "Times New Roman"
            r_nat.font.size = Pt(14)
            r_tab2 = p_nat.add_run("\t")
            r_party = p_nat.add_run(party.strip() or "Partiyasiz")
            r_party.font.name = "Times New Roman"
            r_party.font.size = Pt(14)

        # P[12]: Header for Education / University
        if len(doc.paragraphs) > 12:
            p_ehead = doc.paragraphs[12]
            p_ehead.text = ""
            p_ehead.paragraph_format.tab_stops.clear_all()
            p_ehead.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_eh1 = p_ehead.add_run("Ma'lumoti:")
            r_eh1.font.name = "Times New Roman"
            r_eh1.font.size = Pt(14)
            r_eh1.bold = True
            r_eht = p_ehead.add_run("\t")
            r_eh2 = p_ehead.add_run("Tamomlagan:")
            r_eh2.font.name = "Times New Roman"
            r_eh2.font.size = Pt(14)
            r_eh2.bold = True

        # P[13]: Education Level and University/Specialty values
        if len(doc.paragraphs) > 13:
            p_edu = doc.paragraphs[13]
            p_edu.text = ""
            p_edu.paragraph_format.tab_stops.clear_all()
            p_edu.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_el = p_edu.add_run(education_level.strip() or "-")
            r_el.font.name = "Times New Roman"
            r_el.font.size = Pt(14)
            r_tab3 = p_edu.add_run("\t")
            
            edu_details = university.strip() or "-"
            if education_level.lower() == 'oliy' and education_form:
                edu_details += f" ({education_form.strip()})"
            if specialty.strip():
                edu_details += f", mutaxassisligi: {specialty.strip()}"
            r_uni = p_edu.add_run(edu_details)
            r_uni.font.name = "Times New Roman"
            r_uni.font.size = Pt(14)

        # P[14]: Header for Academic Degree / Title
        if len(doc.paragraphs) > 14:
            p_dhead = doc.paragraphs[14]
            p_dhead.text = ""
            p_dhead.paragraph_format.tab_stops.clear_all()
            p_dhead.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_dh1 = p_dhead.add_run("Ilmiy darajasi:")
            r_dh1.font.name = "Times New Roman"
            r_dh1.font.size = Pt(14)
            r_dh1.bold = True
            r_dht = p_dhead.add_run("\t")
            r_dh2 = p_dhead.add_run("Ilmiy unvoni:")
            r_dh2.font.name = "Times New Roman"
            r_dh2.font.size = Pt(14)
            r_dh2.bold = True

        # P[15]: Academic Degree and Title values
        if len(doc.paragraphs) > 15:
            p_deg = doc.paragraphs[15]
            p_deg.text = ""
            p_deg.paragraph_format.tab_stops.clear_all()
            p_deg.paragraph_format.tab_stops.add_tab_stop(TAB_COL2)
            r_deg = p_deg.add_run(academic_degree.strip() or "Yo'q")
            r_deg.font.name = "Times New Roman"
            r_deg.font.size = Pt(14)
            r_tab4 = p_deg.add_run("\t")
            r_tit = p_deg.add_run(academic_title.strip() or "Yo'q")
            r_tit.font.name = "Times New Roman"
            r_tit.font.size = Pt(14)

        # P[17]: Foreign Languages
        if len(doc.paragraphs) > 17:
            p_lang = doc.paragraphs[17]
            p_lang.text = ""
            lang_str = ", ".join(languages) if languages else "Yo'q"
            r_lang = p_lang.add_run(lang_str)
            r_lang.font.name = "Times New Roman"
            r_lang.font.size = Pt(14)

        # P[19]: Awards
        if len(doc.paragraphs) > 19:
            p_awd = doc.paragraphs[19]
            p_awd.text = ""
            r_awd = p_awd.add_run(awards.strip() or "yo'q")
            r_awd.font.name = "Times New Roman"
            r_awd.font.size = Pt(14)

        # P[21]: Deputy / Elected Member
        if len(doc.paragraphs) > 21:
            p_dep = doc.paragraphs[21]
            p_dep.text = ""
            r_dep = p_dep.add_run(deputy.strip() or "yo'q")
            r_dep.font.name = "Times New Roman"
            r_dep.font.size = Pt(14)

        # ── 3. Work History Section ──────────────────────────────
        mehnat_idx = -1
        rel_title_idx = -1
        for i, p in enumerate(doc.paragraphs):
            if "MEHNAT FAOLIYATI" in p.text.upper():
                mehnat_idx = i
                break
        
        for i, p in enumerate(doc.paragraphs):
            if "yaqin qarindoshlari haqida" in p.text.lower():
                rel_title_idx = i
                break

        if mehnat_idx != -1 and rel_title_idx != -1 and rel_title_idx > mehnat_idx:
            # Remove old sample work entries between MEHNAT FAOLIYATI and relatives title
            p_to_remove = doc.paragraphs[mehnat_idx + 1 : rel_title_idx]
            for p in p_to_remove:
                p._p.getparent().remove(p._p)

        # Locate the relatives title paragraph again
        rel_title_p = None
        for p in doc.paragraphs:
            if "yaqin qarindoshlari haqida" in p.text.lower():
                rel_title_p = p
                break

        if rel_title_p:
            # Insert empty space after MEHNAT FAOLIYATI
            spacer1 = rel_title_p.insert_paragraph_before()
            spacer1.paragraph_format.space_after = Pt(2)

            # Insert user work history
            if work_history and len(work_history) > 0:
                for item in work_history:
                    period = item.get('period', '').strip()
                    desc = item.get('description', '').strip()
                    if period or desc:
                        wp = rel_title_p.insert_paragraph_before()
                        wp.paragraph_format.space_after = Pt(3)
                        wp.paragraph_format.line_spacing = 1.15
                        r_item = wp.add_run(f"{period} - {desc}" if period and desc else (period or desc))
                        r_item.font.name = "Times New Roman"
                        r_item.font.size = Pt(14)
            else:
                wp = rel_title_p.insert_paragraph_before()
                r_item = wp.add_run("Keltirilmagan")
                r_item.font.name = "Times New Roman"
                r_item.font.size = Pt(14)

            # Insert empty paragraph spacer before next page
            spacer2 = rel_title_p.insert_paragraph_before()
            spacer2.paragraph_format.space_after = Pt(4)

        # ── 4. Page 2: Relatives Title (Preserve Page Break) ────
        if rel_title_p:
            # Check if paragraph has page break
            has_page_break = any('w:br' in r._r.xml for r in rel_title_p.runs)
            rel_title_p.text = ""
            if has_page_break:
                r_br = rel_title_p.add_run()
                r_br.add_break(WD_BREAK.PAGE)

            clean_fn = full_name.strip()
            fn_lower = clean_fn.lower()
            if fn_lower.endswith("o'g'li") or fn_lower.endswith("o‘g‘li"):
                title_prefix = clean_fn[:-5].strip() + " o'g'lining"
            elif fn_lower.endswith("qizi"):
                title_prefix = clean_fn[:-4].strip() + " qizining"
            else:
                title_prefix = clean_fn + "ning"

            r_title = rel_title_p.add_run(f"{title_prefix} yaqin qarindoshlari haqida")
            r_title.font.name = "Times New Roman"
            r_title.font.size = Pt(14)
            r_title.bold = True
            rel_title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # ── 5. Page 2: Relatives Table ───────────────────────────
        if len(doc.tables) > 0:
            table = doc.tables[0]
            if len(table.rows) >= 3:
                # Row 1 is the template row with proper cell spans & formatting
                row_template_xml = copy.deepcopy(table.rows[1]._tr)

                # Delete existing relative sample rows (all rows between header and footer)
                sample_count = len(table.rows) - 2
                for _ in range(sample_count):
                    table._tbl.remove(table.rows[1]._tr)

                # Add user relatives
                if relatives and len(relatives) > 0:
                    for rel in relatives:
                        new_tr = copy.deepcopy(row_template_xml)
                        table.rows[-1]._tr.addprevious(new_tr)
                        new_row = table.rows[-2]
                        cells = new_row.cells

                        def format_cell(cell, text):
                            cell.text = ""
                            p = cell.paragraphs[0]
                            p.paragraph_format.space_after = Pt(2)
                            p.paragraph_format.line_spacing = 1.0
                            run = p.add_run(text.strip())
                            run.font.name = "Times New Roman"
                            run.font.size = Pt(12)

                        format_cell(cells[0], rel.get('relationship', ''))
                        format_cell(cells[1], rel.get('fullName', ''))
                        format_cell(cells[2], rel.get('birthYearPlace', ''))
                        format_cell(cells[3], rel.get('birthYearPlace', ''))
                        format_cell(cells[4], rel.get('workplacePosition', ''))
                        format_cell(cells[5], rel.get('workplacePosition', ''))
                        format_cell(cells[6], rel.get('livingAddress', ''))

                # Update bottom row with contact info
                last_row = table.rows[-1]
                contact_parts = []
                if phone.strip():
                    contact_parts.append(f"Telefon: {phone.strip()}")
                if email.strip():
                    contact_parts.append(f"E-mail: {email.strip()}")
                if living_address.strip():
                    contact_parts.append(f"Manzil: {living_address.strip()}")
                
                contact_line = "   |   ".join(contact_parts) if contact_parts else "Bog'lanish ma'lumotlari kiritilmagan"
                
                for c in last_row.cells:
                    c.text = ""
                p_contact = last_row.cells[0].paragraphs[0]
                r_cnt = p_contact.add_run(contact_line)
                r_cnt.font.name = "Times New Roman"
                r_cnt.font.size = Pt(10.5)
                r_cnt.bold = True

        # ── 6. Save Document ─────────────────────────────────────
        file_id = f"obyektivka_{uuid.uuid4().hex[:10]}"
        safe_fn = "".join(c for c in full_name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_fn = safe_fn.replace(' ', '_') or "malumotnoma"
        filename = f"{safe_fn}_{file_id}.docx"
        output_filepath = os.path.join(self.static_dir, filename)

        doc.save(output_filepath)

        static_url = f"/static/obyektivkalar/{filename}"
        return {
            "id": file_id,
            "filename": filename,
            "file_path": output_filepath,
            "file_url": static_url,
            "docx_url": static_url,
        }
