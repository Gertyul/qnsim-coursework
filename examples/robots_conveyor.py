"""Приклад з навчального посібника (рис. 3.1): обробка деталей п'ятьма
роботами, розміщеними вздовж стрічки конвеєра.

Деталь намагається потрапити на обробку до робота (одне місце очікування);
маршрут до наступної ділянки конвеєра має нижчий пріоритет і обирається
лише тоді, коли маршрут до робота заблоковано умовою Q_i = max (у записі
бібліотеки: "L(Di) = 1 ∧ K(Di) ≠ 0").
Після п'ятого робота деталь повертається на початок конвеєра (3 хв).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qnsim import Const, Create, Dispose, Exp, Model, Process  # noqa: E402


def build(n=5, seed=None):
    src = Create("Надходження", Exp(0.25))
    robots = [Process(f"D{i + 1}", Exp(1.0), max_queue=1) for i in range(n)]
    # «нескінченна» кількість каналів - достатньо велика, щоб не було відмов
    conv = [Process(f"C{i + 1}", Const(0.5 if i > 0 else 3.0), channels=500) for i in range(n)]
    out = Dispose("Вихід")
    # з джерела деталь потрапляє до першого робота або їде далі
    src.add_route(robots[0], priority=1, block="L(D1) = 1 ∧ K(D1) ≠ 0")
    src.add_route(conv[1 % n], priority=0)
    for i in range(n):
        robots[i].to(out)
        # ділянка Ci доставляє деталь до робота i
        conv[i].add_route(robots[i], priority=1, block=f"L(D{i + 1}) = 1 ∧ K(D{i + 1}) ≠ 0")
        conv[i].add_route(conv[(i + 1) % n], priority=0)
    return Model(src, *robots, *conv, out, seed=seed)


if __name__ == "__main__":
    m = build(seed=1)
    r = m.simulate(10000.0, warmup=500.0)
    print(m.report(r))
    print("Продуктивність, дет./хв:", round(r["Вихід"]["throughput"], 4))
    print("Середній час перебування, хв:", round(r["Вихід"]["mean_time"], 3))
