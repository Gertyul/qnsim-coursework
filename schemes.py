"""Схеми для пояснювальної записки в нотації навчального посібника:
черга - прямокутник зі штрихами, пристрій - сірий круг, блокування
маршруту - трикутник з пунктирною лінією до умови B(S, t).
Координати задаються в сантиметрах, рисунок вставляється в 1:1."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

FIG = os.path.join(os.path.dirname(__file__), "figures")
CM = 1 / 2.54
LW = 1.0
GREY = "#d0d0d0"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "mathtext.fontset": "dejavusans",
                     "mathtext.default": "regular"})


def canvas(w, h):
    fig = plt.figure(figsize=(w * CM, h * CM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=300)
    plt.close(fig)


def T(ax, x, y, s, ha="center", va="center", size=9, **kw):
    ax.text(x, y, s, ha=ha, va=va, fontsize=size, **kw)


def line(ax, pts, dashed=False, lw=LW):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color="black", lw=lw, linestyle=(0, (3, 2.5)) if dashed else "-",
            solid_capstyle="butt", zorder=2)


def arrow(ax, pts, lw=LW):
    """Ламана зі стрілкою на кінці."""
    if len(pts) > 2:
        line(ax, pts[:-1], lw=lw)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>,head_length=0.45,head_width=0.18", color="black",
                                lw=lw, shrinkA=0, shrinkB=0), zorder=3)


def queue(ax, x, y, w=1.4, h=1.0, bars=5):
    """Черга: прямокутник, відкритий зліва, зі штрихами праворуч (вхід - (x, y))."""
    x0, y0 = x, y - h / 2
    line(ax, [(x0, y0 + h), (x0 + w, y0 + h), (x0 + w, y0), (x0, y0)])
    for i in range(bars):
        xb = x0 + w - 0.15 - i * 0.14
        line(ax, [(xb, y0 + 0.12), (xb, y0 + h - 0.12)], lw=0.8)
    return x0 + w  # вихід


def device(ax, x, y, name, r=0.55):
    ax.add_patch(Circle((x, y), r, facecolor=GREY, edgecolor="black", lw=LW, zorder=4))
    T(ax, x, y, name, size=10, zorder=5)
    return x - r, x + r


def block(ax, x, y, s=0.32):
    """Трикутник блокування маршруту (вершиною за напрямком руху)."""
    ax.add_patch(Polygon([(x - s / 2, y + s * 0.6), (x - s / 2, y - s * 0.6), (x + s / 2, y)],
                         closed=True, facecolor="#404040", edgecolor="black", lw=0.8, zorder=4))


def source(ax, x, y, label):
    arrow(ax, [(x, y), (x + 1.1, y)])


# ---------------------------------------------------------------- рис. 2.2
def formal_demo():
    W, H = 17.0, 10.6
    fig, ax = canvas(W, H)
    fs = 8
    yc, yu, yd, yr = 6.6, 9.3, 3.9, 2.4
    # надходження і M1
    arrow(ax, [(0.15, yc), (1.3, yc)])
    T(ax, 0.1, yc + 0.4, "t = exp(2)", ha="left", size=fs)
    qe = queue(ax, 1.3, yc)
    T(ax, 2.0, yc - 0.8, "max = ∞", size=fs)
    line(ax, [(qe, yc), (3.05, yc)])
    device(ax, 3.6, yc, "M1")
    T(ax, 3.6, yc + 0.9, "t = exp(1,4)", size=fs)
    bx = 4.45
    line(ax, [(4.15, yc), (bx, yc)])
    line(ax, [(bx, yd), (bx, yu)])
    rows = ((yu, "FA", "r = 3", "B₁", "KA", "t = exp(2,5)"),
            (yc, "FB", "r = 2", "B₂", "KB", "t = exp(4,0)"),
            (yd, "FR", "r = 1", None, "∞", "t = exp(6,0)"))
    for yy, nm, prio, bl, mx, ty in rows:
        T(ax, bx + 0.15, yy + 0.3, prio, ha="left", size=fs)
        if bl:
            line(ax, [(bx, yy), (5.04, yy)])
            block(ax, 5.2, yy)
            arrow(ax, [(5.36, yy), (5.75, yy)])
            line(ax, [(5.2, yy - 0.22), (5.45, yy - 0.6)], dashed=True)
            T(ax, 5.5, yy - 0.72, bl, ha="left", size=9)
        else:
            arrow(ax, [(bx, yy), (5.75, yy)])
        q2 = queue(ax, 5.75, yy)
        T(ax, 6.45, yy + 0.8, f"max = {mx}", size=fs)
        line(ax, [(q2, yy), (7.6, yy)])
        device(ax, 8.15, yy, nm)
        T(ax, 8.15, yy - 0.9, ty, size=fs)
        line(ax, [(8.7, yy), (9.14, yy)])
        block(ax, 9.3, yy)
        line(ax, [(9.3, yy - 0.22), (9.55, yy - 0.6)], dashed=True)
        T(ax, 9.6, yy - 0.72, "B₃", ha="left", size=9)
        line(ax, [(9.46, yy), (10.2, yy)])
    line(ax, [(10.2, yd), (10.2, yu)])
    # QC
    arrow(ax, [(10.2, yc), (10.65, yc)])
    qe = queue(ax, 10.65, yc)
    T(ax, 11.35, yc + 0.8, "max = KC", size=fs)
    line(ax, [(qe, yc), (12.5, yc)])
    device(ax, 13.05, yc, "QC")
    T(ax, 13.05, yc - 0.9, "t = exp(1,4)", size=fs)
    b2 = 13.85
    line(ax, [(13.6, yc), (b2, yc)])
    # вихід на пакування з групуванням 4
    ypk = yu
    line(ax, [(b2, yc), (b2, ypk)])
    arrow(ax, [(b2, ypk), (14.3, ypk)])
    T(ax, b2 - 0.12, (yc + ypk) / 2, "0,85", ha="right", size=fs)
    T(ax, b2 + 0.17, ypk + 0.32, "4", size=10, weight="bold")
    device(ax, 14.75, ypk, "PK", r=0.45)
    T(ax, 14.75, ypk + 0.8, "t = exp(4)", size=fs)
    arrow(ax, [(15.2, ypk), (15.75, ypk)])
    T(ax, 15.8, ypk, "Склад", ha="left", size=9)
    # брак
    arrow(ax, [(b2, yc), (15.75, yc)])
    T(ax, 14.8, yc + 0.3, "0,05", size=fs)
    T(ax, 15.8, yc, "Брак", ha="left", size=9)
    # повернення на M1
    line(ax, [(b2, yc), (b2, yr), (0.75, yr), (0.75, yc)])
    T(ax, b2 + 0.12, yr + 0.9, "0,10", ha="left", size=fs)
    # умови блокування
    conds = ["B₁:  L(FA) = KA ∧ K(FA) ≠ 0",
             "B₂:  (L(FB) = KB ∧ K(FB) ≠ 0) ∨ t mod 480 ∈ [480 − TO; 480)",
             "B₃:  L(QC) = KC ∧ K(QC) ≠ 0"]
    for i, c in enumerate(conds):
        T(ax, 0.3, 1.55 - i * 0.55, c, ha="left", size=8.5)
    save(fig, "formal.png")


# ---------------------------------------------------------------- рис. 2.1 нотація
def notation():
    W, H = 16.5, 13.2
    fig, ax = canvas(W, H)
    rows = [
        ("Надходження\nвимог ззовні", "Інтервал t між надходженнями; режим при блокуванні маршруту:\nпризупинення або втрата вимоги"),
        ("Черга", "max – обмеження кількості місць (за замовчуванням ∞);\nдисципліна FIFO / LIFO / за пріоритетом вимоги"),
        ("Пристрій\n(канал) обслуговування", "t – час обслуговування; стан K ∈ {0, 1, 2}:\nвільний, зайнятий, заблокований"),
        ("СМО з m каналами", "m – кількість ідентичних каналів;\nчерга є складовою частиною СМО"),
        ("Розгалуження\nз ймовірностями", "p$_k$ – ймовірність (вага) вибору маршруту серед\nмаршрутів однакового пріоритету"),
        ("Розгалуження\nз пріоритетом", "r$_k$ – пріоритет маршруту (число або функція стану);\nобирається відкритий маршрут з найбільшим r$_k$"),
        ("Блокування\nмаршруту", "B(S, t) – умова блокування; при B = 1 маршрут закритий,\nвимога залишається в елементі, з якого виходить"),
    ]
    xs, xn, xd = 0.2, 4.6, 8.0
    top = H - 0.2
    rh = (H - 1.0) / len(rows)
    # шапка
    for x0, x1, s in ((xs, xn, "Графічне позначення"), (xn, xd, "Елемент"), (xd, W - 0.2, "Числові параметри")):
        T(ax, (x0 + x1) / 2, top - 0.4, s, size=9, weight="bold")
    yh = top - 0.8
    line(ax, [(xs, top), (W - 0.2, top)])
    line(ax, [(xs, yh), (W - 0.2, yh)])
    for i, (name, par) in enumerate(rows):
        yc = yh - rh * (i + 0.5)
        yb = yh - rh * (i + 1)
        line(ax, [(xs, yb), (W - 0.2, yb)], lw=0.6)
        T(ax, xn + 0.15, yc, name, ha="left", size=9)
        T(ax, xd + 0.15, yc, par, ha="left", size=8.5)
        cx = (xs + xn) / 2
        if i == 0:
            arrow(ax, [(cx - 1.4, yc), (cx + 0.2, yc)])
            T(ax, cx + 1.1, yc, "t = exp(2)", size=8.5)
        elif i == 1:
            queue(ax, cx - 0.9, yc)
            T(ax, cx + 1.3, yc, "max = 10", size=8.5)
        elif i == 2:
            device(ax, cx - 0.5, yc, "D1", r=0.45)
            T(ax, cx + 1.0, yc, "t = unif(5, 2)", size=8.5)
        elif i == 3:
            queue(ax, cx - 1.9, yc, w=1.1, h=0.9)
            line(ax, [(cx - 0.8, yc), (cx - 0.4, yc)])
            line(ax, [(cx - 0.4, yc + 0.5), (cx - 0.4, yc - 0.5)])
            for dy, nm in ((0.5, "D1"), (-0.5, "Dm")):
                line(ax, [(cx - 0.4, yc + dy), (cx - 0.05, yc + dy)])
                device(ax, cx + 0.3, yc + dy, nm, r=0.33)
            T(ax, cx + 0.3, yc + 0.05, "⋮", size=8)
            T(ax, cx + 1.35, yc, "m", size=9, style="italic")
        elif i in (4, 5):
            line(ax, [(cx - 1.4, yc), (cx - 0.5, yc), (cx - 0.5, yc + 0.45)])
            line(ax, [(cx - 0.5, yc), (cx - 0.5, yc - 0.45)])
            labs = ("0,7", "0,3") if i == 4 else ("r = 2", "r = 1")
            for dy, lb in ((0.45, labs[0]), (-0.45, labs[1])):
                arrow(ax, [(cx - 0.5, yc + dy), (cx + 0.6, yc + dy)])
                T(ax, cx + 1.25, yc + dy, lb, size=8.5)
        else:
            device(ax, cx - 1.3, yc + 0.1, "", r=0.35)
            line(ax, [(cx - 0.95, yc + 0.1), (cx - 0.45, yc + 0.1)])
            block(ax, cx - 0.29, yc + 0.1)
            arrow(ax, [(cx - 0.13, yc + 0.1), (cx + 0.7, yc + 0.1)])
            line(ax, [(cx - 0.29, yc - 0.1), (cx + 0.1, yc - 0.5)], dashed=True)
            T(ax, cx + 0.15, yc - 0.6, "B(S, t)", ha="left", size=8.5)
    for x in (xs, xn, xd, W - 0.2):
        line(ax, [(x, top), (x, yh - rh * len(rows))])
    save(fig, "notation.png")


# ---------------------------------------------------------------- рис. 1.1 концептуальна схема
def rbox(ax, x, y, w, h, s, dashed=False, size=8.5, fill="white"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.18",
                                facecolor=fill, edgecolor="black", lw=LW,
                                linestyle=(0, (3, 2)) if dashed else "-", zorder=3))
    T(ax, x, y, s, size=size, zorder=4)


def gateway(ax, x, y, s=0.42, mark="×"):
    ax.add_patch(Polygon([(x, y + s), (x + s, y), (x, y - s), (x - s, y)], closed=True,
                         facecolor="white", edgecolor="black", lw=LW, zorder=3))
    T(ax, x, y, mark, size=11, zorder=4)


def event(ax, x, y, end=False):
    ax.add_patch(Circle((x, y), 0.3, facecolor="white", edgecolor="black", lw=2.2 if end else LW, zorder=3))


def concept():
    W, H = 16.0, 19.0
    fig, ax = canvas(W, H)
    cx, bw, bh = 8.0, 5.4, 1.15
    cols = (3.0, 8.0, 13.0)
    event(ax, cx, 18.5)
    T(ax, cx + 0.55, 18.5, "Надходження заготовки (інтервал exp(2) хв)", ha="left", size=8.5)
    arrow(ax, [(cx, 18.2), (cx, 17.25)])
    rbox(ax, cx, 16.7, bw, bh, "Очікування на вхідному складі\n(місць необмежено)")
    arrow(ax, [(cx, 16.12), (cx, 15.25)])
    rbox(ax, cx, 14.7, bw, bh, "Токарна обробка на M1\n(exp(1,4) хв)", fill="#eeeeee")
    arrow(ax, [(cx, 14.12), (cx, 13.22)])
    gateway(ax, cx, 12.8)
    T(ax, cx + 0.55, 13.15, "вибір гілки за пріоритетом", ha="left", size=8)
    ybr = 12.0
    line(ax, [(cx, 12.38), (cx, ybr)])
    line(ax, [(cols[0], ybr), (cols[2], ybr)])
    labels = ("r = 3: є місце біля FA", "r = 2: є місце біля FB\nі немає техобслуговування", "r = 1: інакше\n(гілка без блокування)")
    nk = ("Накопичувач FA\n(KA місць)", "Накопичувач FB\n(KB місць)", "Черга FR\n(необмежена)")
    fr = ("Фрезерування FA\n(сучасний, exp(2,5))", "Фрезерування FB\n(старий, exp(4,0))", "Ручна обробка FR\n(резерв, exp(6,0))")
    for x, lab, a1, a2 in zip(cols, labels, nk, fr):
        arrow(ax, [(x, ybr), (x, 10.38)])
        T(ax, x, 11.35, lab, size=7.5, bbox=dict(facecolor="white", edgecolor="none", pad=0.3))
        rbox(ax, x, 9.8, 3.7, bh, a1)
        arrow(ax, [(x, 9.22), (x, 8.48)])
        rbox(ax, x, 7.9, 3.7, bh, a2, fill="#eeeeee")
        line(ax, [(x, 7.32), (x, 6.8)])
    line(ax, [(cols[0], 6.8), (cols[2], 6.8)])
    arrow(ax, [(cx, 6.8), (cx, 6.28)])
    rbox(ax, cx, 5.7, bw + 0.9, bh, "Накопичувач QC (KC місць)\nзаповнений → верстат простоює")
    arrow(ax, [(cx, 5.12), (cx, 4.38)])
    rbox(ax, cx, 3.8, bw, bh, "Контроль якості QC\n(exp(1,4) хв)", fill="#eeeeee")
    arrow(ax, [(cx, 3.22), (cx, 2.82)])
    gateway(ax, cx, 2.4, s=0.38)
    # придатна -> пакування
    line(ax, [(cx + 0.38, 2.4), (11.0, 2.4)])
    arrow(ax, [(11.0, 2.4), (11.0, 1.62)])
    T(ax, 9.6, 2.65, "придатна (0,85)", size=8)
    rbox(ax, 11.0, 1.05, 3.4, 1.05, "Пакування по 4 шт.\n(exp(4) хв)", fill="#eeeeee")
    arrow(ax, [(12.7, 1.05), (14.0, 1.05)])
    event(ax, 14.3, 1.05, end=True)
    T(ax, 14.3, 1.6, "Склад", size=8.5)
    # брак
    arrow(ax, [(cx, 2.02), (cx, 0.75)])
    event(ax, cx, 0.45, end=True)
    T(ax, cx - 0.45, 0.45, "Брак (0,05)", ha="right", size=8.5)
    # повторна обробка
    line(ax, [(cx - 0.38, 2.4), (0.6, 2.4), (0.6, 16.7)])
    arrow(ax, [(0.6, 16.7), (cx - bw / 2, 16.7)])
    T(ax, 0.75, 9.0, "повторна обробка (0,10)", ha="left", size=8, rotation=90)
    save(fig, "concept.png")


# ---------------------------------------------------------------- блок-схеми (ГОСТ 19.701)
def fc_box(ax, x, y, w, h, s, kind="proc", size=8.5):
    if kind == "proc":
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor="white", edgecolor="black", lw=LW, zorder=3))
    elif kind == "term":
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle=f"round,pad=0,rounding_size={h/2}",
                                    facecolor="white", edgecolor="black", lw=LW, zorder=3))
    elif kind == "io":
        d = 0.3
        ax.add_patch(Polygon([(x - w / 2 + d, y + h / 2), (x + w / 2 + d, y + h / 2), (x + w / 2 - d, y - h / 2),
                              (x - w / 2 - d, y - h / 2)], closed=True, facecolor="white", edgecolor="black", lw=LW, zorder=3))
    elif kind == "dec":
        ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True,
                             facecolor="white", edgecolor="black", lw=LW, zorder=3))
    T(ax, x, y, s, size=size, zorder=4)


def algo():
    W, H = 16.0, 22.0
    fig, ax = canvas(W, H)
    fs = 8
    cx, w, gap = 6.2, 9.0, 0.5
    xr, wr = 13.3, 4.0
    y = H - 0.3
    pos = {}

    def put(key, kind, text, h, width=w, x=cx):
        nonlocal y
        yc = y - h / 2
        if pos:
            last = list(pos.values())[-1]
            arrow(ax, [(cx, last[1]), (cx, y)])
        fc_box(ax, x, yc, width, h, text, kind, size=fs)
        pos[key] = (y, y - h, yc)
        y = y - h - gap

    put("start", "term", "Початок", 0.7, 3.0)
    put("in", "io", "Введення мережі (елементи, маршрути), Tmod, Twarm", 0.85)
    put("init", "proc", "t := 0;  t$_{0,i}$ := g$_{0,i}$;  усі канали K := 0, черги порожні", 0.85)
    put("find", "proc", "t$_{next}$ := min(t$_{0,i}$; t$_{j,r}$; моменти зміни часових умов)", 0.85)
    put("dw", "dec", "t$_{next}$ ≥ Twarm\nвперше?", 1.4, 4.6)
    yc = pos["dw"][2]
    fc_box(ax, xr, yc, wr - 0.6, 0.85, "Обнулити статистику", size=fs)
    arrow(ax, [(cx + 2.3, yc), (xr - (wr - 0.6) / 2, yc)])
    T(ax, cx + 2.6, yc + 0.25, "так", size=fs)
    y_merge = pos["dw"][1] - gap / 2
    line(ax, [(xr, yc - 0.425), (xr, y_merge), (cx, y_merge)])
    T(ax, cx + 0.3, pos["dw"][1] - 0.15, "ні", size=fs, ha="left")
    put("dt", "dec", "t$_{next}$ > Tmod?", 1.4, 4.6)
    ytc = pos["dt"][2]
    T(ax, cx + 2.6, ytc + 0.25, "так", size=fs)
    T(ax, cx + 0.3, pos["dt"][1] - 0.15, "ні", size=fs, ha="left")
    put("stat", "proc", "Статистика на [t; t$_{next}$):  ΣL·Δt,  ΣZ·Δt,  ΣY·Δt", 0.85)
    put("adv", "proc", "t := t$_{next}$", 0.7, 3.0)
    put("ev", "proc", "Обробка подій з t$_{next}$ = t (спершу завершення\nобслуговування, потім надходження): вибір\nмаршруту, перехід каналу у стан 0, 1 або 2", 1.45)
    put("rb", "proc", "Перегляд заблокованих у порядку часу\nблокування; якщо маршрут відкрився –\nзвільнення і повторний перегляд", 1.45)
    put("dm", "dec", "Є ще події\nз t$_{next}$ = t?", 1.4, 4.6)
    ym = pos["dm"][2]
    # так -> назад до обробки подій
    xl1, xl2 = cx - w / 2 - 0.55, cx - w / 2 - 1.1
    line(ax, [(cx - 2.3, ym), (xl1, ym), (xl1, pos["ev"][2])])
    arrow(ax, [(xl1, pos["ev"][2]), (cx - w / 2, pos["ev"][2])])
    T(ax, cx - 2.6, ym + 0.25, "так", size=fs)
    # ні -> до пошуку найближчої події
    yb = pos["dm"][1] - 0.4
    line(ax, [(cx, pos["dm"][1]), (cx, yb), (xl2, yb), (xl2, pos["find"][2])])
    arrow(ax, [(xl2, pos["find"][2]), (cx - w / 2, pos["find"][2])])
    T(ax, cx + 0.3, pos["dm"][1] - 0.2, "ні", size=fs, ha="left")
    # права колонка: завершення
    y1 = ytc - 1.6
    line(ax, [(cx + 2.3, ytc), (xr, ytc)])
    arrow(ax, [(xr, ytc), (xr, y1 + 0.425)])
    fc_box(ax, xr, y1, wr - 0.6, 0.85, "Статистика\nна [t; Tmod)", size=fs)
    y2 = y1 - 1.6
    arrow(ax, [(xr, y1 - 0.425), (xr, y2 + 0.5)])
    fc_box(ax, xr, y2, wr - 0.4, 1.0, "Виведення характе-\nристик (2.6)–(2.12)", "io", size=fs)
    y3 = y2 - 1.4
    arrow(ax, [(xr, y2 - 0.5), (xr, y3 + 0.35)])
    fc_box(ax, xr, y3, 2.6, 0.7, "Кінець", "term", size=fs)
    ax.set_ylim(yb - 0.3, H)
    fig.set_size_inches(W * CM, (H - yb + 0.3) * CM)
    save(fig, "algo.png")


def route():
    W, H = 16.0, 13.0
    fig, ax = canvas(W, H)
    cx = 6.0
    y = H - 0.6
    fc_box(ax, cx, y, 8.4, 0.8, "Вимога має залишити елемент у момент t", "term")
    y -= 1.5
    arrow(ax, [(cx, y + 1.1), (cx, y + 0.45)])
    fc_box(ax, cx, y, 7.6, 0.9, "R$_0$ = { k : B$_k$(S, t) = 0 }  – відкриті маршрути")
    y -= 1.75
    arrow(ax, [(cx, y + 1.3), (cx, y + 0.65)])
    fc_box(ax, cx, y, 4.0, 1.3, "R$_0$ = ∅ ?", "dec")
    y_e = y
    # так -> блокування праворуч
    fc_box(ax, cx + 5.6, y, 4.9, 1.6, "Канал СМО: K := 2, t$_r$ := ∞;\nджерело: t$_0$ := ∞ або втрата;\nзанести в список\nзаблокованих", size=8)
    arrow(ax, [(cx + 2.0, y), (cx + 3.15, y)])
    T(ax, cx + 2.3, y + 0.25, "так", size=8)
    y -= 1.85
    arrow(ax, [(cx, y_e - 0.65), (cx, y + 0.55)])
    T(ax, cx + 0.3, y_e - 0.9, "ні", size=8)
    fc_box(ax, cx, y, 7.6, 1.1, "Обчислити пріоритети r$_k$(S, t), k ∈ R$_0$;\nG = { k ∈ R$_0$ : r$_k$ = max r$_i$ }")
    y -= 1.85
    arrow(ax, [(cx, y + 1.3), (cx, y + 0.65)])
    fc_box(ax, cx, y, 4.0, 1.3, "|G| = 1 ?", "dec")
    y_g = y
    fc_box(ax, cx + 5.4, y - 1.6, 4.4, 1.1, "Вибір k ∈ G з ймовірністю\np$_k$ / Σ p$_i$", size=8)
    line(ax, [(cx + 2.0, y), (cx + 5.4, y)])
    arrow(ax, [(cx + 5.4, y), (cx + 5.4, y - 1.05)])
    T(ax, cx + 2.3, y + 0.25, "ні", size=8)
    y -= 3.2
    arrow(ax, [(cx, y_g - 0.65), (cx, y + 0.6)])
    T(ax, cx + 0.3, y_g - 0.9, "так", size=8)
    line(ax, [(cx + 5.4, y_g - 2.15), (cx + 5.4, y + 0.95), (cx, y + 0.95)])
    fc_box(ax, cx, y, 9.0, 1.2, "Звільнити канал (K := 0), узяти вимогу з черги;\nпередати вимогу в СМО маршруту k")
    ax.set_ylim(y - 0.9, H)
    fig.set_size_inches(W * CM, (H - y + 0.9) * CM)
    save(fig, "route.png")


# ---------------------------------------------------------------- рис. 3.x мережі верифікації
def verif():
    W, H = 16.0, 17.2
    fig, ax = canvas(W, H)
    fs = 8

    def src(x, y, lab):
        line(ax, [(x, y), (x + 1.3, y)])
        T(ax, x, y + 0.35, lab, ha="left", size=fs)
        return x + 1.3

    def blk(x, y, cond, up=False):
        """трикутник на дузі, що починається в x; повертає кінець трикутника"""
        line(ax, [(x, y), (x + 0.15, y)])
        block(ax, x + 0.31, y)
        sgn = 1 if up else -1
        line(ax, [(x + 0.31, y + sgn * 0.22), (x + 0.6, y + sgn * 0.75)], dashed=True)
        T(ax, x + 0.62, y + sgn * 0.95, cond, ha="left", size=fs)
        return x + 0.47

    def out(x, y, x2):
        arrow(ax, [(x, y), (x2, y)])
        T(ax, x2 + 0.15, y, "Вихід", ha="left", size=9)

    # а)
    y = 16.0
    x = src(0.2, y, "t = exp(1)")
    x = blk(x, y, "B: L(S) = 2 ∧ K(S) ≠ 0")
    arrow(ax, [(x, y), (x + 0.9, y)])
    q = queue(ax, x + 0.9, y)
    T(ax, x + 1.6, y + 0.8, "max = 2", size=fs)
    line(ax, [(q, y), (q + 0.9, y)])
    device(ax, q + 1.45, y, "S")
    T(ax, q + 1.45, y + 0.9, "t = exp(0,8)", size=fs)
    out(q + 2.0, y, q + 3.6)
    T(ax, W / 2, y - 1.55, "а) M/M/1/3: блокування маршруту від джерела (режим втрати вимоги)", size=9)

    # б)
    y = 12.5
    x = src(0.2, y, "t = 0")
    x = blk(x, y, "B: K(F1) ≠ 0")
    arrow(ax, [(x, y), (x + 0.9, y)])
    device(ax, x + 1.45, y, "F1")
    T(ax, x + 1.45, y + 0.9, "t = exp(1)", size=fs)
    x = blk(x + 2.0, y, "B: L(F2) = B ∧ K(F2) ≠ 0")
    arrow(ax, [(x, y), (x + 0.9, y)])
    q = queue(ax, x + 0.9, y)
    T(ax, x + 1.6, y + 0.8, "max = B", size=fs)
    line(ax, [(q, y), (q + 0.9, y)])
    device(ax, q + 1.45, y, "F2")
    T(ax, q + 1.45, y + 0.9, "t = exp(1)", size=fs)
    out(q + 2.0, y, q + 3.6)
    T(ax, W / 2, y - 1.55, "б) насичена двофазна лінія з накопичувачем B та блокуванням першої фази", size=9)

    # в)
    y = 9.0
    x = src(0.2, y, "t = exp(1)")
    x = blk(x, y, "B: t mod 60 ∈ [50; 60)", up=True)
    arrow(ax, [(x, y), (x + 4.3, y)])
    xb = x + 4.3
    line(ax, [(xb, y - 0.9), (xb, y + 0.9)])
    for dy, nm in ((0.9, "D1"), (-0.9, "D10")):
        line(ax, [(xb, y + dy), (xb + 0.5, y + dy)])
        device(ax, xb + 0.95, y + dy, nm, r=0.45)
        line(ax, [(xb + 1.4, y + dy), (xb + 1.9, y + dy)])
    T(ax, xb + 0.95, y + 0.05, "⋮", size=9)
    line(ax, [(xb + 1.9, y - 0.9), (xb + 1.9, y + 0.9)])
    out(xb + 1.9, y, xb + 3.4)
    T(ax, xb + 2.2, y + 0.4, "t = exp(0,5), m = 10", ha="left", size=fs)
    T(ax, W / 2, y - 1.9, "в) блокування маршруту за часовою умовою (перерва 10 хв щогодини)", size=9)

    # г) мережа Джексона
    def smo(x, y, name, lab, below=False):
        q = queue(ax, x, y)
        line(ax, [(q, y), (q + 0.4, y)])
        device(ax, q + 0.95, y, name)
        T(ax, q + 0.95, y + (-0.95 if below else 0.95), lab, size=fs)
        return q + 1.5

    Y = 3.4
    line(ax, [(0.2, Y), (1.8, Y)])
    T(ax, 0.2, Y + 0.35, "t = exp(1)", ha="left", size=fs)
    arrow(ax, [(1.8, Y), (2.4, Y)])
    x = smo(2.4, Y, "S1", "t = exp(0,5)")
    xb = x + 0.6
    line(ax, [(x, Y), (xb, Y)])
    line(ax, [(xb, Y - 1.3), (xb, Y + 1.3)])
    xe = 13.0
    for dy, p, nm, lab in ((1.3, "p = 0,6", "S2", "t = exp(0,8)"), (-1.3, "p = 0,4", "S3", "t = exp(1)")):
        yy = Y + dy
        T(ax, xb + 0.15, yy + 0.3, p, ha="left", size=fs)
        arrow(ax, [(xb, yy), (xb + 1.4, yy)])
        x2 = smo(xb + 1.4, yy, nm, lab, below=dy < 0)
        if dy > 0:
            xb2 = x2 + 0.6
            line(ax, [(x2, yy), (xe, yy)])
            T(ax, xb2 + 0.2, yy + 0.3, "p = 0,8", ha="left", size=fs)
            T(ax, xb2 + 0.2, yy + 1.45, "p = 0,2", ha="left", size=fs)
            line(ax, [(xb2, yy), (xb2, yy + 1.2), (1.8, yy + 1.2)])
            arrow(ax, [(1.8, yy + 1.2), (1.8, Y)])
        else:
            line(ax, [(x2, yy), (xe, yy)])
    line(ax, [(xe, Y - 1.3), (xe, Y + 1.3)])
    arrow(ax, [(xe, Y), (xe + 1.2, Y)])
    T(ax, xe + 1.35, Y, "Вихід", ha="left", size=9)
    T(ax, W / 2, Y - 2.75, "г) мережа Джексона: ймовірнісні маршрути між СМО зі зворотним зв'язком", size=9)
    save(fig, "verif.png")


def symbols():
    """Окремі графічні позначення для таблиці 2.1 (4,2 × 2,0 см)."""
    W, H = 4.2, 2.0
    y = 1.0
    specs = {}

    def s_source(ax):
        arrow(ax, [(0.3, y), (1.9, y)])
        T(ax, 2.0, y, "t = exp(2)", ha="left", size=8)
    specs["source"] = s_source

    def s_queue(ax):
        queue(ax, 0.6, y)
        T(ax, 2.15, y, "max = 10", ha="left", size=8)
    specs["queue"] = s_queue

    def s_device(ax):
        device(ax, 1.0, y, "D1", r=0.5)
        T(ax, 1.65, y, "t = unif(5,2)", ha="left", size=8)
    specs["device"] = s_device

    def s_smo(ax):
        queue(ax, 0.2, y, w=1.2, h=0.9)
        line(ax, [(1.4, y), (1.8, y)])
        line(ax, [(1.8, y + 0.5), (1.8, y - 0.5)])
        for dy, nm in ((0.5, "D1"), (-0.5, "Dm")):
            line(ax, [(1.8, y + dy), (2.15, y + dy)])
            device(ax, 2.5, y + dy, nm, r=0.36)
        T(ax, 2.5, y + 0.03, "⋮", size=8)
        T(ax, 3.05, y, "m", ha="left", size=9, style="italic")
    specs["smo"] = s_smo

    def s_prob(ax):
        line(ax, [(0.3, y), (1.2, y)])
        line(ax, [(1.2, y + 0.55), (1.2, y - 0.55)])
        for dy, lb in ((0.55, "0,7"), (-0.55, "0,3")):
            arrow(ax, [(1.2, y + dy), (2.6, y + dy)])
            T(ax, 2.75, y + dy, lb, ha="left", size=8)
    specs["prob"] = s_prob

    def s_prio(ax):
        line(ax, [(0.3, y), (1.2, y)])
        line(ax, [(1.2, y + 0.55), (1.2, y - 0.55)])
        for dy, lb in ((0.55, "r = 2"), (-0.55, "r = 1")):
            arrow(ax, [(1.2, y + dy), (2.6, y + dy)])
            T(ax, 2.75, y + dy, lb, ha="left", size=8)
    specs["prio"] = s_prio

    def s_block(ax):
        device(ax, 0.75, y + 0.25, "", r=0.4)
        line(ax, [(1.15, y + 0.25), (1.6, y + 0.25)])
        block(ax, 1.76, y + 0.25)
        arrow(ax, [(1.92, y + 0.25), (2.9, y + 0.25)])
        line(ax, [(1.76, y + 0.03), (2.1, y - 0.5)], dashed=True)
        T(ax, 2.15, y - 0.62, "B(S, t)", ha="left", size=8)
    specs["block"] = s_block

    def s_group(ax):
        arrow(ax, [(0.3, y), (2.4, y)])
        T(ax, 1.3, y + 0.32, "k", size=10, weight="bold", style="italic")
        T(ax, 2.55, y, "(1/k)", ha="left", size=8)
    specs["group"] = s_group

    def s_exit(ax):
        arrow(ax, [(0.3, y), (2.2, y)])
        T(ax, 2.4, y, "Вихід", ha="left", size=9)
    specs["exit"] = s_exit

    for name, f in specs.items():
        fig, ax = canvas(W, H)
        f(ax)
        save(fig, f"sym_{name}.png")


if __name__ == "__main__":
    formal_demo()
    symbols()
    concept()
    verif()
    print("ok")
