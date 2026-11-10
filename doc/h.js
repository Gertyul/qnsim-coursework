// Допоміжні функції оформлення пояснювальної записки за ДСТУ 3008:2015
const fs = require("fs");
const path = require("path");
const d = require("docx");
const {
  Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, HeadingLevel, TabStopType, Tab, VerticalAlign, ShadingType,
} = d;

const FONT = "Times New Roman";
const W = 9638;            // ширина текстового поля, DXA (21 см - 2·2 см)
const IND = 709;           // абзацний відступ 1,25 см
const ROOT = path.join(__dirname, "..");

// ---------- розмітка в рядку ----------
// **жирний**, {i:курсив}, _{нижній індекс}, ^{верхній індекс}, `код`
function runs(text, base = {}) {
  if (Array.isArray(text)) return text.flatMap((t) => (typeof t === "string" ? runs(t, base) : [t]));
  const out = [];
  const re = /(\*\*[^*]+\*\*|_\{[^}]*\}|\^\{[^}]*\}|\{i:[^}]*\}|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const s = m[0];
    if (s.startsWith("**")) out.push(new TextRun({ text: s.slice(2, -2), bold: true, ...base }));
    else if (s.startsWith("_{")) out.push(new TextRun({ text: s.slice(2, -1), subScript: true, ...base }));
    else if (s.startsWith("^{")) out.push(new TextRun({ text: s.slice(2, -1), superScript: true, ...base }));
    else if (s.startsWith("{i:")) out.push(new TextRun({ text: s.slice(3, -1), italics: true, ...base }));
    else out.push(new TextRun({ text: s.slice(1, -1), font: "Courier New", ...base }));
    last = m.index + s.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

// ---------- абзаци ----------
const p = (text, opt = {}) => new Paragraph({ children: runs(text), ...opt });
const pc = (text, opt = {}) => new Paragraph({ children: runs(text), alignment: AlignmentType.CENTER,
  indent: { firstLine: 0 }, ...opt });
const pn = (text, opt = {}) => new Paragraph({ children: runs(text), indent: { firstLine: 0 }, ...opt });

const h1 = (text, opt = {}) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)], ...opt });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
const h3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });

// переліки: дефіс або 1), 2) ...
let listInstance = 0;
const li = (items) => items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "dash", level: 0 } }));
const ol = (items) => {
  listInstance += 1;
  return items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "num", level: 0, instance: listInstance } }));
};

// ---------- рисунки ----------
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function fig(file, caption, widthCm = 16.5, maxHcm = 21) {
  const f = path.join(ROOT, file);
  const s = pngSize(f);
  let wpx = widthCm / 2.54 * 96;
  let hpx = wpx * s.h / s.w;
  const maxH = maxHcm / 2.54 * 96;
  if (hpx > maxH) { hpx = maxH; wpx = hpx * s.w / s.h; }
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, indent: { firstLine: 0 }, keepNext: true,
      spacing: { before: 120 }, children: [new ImageRun({ type: "png", data: fs.readFileSync(f),
        transformation: { width: Math.round(wpx), height: Math.round(hpx) } })] }),
    new Paragraph({ style: "FigCaption", children: runs(caption) }),
  ];
}

