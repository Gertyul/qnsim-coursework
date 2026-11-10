"""Побудова графіків за результатами експериментів (results/*.csv, summary.json)."""
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import numpy as np  # noqa: E402

BASE = os.path.dirname(__file__)
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 1.6, "legend.frameon": False, "savefig.dpi": 200,
})
COMMA = FuncFormatter(lambda v, p: (f"{v:g}").replace(".", ","))


def comma(ax, x=True, y=True):
    if x:
        ax.xaxis.set_major_formatter(COMMA)
    if y:
        ax.yaxis.set_major_formatter(COMMA)


def read(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        r = list(csv.reader(f))
    return r[0], r[1:]


def col(rows, hdr, name):
    i = hdr.index(name)
    return np.array([float(r[i]) for r in rows])


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)


def fig_transient(S):
    hdr, rows = read("transient.csv")
    t = col(rows, hdr, "t") / 1000
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    for k in range(1, len(hdr) - 1):
        ax.plot(t, [float(r[k]) for r in rows], color=SERIES[k - 1], label=f"Прогін {k}")
    T1 = S["T1"] / 1000
    ax.axvline(T1, color=INK2, linestyle="--", linewidth=1)
    ax.text(T1, ax.get_ylim()[1] * 0.99, f" T = {T1:g}·10³ хв", va="top", ha="left", color=INK2, fontsize=9)
    ax.set_xlabel("Модельний час t, тис. хв")
    ax.set_ylabel("Середній час обробки деталі, хв")
    ax.legend(ncol=6, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), handlelength=1.5)
    comma(ax)
    save(fig, "transient.png")

    hdr, rows = read("transient_ensemble.csv")
    t, y = col(rows, hdr, "t"), col(rows, hdr, "L_mean")
    w = 5
    ma = np.convolve(y, np.ones(w) / w, mode="same")
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.plot(t, y, color=SERIES[0], linewidth=1, alpha=0.55, label="Середнє по 40 прогонах")
    ax.plot(t[w:-w], ma[w:-w], color=SERIES[1], label="Ковзне середнє (вікно 250 хв)")
    ax.axvline(2000, color=INK2, linestyle="--", linewidth=1)
    ax.text(2000, 1, "  Tперех = 2000 хв", color=INK2, fontsize=9)
    ax.set_xlabel("Модельний час t, хв")
    ax.set_ylabel("Кількість деталей на ділянці, шт.")
    ax.set_ylim(0, max(y) * 1.15)
    ax.legend(loc="lower right", fontsize=9)
    comma(ax)
    save(fig, "warmup.png")


LEV = ["A>B>R", "B>A>R", "A=B>R", "A=B=R"]


def fig_priorities():
    hdr, rows = read("priorities.csv")
    data = [[float(r[2]) for r in rows if r[0] == lv] for lv in LEV]
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    bp = ax.boxplot(data, widths=0.45, patch_artist=True, medianprops=dict(color=INK))
    for patch, c in zip(bp["boxes"], SERIES):
        patch.set_facecolor(c)
        patch.set_alpha(0.55)
        patch.set_edgecolor(INK2)
    ax.set_xticks(range(1, 5))
    ax.set_xticklabels(LEV)
    ax.set_xlabel("Варіант пріоритетів гілок з M1")
    ax.set_ylabel("Середній час обробки, хв (лог. шкала)")
    ax.set_yscale("log")
    ax.set_yticks([20, 30, 50, 100, 200])
    ax.grid(axis="x", visible=False)
    comma(ax, x=False)
    save(fig, "prio.png")

    sh = {k: [np.mean([float(r[i]) for r in rows if r[0] == lv]) for lv in LEV]
          for k, i in (("FA", 4), ("FB", 5), ("FR", 6))}
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    x = np.arange(4)
    for j, (k, c) in enumerate(zip(("FA", "FB", "FR"), SERIES)):
        ax.bar(x + (j - 1) * 0.26, sh[k], width=0.24, color=c, label=f"Гілка {k}")
    ax.set_xticks(x)
    ax.set_xticklabels(LEV)
    ax.set_xlabel("Варіант пріоритетів гілок з M1")
    ax.set_ylabel("Частка деталей")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    ax.grid(axis="x", visible=False)
    comma(ax, x=False)
    save(fig, "prio_share.png")


