"""Оцінка запропонованих змін демонстраційної мережі (розділ 5).
Результат додається до results/summary.json під ключем "proposals"."""
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
import experiments as E  # noqa: E402

VARIANTS = {
    "Базовий (KA = KB = 2, KC = 3)": {},
    "KA = KB = 3, KC = 3": {"KA": 3, "KB": 3},
    "Рекомендований (KA = KB = 3, KC = 5)": {"KA": 3, "KB": 3, "KC": 5},
}

if __name__ == "__main__":
    path = os.path.join(E.OUT, "summary.json")
    with open(path, encoding="utf-8") as f:
        S = json.load(f)
    E.TMOD = float(S["TMOD"])
    with Pool(2) as pool:
        S["proposals"] = E.proposals(pool, VARIANTS)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=1, default=str)
    for k, v in S["proposals"].items():
        print(k, {kk: round(vv, 4) for kk, vv in v.items() if isinstance(vv, float)})