// ---------- таблиці ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const borders = { top: border, bottom: border, left: border, right: border };
function cell(text, w, { bold = false, align = AlignmentType.CENTER, shade = false, size = 24 } = {}) {
  if (text && typeof text === "object" && text.img) {
    const f = path.join(ROOT, text.img);
    const sz = pngSize(f);
    const wpx = (text.cm || 3.6) / 2.54 * 96;
    return new TableCell({
      width: { size: w, type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
      margins: { top: 40, bottom: 40, left: 40, right: 40 },
      children: [new Paragraph({ alignment: AlignmentType.CENTER, indent: { firstLine: 0 },
        spacing: { line: 240, lineRule: "auto" },
        children: [new ImageRun({ type: "png", data: fs.readFileSync(f),
          transformation: { width: Math.round(wpx), height: Math.round(wpx * sz.h / sz.w) } })] })],
    });
  }
  return new TableCell({
    width: { size: w, type: WidthType.DXA }, borders, verticalAlign: VerticalAlign.CENTER,
    margins: { top: 30, bottom: 30, left: 70, right: 70 },
    shading: shade ? { fill: "F2F2F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
    children: String(text).split("\n").map((line) => new Paragraph({ alignment: align,
      indent: { firstLine: 0 }, spacing: { line: 240, lineRule: "auto" },
      children: runs(line, { bold, size }) })),
  });
}
// header: масив заголовків; rows: масив масивів; widths: частки або DXA
function table(caption, header, rows, widths, { size = 24, alignFirst = AlignmentType.LEFT } = {}) {
  const tot = widths.reduce((a, b) => a + b, 0);
  const ws = widths.map((x) => Math.round(x / tot * W));
  ws[ws.length - 1] += W - ws.reduce((a, b) => a + b, 0);
  const trs = [new TableRow({ tableHeader: true, cantSplit: true,
    children: header.map((h, i) => cell(h, ws[i], { bold: false, size })) })];
  rows.forEach((r) => trs.push(new TableRow({ cantSplit: true,
    children: r.map((c, i) => cell(c, ws[i], { size, align: i === 0 ? alignFirst : AlignmentType.CENTER })) })));
  return [
    new Paragraph({ style: "TabCaption", children: runs(caption) }),
    new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: ws, rows: trs }),
    new Paragraph({ indent: { firstLine: 0 }, spacing: { line: 240, lineRule: "auto" }, children: [] }),
  ];
}

// ---------- формули ----------
// expr - масив дочірніх елементів docx.Math; num - номер формули "2.1"
function eq(expr, num) {
  return new Paragraph({
    indent: { firstLine: 0 }, spacing: { before: 120, after: 120 },
    tabStops: [{ type: TabStopType.CENTER, position: W / 2 }, { type: TabStopType.RIGHT, position: W }],
    children: [new TextRun({ children: [new Tab()] }), new d.Math({ children: expr }),
      new TextRun({ children: [new Tab(), `(${num})`] })],
  });
}
// скорочення для математичних виразів
const M = {
  r: (t) => new d.MathRun(t),
  sub: (base, s) => new d.MathSubScript({ children: [new d.MathRun(base)], subScript: [new d.MathRun(s)] }),
  sup: (base, s) => new d.MathSuperScript({ children: [new d.MathRun(base)], superScript: [new d.MathRun(s)] }),
  subsup: (base, s, u) => new d.MathSubSuperScript({ children: [new d.MathRun(base)],
    subScript: [new d.MathRun(s)], superScript: [new d.MathRun(u)] }),
  frac: (num, den) => new d.MathFraction({ numerator: num, denominator: den }),
  sum: (from, to, body) => (to && to.length ? new d.MathSum({ children: body, subScript: from, superScript: to })
    : new d.MathSum({ children: body, subScript: from })),
  sp: () => new d.MathRun(",\u2003\u2003"),
  sqrt: (body) => new d.MathRadical({ children: body }),
  par: (body) => new d.MathRoundBrackets({ children: body }),
};

// ---------- код ----------
function code(text, size = 20) {
  return text.replace(/\t/g, "    ").split("\n").map((line, i, arr) => new Paragraph({
    style: "Code", children: [new TextRun({ text: line.length ? line : " ", size })],
  }));
}
function codeFile(rel, size = 20) {
  return code(fs.readFileSync(path.join(ROOT, rel), "utf8").replace(/\s+$/, ""), size);
}

// «де» - пояснення до формули
const where = (text) => new Paragraph({ children: runs(text), indent: { firstLine: 0 } });

module.exports = { d, runs, p, pc, pn, h1, h2, h3, li, ol, fig, table, eq, M, code, codeFile, where,
  W, IND, FONT, ROOT, cell };
