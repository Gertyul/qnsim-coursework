// Збирання пояснювальної записки: node build.js [stats.json]
const fs = require("fs");
const path = require("path");
const { d, p, h1, W, IND, FONT, ROOT } = require("./h");
const { Document, Packer, Paragraph, TextRun, Header, AlignmentType, PageNumber, LevelFormat,
  TableOfContents, LevelSuffix } = d;
const front = require("./front");
const { ch1, ch2 } = require("./ch12");
const { ch3 } = require("./ch3");
const { ch4, ch5, conclusions, sources, appendices, stats } = require("./ch45");

const S = stats();
const extra = process.argv[2] && fs.existsSync(process.argv[2]) ? JSON.parse(fs.readFileSync(process.argv[2])) : {};
Object.assign(S, { nPages: "__", nFig: "__", nTab: "__" }, extra);

const body = [
  ...front.taskPage(),
  ...front.annotation(S),
  h1("ЗМІСТ"),
  new TableOfContents("Зміст", { hyperlink: true, headingStyleRange: "1-2" }),
  ...front.intro(S),
  ...ch1(), ...ch2(), ...ch3(S), ...ch4(S), ...ch5(S),
  ...conclusions(S), ...sources(), ...appendices(S),
];

const doc = new Document({
  creator: "Богдан Пята",
  title: front.TOPIC,
  features: { updateFields: false },
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 28 },
        paragraph: { spacing: { line: 360, lineRule: "auto", before: 0, after: 0 }, alignment: AlignmentType.JUSTIFIED,
          indent: { firstLine: IND } },
      },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, allCaps: true, color: "000000" },
        paragraph: { alignment: AlignmentType.CENTER, indent: { firstLine: 0 }, pageBreakBefore: true,
          keepNext: true, spacing: { before: 0, after: 360 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: "000000" },
        paragraph: { alignment: AlignmentType.LEFT, indent: { firstLine: IND }, keepNext: true,
          spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, italics: false, color: "000000" },
        paragraph: { alignment: AlignmentType.LEFT, indent: { firstLine: IND }, keepNext: true,
          spacing: { before: 120, after: 60 }, outlineLevel: 2 } },
      { id: "FigCaption", name: "Figure Caption", basedOn: "Normal",
        paragraph: { alignment: AlignmentType.CENTER, indent: { firstLine: 0 }, spacing: { before: 60, after: 200 } } },
      { id: "TabCaption", name: "Table Caption", basedOn: "Normal",
        paragraph: { alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 0 }, keepNext: true,
          spacing: { before: 120, after: 60 } } },
      { id: "Code", name: "Code", basedOn: "Normal",
        run: { font: "Courier New", size: 20 },
        paragraph: { alignment: AlignmentType.LEFT, indent: { firstLine: 0 }, spacing: { line: 240, lineRule: "auto" } } },
      { id: "TOC1", name: "toc 1", basedOn: "Normal", paragraph: { indent: { firstLine: 0 } } },
      { id: "TOC2", name: "toc 2", basedOn: "Normal", paragraph: { indent: { firstLine: 0, left: 280 } } },
      { id: "TOC3", name: "toc 3", basedOn: "Normal", paragraph: { indent: { firstLine: 0, left: 560 } } },
    ],
  },
  numbering: {
    config: [
      { reference: "dash", levels: [{ level: 0, format: LevelFormat.BULLET, text: "–", suffix: LevelSuffix.SPACE,
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 0, firstLine: IND } } } }] },
      { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", suffix: LevelSuffix.SPACE,
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 0, firstLine: IND } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 },
        margin: { top: 1134, bottom: 1134, left: 1134, right: 1134, header: 567, footer: 567 } },
      titlePage: true,
    },
    headers: {
      default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, indent: { firstLine: 0 },
        children: [new TextRun({ children: [PageNumber.CURRENT] })] })] }),
      first: new Header({ children: [new Paragraph({ children: [] })] }),
    },
    children: [...front.titlePage(), ...body],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "doc", "kursova_raw.docx");
  fs.writeFileSync(out, buf);
  console.log("written", out);
});