def two_panel(name, xs, xl, left, left_lab, right, right_lab, fname, logy=False):
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2))
    if logy:
        axes[0].set_yscale("log")
    for ax, series, lab in ((axes[0], left, left_lab), (axes[1], right, right_lab)):
        for i, (y, nm) in enumerate(series):
            ax.plot(xs, y, "-o", color=SERIES[i], markersize=5, label=nm)
        ax.set_xlabel(xl)
        ax.set_ylabel(lab)
        if len(series) > 1:
            ax.legend(fontsize=8.5)
        comma(ax)
    save(fig, fname)


def fig_sweeps():
    hdr, rows = read("sweep_K.csv")
    x = col(rows, hdr, "K")
    two_panel("K", x, "Ємність KA = KB, місць",
              [(col(rows, hdr, "time"), "час")], "Час обробки, хв (лог. шкала)",
              [(col(rows, hdr, "share_fa"), "FA"), (col(rows, hdr, "share_fb"), "FB"), (col(rows, hdr, "share_fr"), "FR")],
              "Частка деталей на гілку", "sweep_K.png", logy=True)
    hdr, rows = read("sweep_TO.csv")
    x = col(rows, hdr, "TO")
    two_panel("TO", x, "Тривалість техобслуговування TO, хв",
              [(col(rows, hdr, "time"), "час")], "Середній час обробки, хв",
              [(col(rows, hdr, "share_fa"), "FA"), (col(rows, hdr, "share_fb"), "FB"), (col(rows, hdr, "share_fr"), "FR")],
              "Частка деталей на гілку", "sweep_TO.png")
    hdr, rows = read("sweep_KC.csv")
    x = col(rows, hdr, "KC")
    two_panel("KC", x, "Ємність KC, місць",
              [(col(rows, hdr, "time"), "час")], "Середній час обробки, хв",
              [(col(rows, hdr, "b_fa"), "FA"), (col(rows, hdr, "b_fb"), "FB"), (col(rows, hdr, "b_fr"), "FR")],
              "Частка часу блокування верстата", "sweep_KC.png")


def fig_block_refuse():
    hdr, rows = read("block_vs_refuse.csv")
    kc = sorted({int(r[0]) for r in rows})
    get = lambda mode, key: [float(next(r for r in rows if int(r[0]) == k and r[1] == mode)[hdr.index(key)]) for k in kc]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2))
    for ax, key, lab in ((axes[0], "throughput", "Продуктивність, дет./хв"), (axes[1], "time", "Середній час обробки, хв")):
        ax.plot(kc, get("block", key), "-o", color=SERIES[0], markersize=5, label="з блокуванням")
        ax.plot(kc, get("refuse", key), "-s", color=SERIES[1], markersize=5, label="з відмовою")
        ax.set_xlabel("Ємність KC, місць")
        ax.set_ylabel(lab)
        ax.legend(fontsize=8.5)
        comma(ax)
    save(fig, "block_refuse.png")


def fig_complexity(S):
    c = S["complexity"]
    for name, rows, xl, yl, key, idx, deg, fn in (
            ("T", c["rows_T"], "Час моделювання Tmod, тис. хв", "Час імітації, с", "reg_T", 2, 1, "cplx_T.png"),
            ("N", c["rows_N"], "Кількість СМО в мережі N", "Час імітації (Tmod = 5000), с", "reg_N", 2, 2, "cplx_N.png"),
            ("B", c["rows_B"], "Кількість гілок у розгалуженні n", "Час на одну подію, мкс", "reg_B_event", 3, 1, "cplx_B.png")):
        x = np.array([r[0] for r in rows], float)
        y = np.array([r[idx] for r in rows], float)
        b = c[key][0]
        xs = x / 1000 if name == "T" else x
        fig, ax = plt.subplots(figsize=(6.6, 3.2))
        ax.plot(xs, y, "o", color=SERIES[0], markersize=6, label="Виміряне значення")
        xx = np.linspace(0, x.max(), 100)
        yy = sum(bk * xx ** k for k, bk in enumerate(b))
        ax.plot(xx / 1000 if name == "T" else xx, yy, color=SERIES[1],
                label="Квадратична регресія" if deg == 2 else "Лінійна регресія")
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.legend(loc="upper left")
        comma(ax)
        save(fig, fn)


if __name__ == "__main__":
    with open(os.path.join(RES, "summary.json"), encoding="utf-8") as f:
        S = json.load(f)
    hdr, rows = read("transient.csv")
    sp = col(rows, hdr, "spread")
    t = col(rows, hdr, "t")
    S["T1"] = next(t[i] for i in range(len(t)) if all(sp[i:] < 3.0))
    fig_transient(S)
    fig_priorities()
    fig_sweeps()
    fig_block_refuse()
    fig_complexity(S)
    print("графіки збережено; T1 =", S["T1"])
