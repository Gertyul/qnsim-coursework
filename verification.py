"""Верифікація універсального алгоритму імітації.

1) Порівняння з аналітичними результатами теорії масового обслуговування
   для мереж, у яких задіяні всі механізми алгоритму:
     - M/M/1 та M/M/3 (базове просування часу та багатоканальна СМО);
     - M/M/1/K, реалізована блокуванням маршруту від джерела в режимі
       втрати вимоги (перевірка блокування Create, on_block='lose');
     - система з упорядкованим зайняттям 3 каналів без черги, реалізована
       пріоритетами маршрутів (перевірка пріоритетного вибору маршруту);
     - насичена двофазна лінія з накопичувачем ємністю B та блокуванням
       першої фази (перевірка блокування каналу СМО, стан K=2);
     - блокування маршруту за часовою умовою (перерви в роботі);
     - дуга групування k → 1 (система E4/M/1) та розгрупування 1 → k.
   Усі умови блокування записані в логіко-алгебраїчному вигляді.
2) Верифікація демонстраційної моделі варіюванням вхідних змінних.
3) Протокол подій демонстраційної моделі.
"""
import csv
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "examples"))

from qnsim import Const, Create, Dispose, Exp, Model, Process  # noqa: E402
import demo_line  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUT, exist_ok=True)

N_RUNS = 10
TMOD = 100000.0
WARMUP = 1000.0


def mmc_lq(lam, mu, c):
    a = lam / mu
    rho = a / c
    s = sum(a ** k / math.factorial(k) for k in range(c))
    p0 = 1.0 / (s + a ** c / (math.factorial(c) * (1 - rho)))
    return p0 * a ** c * rho / (math.factorial(c) * (1 - rho) ** 2)


def replicate(builder, extract, n=N_RUNS, tmod=TMOD, warmup=WARMUP):
    vals = []
    for s in range(n):
        m = builder()
        m.rng.seed(1000 + s)
        r = m.simulate(tmod, warmup=warmup)
        vals.append(extract(r))
    mean = st.mean(vals)
    sd = st.stdev(vals) if n > 1 else 0.0
    half = 2.262 * sd / math.sqrt(n)   # t(0,975; 9) для 10 прогонів
    return mean, half


def check(rows, model, metric, analytic, sim):
    mean, half = sim
    err = abs(mean - analytic) / abs(analytic) * 100 if analytic else abs(mean) * 100
    ok = abs(mean - analytic) <= half or err < 2.0
    rows.append([model, metric, f"{analytic:.4f}", f"{mean:.4f}", f"±{half:.4f}",
                 f"{err:.2f}", "так" if ok else "ні"])
    print(f"{model:<38} {metric:<28} теор={analytic:9.4f} імітація={mean:9.4f} ±{half:.4f} "
          f"δ={err:5.2f}%  {'OK' if ok else '!!'}")


