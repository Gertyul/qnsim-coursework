// Список джерел та додатки
const fs = require("fs");
const path = require("path");
const { d, p, pc, pn, h1, h2, code, codeFile, ROOT } = require("./h");

const SOURCES = [
  "Стеценко І. В., Дифучина О. Ю., Дифучин А. Ю. Моделювання систем. Курсова робота : рек. до виконання курсов. роботи : навч. посіб. для здобувачів ступеня бакалавра за освіт. програмою «Інженерія програмного забезпечення інформаційних систем» спец. 121 Інженерія програмного забезпечення. Київ : КПІ ім. Ігоря Сікорського, 2024. 109 с. URL: https://ela.kpi.ua/items/907b5d1f-ca48-4165-a67e-e790ac6fbec5 (дата звернення: 24.10.2026).",
  "Стеценко І. В. Моделювання систем : навч. посіб. Черкаси : ЧДТУ, 2010. 399 с.",
  "Томашевський В. М. Моделювання систем. Київ : Видавнича група BHV, 2005. 352 с.",
  "Law A. M. Simulation Modeling and Analysis. 5th ed. New York : McGraw-Hill Education, 2015. 804 p.",
  "Kleinrock L. Queueing Systems. Vol. 1: Theory. New York : John Wiley & Sons, 1975. 417 p.",
  "Gross D., Shortle J. F., Thompson J. M., Harris C. M. Fundamentals of Queueing Theory. 4th ed. Hoboken : John Wiley & Sons, 2008. 528 p.",
  "Balsamo S., de Nitto Personè V., Onvural R. Analysis of Queueing Networks with Blocking. Boston : Kluwer Academic Publishers, 2001. 176 p.",
  "Python Software Foundation. The Python Standard Library: random — Generate pseudo-random numbers. URL: https://docs.python.org/3/library/random.html (дата звернення: 24.10.2026).",
  "Kelton W. D., Ivey N., Zupick N. Simulation with Arena. 7th ed. New York : McGraw-Hill, 2024. 611 p.",
  "Object Management Group. Business Process Model and Notation (BPMN). Version 2.0.2. 2014. URL: https://www.omg.org/spec/BPMN/2.0.2/ (дата звернення: 24.10.2026).",
  "Virtanen P., Gommers R., Oliphant T. E. et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. Nature Methods. 2020. Vol. 17. P. 261–272. DOI: 10.1038/s41592-019-0686-2.",
  "Hillier F. S., Boling R. W. Finite queues in series with exponential or Erlang service times – a numerical approach. Operations Research. 1967. Vol. 15, No. 2. P. 286–303.",
  "Звіти у сфері науки і техніки. Структура та правила оформлювання : ДСТУ 3008:2015. Київ : ДП «УкрНДНЦ», 2016. 26 с.",
];

function sources() {
  return [
    h1("СПИСОК ВИКОРИСТАНИХ ДЖЕРЕЛ"),
    ...SOURCES.map((s, i) => new d.Paragraph({ children: [new d.TextRun(`${i + 1}. ${s}`)] })),
  ];
}

function appendix(letter, title, blocks) {
  return [h1(`ДОДАТОК ${letter}`), pc(title, { spacing: { after: 240 } }), ...blocks];
}

function appendices() {
  const L = (rel) => [pn(`Файл ${rel}`, { spacing: { before: 120, after: 60 } }), ...codeFile(rel, 20)];
  const lines = fs.readFileSync(path.join(ROOT, "results", "protocol_demo.txt"), "utf8").split("\n");
  const i450 = lines.findIndex((l) => l.includes("умови блокування за часом"));
  const proto = lines.slice(0, 190).join("\n") + "\n   ...\n" + lines.slice(Math.max(0, i450 - 25), i450 + 40).join("\n");
  return [
    ...appendix("А", "Лістинг бібліотеки імітації qnsim", [
      ...L("qnsim/__init__.py"), ...L("qnsim/distributions.py"), ...L("qnsim/conditions.py"),
      ...L("qnsim/elements.py"), ...L("qnsim/model.py")]),
    ...appendix("Б", "Лістинг опису моделей", [...L("examples/demo_line.py"), ...L("examples/robots_conveyor.py")]),
    ...appendix("В", "Лістинг програми верифікації", [...L("verification.py")]),
    ...appendix("Г", "Лістинг програми експериментального дослідження", [...L("experiments.py")]),
    ...appendix("Д", "Фрагмент протоколу подій демонстраційної моделі", [
      p("Протокол отримано для демонстраційної мережі з ємностями накопичувачів KA = KB = KC = 1 на " +
        "інтервалі [0; 480] хв (початкове значення генератора 7). Наведено початок протоколу, де видно " +
        "блокування каналів, вибір гілки FR і групування деталей, та фрагмент навколо моменту 450 хв, коли " +
        "умова B₂ змінює значення за часом і маршрут до FB закривається на техобслуговування. Кожен рядок " +
        "містить момент події та її опис; індекс у квадратних дужках – номер каналу СМО."),
      ...code(proto, 18)]),
  ];
}

module.exports = { sources, appendices, SOURCES };
