"""Biologiya PPTX shablonini matn va ixtiyoriy rasmlar bilan to'ldirish.
Usage: python fill_template.py template.pptx data.json result.pptx [--images images.json]
Images JSON: {"image_3": "photos/cell.jpg"}. Faqat lokal yo'llar.
"""
from __future__ import annotations
import argparse,copy,io,json,posixpath,re
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as ET
from PIL import Image,ImageOps

NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
TOKEN=re.compile(r'{{([a-zA-Z0-9_]+)}}')
def xml(e):return ET.tostring(e,encoding='UTF-8',xml_declaration=True,standalone=True)

def fill_template(template_path, data, output_path, images=None, strict=True):
    """Return output Path. No network, API calls, or modifications to template.
    Unknown/missing fields fail in strict mode. Images are optional.
    Distinct image relationships prevent a replaced image from changing other slides.
    """
    src,dest=Path(template_path),Path(output_path)
    if src.resolve()==dest.resolve():raise ValueError('Natija uchun boshqa fayl nomini tanlang.')
    data=dict(data);images=images or {}
    if 'muallif' not in data:
        data['muallif']=data.get('ism_sharif',data.get('ism_familya',''))
    with ZipFile(src) as z:parts={n:z.read(n) for n in z.namelist()}
    roots={n:ET.fromstring(b) for n,b in parts.items() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)}
    required=set()
    for root in roots.values():
        for p in root.findall('.//a:p',NS):
            required.update(TOKEN.findall(''.join(p.xpath('./a:r/a:t/text()',namespaces=NS))))
    missing=sorted(k for k in required if k not in data or data[k] is None or not str(data[k]).strip())
    if strict and missing:raise ValueError('Yetishmayotgan matn kalitlari: '+', '.join(missing))
    available_images={}
    for path,root in roots.items():
        for sh in root.xpath('//p:sp|//p:pic',namespaces=NS):
            nv=sh.find('.//p:cNvPr',NS)
            key=TOKEN.fullmatch(nv.get('name','')) if nv is not None else None
            if key and key[1].startswith('image_'):available_images.setdefault(key[1],[]).append((path,sh))
    bad=set(images)-set(available_images)
    if bad:
        if strict:
            raise ValueError('Shablonda yo‘q rasm kalitlari: '+', '.join(sorted(bad)))
        else:
            for k in bad: del images[k]
    for root in roots.values():
        for par in list(root.findall('.//a:p',NS)):
            runs=par.findall('a:r',NS)
            text=''.join(par.xpath('./a:r/a:t/text()',namespaces=NS))
            if not TOKEN.search(text):continue
            replacement=TOKEN.sub(lambda m:str(data[m[1]]) if m[1] in data else m[0],text)
            if strict and TOKEN.search(replacement):raise ValueError('Qiymat ichida almashtirilmagan kalit bor.')
            # Normalize split PowerPoint runs and preserve original paragraph/run styles.
            first=copy.deepcopy(runs[0]) if runs else ET.Element('{'+NS['a']+'}r')
            if first.find('a:t',NS) is None:ET.SubElement(first,'{'+NS['a']+'}t')
            for child in list(par):
                if child.tag!='{'+NS['a']+'}pPr':par.remove(child)
            for j,line in enumerate(replacement.split('\n')):
                if j:ET.SubElement(par,'{'+NS['a']+'}br')
                run=copy.deepcopy(first);run.find('a:t',NS).text=line;par.append(run)
    serial=0
    for key,image_path in images.items():
        ip=Path(image_path)
        if not ip.is_file():raise FileNotFoundError(ip)
        with Image.open(ip) as loaded:photo=ImageOps.exif_transpose(loaded).convert('RGB')
        for path,sh in available_images[key]:
            serial+=1;xf=sh.find('p:spPr/a:xfrm',NS);ext=xf.find('a:ext',NS)
            w,h=int(ext.get('cx')),int(ext.get('cy'))
            scale=1600/max(w,h);size=(max(1,round(w*scale)),max(1,round(h*scale)))
            crop=ImageOps.fit(photo,size,method=Image.Resampling.LANCZOS,centering=(.5,.5));buffer=io.BytesIO();crop.save(buffer,format='PNG')
            part=f'ppt/media/bot_{key}_{serial}.png';parts[part]=buffer.getvalue()
            relpath=posixpath.dirname(path)+'/_rels/'+posixpath.basename(path)+'.rels'
            relroot=ET.fromstring(parts[relpath]) if relpath in parts else ET.Element('{'+REL+'}Relationships')
            taken={r.get('Id') for r in relroot};rid=f'rIdBotImage{serial}'
            while rid in taken:rid+='x'
            ET.SubElement(relroot,'{'+REL+'}Relationship',Id=rid,Type=NS['r']+'/image',Target='../media/'+posixpath.basename(part))
            parts[relpath]=xml(relroot)
            blip=sh.find('.//a:blip',NS);blip.set('{'+NS['r']+'}embed',rid)
            fill=blip.getparent()
            for child in list(fill):
                if child.tag in ['{'+NS['a']+'}srcRect','{'+NS['a']+'}tile','{'+NS['a']+'}stretch']:fill.remove(child)
            stretch=ET.SubElement(fill,'{'+NS['a']+'}stretch');ET.SubElement(stretch,'{'+NS['a']+'}fillRect')
    ct=ET.fromstring(parts['[Content_Types].xml']);ctns=ET.QName(ct).namespace
    if images and not any(v.get('Extension')=='png' for v in ct):ET.SubElement(ct,'{'+ctns+'}Default',Extension='png',ContentType='image/png')
    parts['[Content_Types].xml']=xml(ct)
    for path,root in roots.items():parts[path]=xml(root)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(dest,'w',ZIP_DEFLATED) as z:
        for path,content in parts.items():z.writestr(path,content)
    return dest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('template');p.add_argument('data');p.add_argument('output');p.add_argument('--images');a=p.parse_args()
    data=json.loads(Path(a.data).read_text(encoding='utf-8'))
    images=json.loads(Path(a.images).read_text(encoding='utf-8')) if a.images else None
    if images:
        parent=Path(a.images).resolve().parent
        images={k:str(parent/Path(v)) if not Path(v).is_absolute() else v for k,v in images.items()}
    print(fill_template(a.template,data,a.output,images))
if __name__=='__main__':main()
