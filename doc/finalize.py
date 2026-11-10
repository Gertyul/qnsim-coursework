"""Остаточне збирання записки:
1) node build.js -> kursova_raw.docx;
2) заповнення поля TOC пунктами змісту (спершу з номером-заглушкою), рендер у PDF;
3) пошук сторінки кожного заголовка в PDF, запис справжніх номерів у поле TOC;
4) підрахунок сторінок, рисунків, таблиць для анотації та повторне збирання.
"""
import html
import json
import os
import re
import shutil
import subprocess
import zipfile

D = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(D, "kursova_raw.docx")
OUT = os.path.join(D, "Kursova_B24_poyasnyuvalna_zapyska.docx")
STATS = os.path.join(D, "stats.json")


def sh(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def build(stats):
    with open(STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)
    sh(["node", os.path.join(D, "build.js"), STATS], cwd=D, stdout=subprocess.DEVNULL)


def read_xml(path):
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def write_xml(src, dst, xml):
    tmp = dst + ".tmp"
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename == "word/document.xml":
                data = xml.encode("utf-8")
            zo.writestr(item, data)
    shutil.move(tmp, dst)


def headings(xml):
    """Заголовки рівнів 1-2 після заголовка ЗМІСТ (для додатків - разом з назвою)."""
    paras = re.findall(r"<w:p>(?:(?!</w:p>).)*</w:p>|<w:p [^>]*>(?:(?!</w:p>).)*</w:p>", xml, flags=re.S)
    res, started = [], False
    for i, para in enumerate(paras):
        m = re.search(r'<w:pStyle w:val="Heading([12])"/>', para)
        if not m:
            continue
        text = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para)))
        if text == "ЗМІСТ":
            started = True
            continue
        if not started:
            continue
        search = text
        if text.startswith("ДОДАТОК"):
            nxt = html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", paras[i + 1])))
            text = f"{text}. {nxt}"
        res.append((int(m.group(1)), text, search))
    return res


def toc_xml(items, pages):
    out = []
    for (lvl, text, _), pg in zip(items, pages):
        ind = 0 if lvl == 1 else 280
        out.append(
            f'<w:p><w:pPr><w:pStyle w:val="TOC{lvl}"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9638"/></w:tabs>'
            f'<w:ind w:left="{ind}" w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{html.escape(text)}</w:t></w:r><w:r><w:tab/></w:r>'
            f'<w:r><w:t>{pg}</w:t></w:r></w:p>')
    return out


def inject_toc(xml, items, pages):
    entries = toc_xml(items, pages)
    begin = ('<w:r><w:fldChar w:fldCharType="begin"/><w:instrText xml:space="preserve">'
             'TOC \\o &quot;1-2&quot; \\h \\z \\u</w:instrText><w:fldChar w:fldCharType="separate"/></w:r>')
    end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    # перший пункт містить початок поля, останній - кінець
    entries[0] = entries[0].replace("</w:pPr>", "</w:pPr>" + begin, 1)
    entries[-1] = entries[-1].replace("</w:p>", end + "</w:p>")
    new = "<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val=\"Table of Contents\"/><w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>" + "".join(entries) + "</w:sdtContent></w:sdt>"
    return re.sub(r"<w:sdt><w:sdtPr><w:alias w:val=\"Зміст\"/>.*?</w:sdt>", lambda m: new, xml, count=1, flags=re.S)


def to_pdf(docx):
    sh(["soffice", "--headless", "--convert-to", "pdf", "--outdir", D, docx],
       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return os.path.splitext(docx)[0] + ".pdf"


def page_texts(pdf):
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    out = []
    for i in range(1, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), pdf, "-"], capture_output=True, text=True).stdout
        out.append(re.sub(r"\s+", "", t))
    return out


def find_pages(items, texts):
    toc_page = next(i for i, t in enumerate(texts) if t.startswith("ЗМІСТ") or "ЗМІСТ" in t[:20])
    pages, ptr = [], toc_page + 1
    for _, _, search in items:
        key = re.sub(r"\s+", "", search)[:45]
        k = ptr
        while k < len(texts) and key not in texts[k]:
            k += 1
        if k == len(texts):
            raise RuntimeError(f"не знайдено заголовок {search}")
        pages.append(k + 1)
        ptr = k
    return pages


def assemble(stats):
    build(stats)
    xml = read_xml(RAW)
    items = headings(xml)
    xml0 = inject_toc(xml, items, ["00"] * len(items))
    write_xml(RAW, OUT, xml0)
    texts = page_texts(to_pdf(OUT))
    pages = find_pages(items, texts)
    write_xml(RAW, OUT, inject_toc(xml, items, pages))
    pdf = to_pdf(OUT)
    texts2 = page_texts(pdf)
    assert find_pages(items, texts2) == pages, "нумерація сторінок змінилась після заповнення змісту"
    return xml, len(texts2), pdf


if __name__ == "__main__":
    stats = {"nPages": "__", "nFig": "__", "nTab": "__"}
    xml, n, pdf = assemble(stats)
    full = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
    nfig = len(set(re.findall(r"Рисунок (\d+\.\d+) –", full)))
    ntab = len(set(re.findall(r"Таблиця (\d+(?:\.\d+)?) –", full)))
    stats = {"nPages": n, "nFig": nfig, "nTab": ntab}
    xml, n2, pdf = assemble(stats)
    print("сторінок:", n2, "рисунків:", nfig, "таблиць:", ntab)
    if n2 != n:
        stats["nPages"] = n2
        xml, n3, pdf = assemble(stats)
        print("перезбирання:", n3)