def analytic_checks():
    rows = []

    # 1. M/M/1, λ = 1, середній час обслуговування 0,8
    def b1():
        s, p, o = Create("Src", Exp(1.0)), Process("S", Exp(0.8)), Dispose("Out")
        s.to(p)
        p.to(o)
        return Model(s, p, o)
    lam, mu = 1.0, 1 / 0.8
    rho = lam / mu
    check(rows, "M/M/1 (λ=1; t=exp(0,8))", "Завантаження ρ", rho,
          replicate(b1, lambda r: r["S"]["utilization"]))
    check(rows, "M/M/1 (λ=1; t=exp(0,8))", "Середня черга Lq", rho ** 2 / (1 - rho),
          replicate(b1, lambda r: r["S"]["mean_queue"]))
    check(rows, "M/M/1 (λ=1; t=exp(0,8))", "Час перебування T", 1 / (mu - lam),
          replicate(b1, lambda r: r["Out"]["mean_time"]))

    # 2. M/M/3, λ = 1, середній час обслуговування 2,5
    def b2():
        s, p, o = Create("Src", Exp(1.0)), Process("S", Exp(2.5), channels=3), Dispose("Out")
        s.to(p)
        p.to(o)
        return Model(s, p, o)
    lq = mmc_lq(1.0, 0.4, 3)
    check(rows, "M/M/3 (λ=1; t=exp(2,5))", "Середня черга Lq", lq,
          replicate(b2, lambda r: r["S"]["mean_queue"]))
    check(rows, "M/M/3 (λ=1; t=exp(2,5))", "Середнє очікування Wq", lq / 1.0,
          replicate(b2, lambda r: r["S"]["mean_wait"]))
    check(rows, "M/M/3 (λ=1; t=exp(2,5))", "Завантаження каналу", 2.5 / 3,
          replicate(b2, lambda r: r["S"]["utilization"]))

    # 3. M/M/1/K через блокування маршруту від джерела (режим втрати)
    K = 3
    def b3():
        s = Create("Src", Exp(1.0), on_block="lose")
        p = Process("S", Exp(1 / 1.25), max_queue=K - 1)
        o = Dispose("Out")
        s.add_route(p, block="L(S) = 2 ∧ K(S) ≠ 0")
        p.to(o)
        return Model(s, p, o)
    r_ = 1.0 / 1.25
    p_loss = (1 - r_) * r_ ** K / (1 - r_ ** (K + 1))
    check(rows, "M/M/1/3 через блокування джерела", "Ймовірність втрати", p_loss,
          replicate(b3, lambda r: r["Src"]["p_lost"]))
    check(rows, "M/M/1/3 через блокування джерела", "Завантаження ρ", r_ * (1 - p_loss),
          replicate(b3, lambda r: r["S"]["utilization"]))

    # 4. Насичена двофазна лінія з накопичувачем B і блокуванням (BAS)
    for B in (0, 1, 3):
        def b5(B=B):
            s = Create("Src", Const(0.0), first=0.0, on_block="wait")
            p1 = Process("F1", Exp(1.0), max_queue=0)
            p2 = Process("F2", Exp(1.0), max_queue=B)
            o = Dispose("Out")
            s.add_route(p1, block="K(F1) ≠ 0")
            p1.add_route(p2, block=f"L(F2) = {B} ∧ K(F2) ≠ 0")
            p2.to(o)
            return Model(s, p1, p2, o)
        check(rows, f"Насичена лінія з блокуванням, B={B}", "Продуктивність",
              (B + 2) / (B + 3), replicate(b5, lambda r: r["Out"]["throughput"]))

    # 5. Часова умова блокування: перерва 10 хв щогодини
    def b6():
        s = Create("Src", Exp(1.0), on_block="lose")
        p = Process("S", Exp(0.5), channels=10)
        o = Dispose("Out")
        s.add_route(p, block="t mod 60 ∈ [50; 60)")
        p.to(o)
        return Model(s, p, o)
    check(rows, "Блокування за часовою умовою", "Частка втрачених вимог", 10 / 60,
          replicate(b6, lambda r: r["Src"]["p_lost"]))

    # 6. Дуга групування 4 → 1: на СМО надходить потік Ерланга 4-го порядку (E4/M/1)
    def b7():
        s, p, o = Create("Src", Exp(1.0)), Process("S", Exp(2.0)), Dispose("Out")
        s.add_route(p, group=4)
        p.to(o)
        return Model(s, p, o)
    # σ = (1 / (1 + μ(1 − σ)))^4,  μ = 0,5;  Wq = σ / (μ(1 − σ))
    sig = 0.5
    for _ in range(200):
        sig = (1 / (1 + 0.5 * (1 - sig))) ** 4
    check(rows, "Групування 4→1 (E4/M/1)", "Завантаження ρ", 0.5,
          replicate(b7, lambda r: r["S"]["utilization"]))
    check(rows, "Групування 4→1 (E4/M/1)", "Середнє очікування Wq", sig / (0.5 * (1 - sig)),
          replicate(b7, lambda r: r["S"]["mean_wait"]))

    # 7. Дуга розгрупування 1 → 3
    def b8():
        s, p, o = Create("Src", Exp(4.0)), Process("S", Exp(0.8)), Dispose("Out")
        s.add_route(p, split=3)
        p.to(o)
        return Model(s, p, o)
    check(rows, "Розгрупування 1→3", "Продуктивність", 0.75,
          replicate(b8, lambda r: r["Out"]["throughput"]))
    check(rows, "Розгрупування 1→3", "Завантаження ρ", 0.6,
          replicate(b8, lambda r: r["S"]["utilization"]))

    # 8. Мережа Джексона з ймовірнісними маршрутами між СМО і зворотним зв'язком
    def b9():
        s = Create("Src", Exp(1.0))
        s1, s2, s3 = Process("S1", Exp(0.5)), Process("S2", Exp(0.8)), Process("S3", Exp(1.0))
        o = Dispose("Out")
        s.to(s1)
        s1.add_route(s2, probability=0.6)
        s1.add_route(s3, probability=0.4)
        s2.add_route(s1, probability=0.2)
        s2.add_route(o, probability=0.8)
        s3.to(o)
        return Model(s, s1, s2, s3, o)
    l1 = 1.0 / (1 - 0.6 * 0.2)
    lam_j = {"S1": l1, "S2": 0.6 * l1, "S3": 0.4 * l1}
    mu_j = {"S1": 2.0, "S2": 1.25, "S3": 1.0}
    L_tot = 0.0
    for j in ("S1", "S2", "S3"):
        rj = lam_j[j] / mu_j[j]
        L_tot += rj / (1 - rj)
        check(rows, "Мережа Джексона (ймовірності між СМО)", f"Завантаження {j}", rj,
              replicate(b9, lambda r, j=j: r[j]["utilization"]))
    for j in ("S1", "S2"):
        rj = lam_j[j] / mu_j[j]
        check(rows, "Мережа Джексона (ймовірності між СМО)", f"Кількість вимог у {j}", rj / (1 - rj),
              replicate(b9, lambda r, j=j: r[j]["mean_queue"] + r[j]["utilization"]))
    check(rows, "Мережа Джексона (ймовірності між СМО)", "Час перебування T", L_tot / 1.0,
          replicate(b9, lambda r: r["Out"]["mean_time"]))

    with open(os.path.join(OUT, "verification_analytic.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Модель", "Характеристика", "Теоретичне", "Імітація", "Напівширина ДІ",
                    "Відхилення, %", "У межах ДІ / <2 %"])
        w.writerows(rows)
    return rows


def demo_verification():
    """Таблиця верифікації демонстраційної мережі (T = 30000 хв, 5 прогонів)."""
    cases = [
        ("Базовий варіант", {}),
        ("Інтервал надходження 2,4", {"t_arr": 2.4}),
        ("Інтервал надходження 1,8", {"t_arr": 1.8}),
        ("Час обробки FA 4,0", {"t_fa": 4.0}),
        ("Час обробки FA 1,5", {"t_fa": 1.5}),
        ("Без повернень (p_rw = 0)", {"p_rw": 0.0, "p_ok": 0.95}),
        ("KA = KB = 0", {"KA": 0, "KB": 0}),
        ("KA = KB = 6", {"KA": 6, "KB": 6}),
        ("Без техобслуговування (TO = 0)", {"TO": 0}),
        ("Техобслуговування TO = 120", {"TO": 120}),
        ("KC = 1", {"KC": 1}),
        ("KC = 6", {"KC": 6}),
        ("Пріоритети B>A>R", {"prio": "B>A>R"}),
        ("Без блокування до QC", {"qc_block": False}),
    ]
    rows = []
    for name, ch in cases:
        res = [demo_line.run(tmod=30000, warmup=2000, seed=s, **ch) for s in range(5)]
        mean = {k: st.mean(r[k] for r in res) for k in res[0]}
        rows.append([name, f"{mean['throughput']:.4f}", f"{mean['time']:.2f}", f"{mean['share_fa']:.3f}",
                     f"{mean['share_fb']:.3f}", f"{mean['share_fr']:.3f}", f"{mean['u_fa']:.3f}",
                     f"{mean['u_fb']:.3f}", f"{mean['u_fr']:.3f}", f"{mean['b_fa']:.3f}", f"{mean['p_fail_qc']:.3f}"])
        print(rows[-1])
    with open(os.path.join(OUT, "verification_demo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Варіант", "Продуктивність", "Час обробки", "Частка FA", "Частка FB", "Частка FR",
                    "ρ FA", "ρ FB", "ρ FR", "Блок. FA", "Відмови QC"])
        w.writerows(rows)
    return rows


VARIANTS = [
    ("V0", "Базовий варіант (B1, B2, B3, пріоритети A>B>R)", {}),
    ("V1", "Без блокування маршруту M1→FA (B1 відсутня)", {"cond_fa": None}),
    ("V2", "Без блокування маршруту M1→FB (B2 відсутня)", {"cond_fb": None}),
    ("V3", "Без блокування маршрутів до QC (B3 відсутня, відмова)", {"qc_block": False}),
    ("V4", "B2 без часової складової: L(FB) = KB ∧ K(FB) ≠ 0",
     {"cond_fb": "L(FB) = KB ∧ K(FB) ≠ 0"}),
    ("V5", "B2 з TO = 120 хв замість 30 хв", {"TO": 120}),
    ("V6", "B1 з меншим порогом: L(FA) ≥ 1 ∧ K(FA) ≠ 0",
     {"cond_fa": "L(FA) ≥ 1 ∧ K(FA) ≠ 0"}),
    ("V7", "B1 з часовою складовою: ... ∨ t mod 480 ∈ [0; 60)",
     {"cond_fa": "(L(FA) = KA ∧ K(FA) ≠ 0) ∨ t mod 480 ∈ [0; 60)"}),
    ("V8", "Пріоритети B>A>R", {"prio": "B>A>R"}),
    ("V9", "Пріоритети A=B>R (ймовірності 0,5 / 0,5)", {"prio": "A=B>R"}),
    ("V10", "Пріоритети A=B=R (ймовірності 0,5 / 0,35 / 0,15)", {"prio": "A=B=R"}),
    ("V11", "Пріоритети R>A>B", {"prio": "R>A>B"}),
]


def _variant_run(args):
    params, seed = args
    model = demo_line.build(seed=seed, **params)
    win = {"M1→FA": [0, 0], "M1→FB": [0, 0]}   # [вибори у вікні, усього]

    def hook(elem, route, t):
        if route is not None and route.name in win:
            ph = t % 480
            w = win[route.name]
            w[1] += 1
            if (route.name == "M1→FB" and ph >= 480 - params.get("TO", 30)) or \
               (route.name == "M1→FA" and ph < 60):
                w[0] += 1
    model.on_choice = hook
    r = model.simulate(30000.0, warmup=2000.0)
    rt = r["_model"]["routes"]
    used = {k: rt[k]["used"] for k in ("M1→FA", "M1→FB", "M1→FR")}
    tot = max(1, sum(used.values()))
    qc_in = r["QC"]["arrivals"]
    return {"fa": used["M1→FA"] / tot, "fb": used["M1→FB"] / tot, "fr": used["M1→FR"] / tot,
            "b_fa": r["FA"]["blocked_share"], "b_fb": r["FB"]["blocked_share"], "b_fr": r["FR"]["blocked_share"],
            "q_fa": r["FA"]["mean_queue"],
            "pf_qc": r["QC"]["failures"] / qc_in if qc_in else 0.0,
            "pf_fa": r["FA"]["p_fail"], "pf_fb": r["FB"]["p_fail"],
            "fb_win": win["M1→FB"][0], "fa_win": win["M1→FA"][0],
            "time": rt["QC→PK"]["mean_time"], "thr": 4 * r["Склад"]["throughput"]}


def variation_verification(n=5):
    """Верифікація пріоритетів і блокувань оцінюванням впливу змін на відгуки моделі."""
    from multiprocessing import Pool
    keys = ["fa", "fb", "fr", "b_fa", "b_fb", "b_fr", "q_fa", "pf_qc", "pf_fa", "pf_fb", "fb_win", "fa_win", "time", "thr"]
    rows = []
    with Pool(2) as pool:
        for code, name, params in VARIANTS:
            res = pool.map(_variant_run, [(params, 500 + s) for s in range(n)])
            avg = {k: st.mean(x[k] for x in res) for k in keys}
            rows.append([code, name] + [f"{avg[k]:.4f}" for k in keys])
            print(code, name, {k: round(avg[k], 3) for k in keys})
    with open(os.path.join(OUT, "verification_variation.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "variant"] + keys)
        w.writerows(rows)
    return rows


def protocol():
    m = demo_line.build(seed=7, trace=True, KA=1, KB=1, KC=1)
    m.simulate(480.0)
    with open(os.path.join(OUT, "protocol_demo.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(m.protocol))
    print(f"протокол: {len(m.protocol)} рядків")


if __name__ == "__main__":
    analytic_checks()
    demo_verification()
    variation_verification()
    protocol()
