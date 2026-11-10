"""Експериментальне дослідження універсального алгоритму імітації.

Е1. Перехідний період і тривалість прогону (формула 3.1 посібника).
Е2. Кількість повторних прогонів для заданої точності (формула 3.5).
Е3. Перевірка правильності виконання пріоритетів і блокувань: кожне рішення
    про вибір маршруту перевіряється незалежним кодом, що аналізує стан СМО
    безпосередньо (без мови умов); перевірка ймовірностей критерієм χ²;
    перевірка дуги групування; частки часу блокування маршрутів.
Е4. Вплив порядку пріоритетів гілок на відгуки (дисперсійний аналіз).
Е5. Вплив параметрів умов блокування: ємностей KA = KB, тривалості
    техобслуговування TO у часовій умові, ємності KC (регресійний аналіз).
Е6. Блокування маршруту проти відмови в обслуговуванні.
Е7. Обчислювальна складність: від часу моделювання, кількості СМО та
    кількості гілок у розгалуженні з пріоритетами й умовами.
"""
import csv
import json
import math
import os
import statistics as st
import sys
import time
from multiprocessing import Pool

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "examples"))

from qnsim import Create, Dispose, Exp, Model, Process  # noqa: E402
import demo_line  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUT, exist_ok=True)

EPS_T = 1.5        # точність оцінювання середнього часу обробки деталі, хв
WARMUP = 2000.0    # перехідний період (Е1)
N_RUNS = 20        # прогонів в одному експерименті (Е2)
TMOD = None        # тривалість прогону - визначається в Е1


def save_csv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def regress(x, y, deg=1):
    x, y = np.asarray(x, float), np.asarray(y, float)
    X = np.column_stack([x ** k for k in range(deg + 1)])
    b = np.linalg.inv(X.T @ X) @ X.T @ y
    yhat = X @ b
    R = math.sqrt(max(0.0, 1 - ((y - yhat) ** 2).sum() / ((y - y.mean()) ** 2).sum()))
    return b.tolist(), R


# ---------------- Е1 ------------------------------------------------------
def transient(seeds=(1, 2, 3, 4, 5, 6), tmod=150000.0, step=1000.0):
    curves = {}
    for s in seeds:
        m = demo_line.build(seed=s)
        r = next(x for x in m.routes if x.name == "QC→PK")
        pts = []
        m.simulate(tmod, observe_every=step,
                   observer=lambda mm, t, pts=pts, r=r: pts.append(r.ts_sum / r.n_used if r.n_used else 0.0))
        curves[s] = pts
    ts = [step * (i + 1) for i in range(len(curves[seeds[0]]))]
    spread = [max(curves[s][i] for s in seeds) - min(curves[s][i] for s in seeds) for i in range(len(ts))]
    T_est = next((ts[i] for i in range(len(ts)) if all(sp < EPS_T for sp in spread[i:])), tmod)
    save_csv("transient.csv", ["t"] + [f"seed{s}" for s in seeds] + ["spread"],
             [[t] + [curves[s][i] for s in seeds] + [spread[i]] for i, t in enumerate(ts)])
    procs = ("M1", "FA", "FB", "FR", "QC")
    ens = []
    for s in range(40):
        m = demo_line.build(seed=300 + s)
        pts = []
        m.simulate(6000.0, observe_every=50.0,
                   observer=lambda mm, t, pts=pts: pts.append(sum(mm[n].in_element for n in procs)))
        ens.append(pts)
    save_csv("transient_ensemble.csv", ["t", "L_mean"],
             [[50.0 * (i + 1), v] for i, v in enumerate(np.mean(ens, axis=0))])
    return {"T_est": T_est, "seeds": list(seeds), "step": step}


# ---------------- допоміжне для пулу --------------------------------------
def _run(args):
    seed, params = args
    return demo_line.run(tmod=TMOD, warmup=WARMUP, seed=seed, **params)


def series(pool, params, n=N_RUNS, base_seed=100):
    return pool.map(_run, [(base_seed + s, params) for s in range(n)])


def mean_of(res, keys=("time", "L", "throughput", "share_fa", "share_fb", "share_fr",
                       "b_fa", "b_fb", "b_fr", "u_fa", "u_fb", "u_fr", "q_fr", "p_fail_qc")):
    return {k: st.mean(r[k] for r in res) for k in keys}


# ---------------- Е2 ------------------------------------------------------
def n_runs_study(pool, n=20):
    res = series(pool, {}, n, 100)
    out = {}
    for key, eps in (("time", EPS_T), ("L", 0.7), ("throughput", 0.002)):
        v = [r[key] for r in res]
        sd = st.stdev(v)
        out[key] = {"mean": st.mean(v), "sd": sd, "eps": eps, "p_required": math.ceil(20 * (sd / eps) ** 2)}
    return out


# ---------------- Е3: незалежна перевірка рішень --------------------------
def _audit(seed):
    P = demo_line.DEFAULTS
    KA, KB, KC, TO = P["KA"], P["KB"], P["KC"], P["TO"]
    m = demo_line.build(seed=seed, route_stats=True)
    FA, FB, QC = m["FA"], m["FB"], m["QC"]

    def full(e, cap):   # незалежна від мови умов перевірка «СМО заповнена»
        return len(e.queue) >= cap and e.channels[0].state != 0

    cnt = {"M1": [0, 0], "toQC": [0, 0], "fb_in_maint": 0, "M1_choice": {"M1→FA": 0, "M1→FB": 0, "M1→FR": 0},
           "QC": {"QC→PK": 0, "QC→M1": 0, "QC→Брак": 0}, "blocked_toQC": 0}

    def on_choice(el, route, t):
        if el.name == "M1":
            maint = (t % 480.0) >= 480.0 - TO
            if not full(FA, KA):
                exp = "M1→FA"
            elif not (full(FB, KB) or maint):
                exp = "M1→FB"
            else:
                exp = "M1→FR"
            cnt["M1"][0] += 1
            cnt["M1"][1] += (route is None or route.name != exp)
            if route is not None:
                cnt["M1_choice"][route.name] += 1
                cnt["fb_in_maint"] += (route.name == "M1→FB" and maint)
        elif el.name in ("FA", "FB", "FR"):
            qc_full = full(QC, KC)
            cnt["toQC"][0] += 1
            cnt["toQC"][1] += ((route is None) != qc_full)
            cnt["blocked_toQC"] += route is None
        elif el.name == "QC":
            cnt["QC"][route.name] += 1

    m.on_choice = on_choice
    r = m.simulate(TMOD, warmup=WARMUP)
    rt = r["_model"]["routes"]
    # перевірка дуги групування: прогін без відкидання перехідного періоду
    m2 = demo_line.build(seed=seed)
    r2 = m2.simulate(30000.0)
    grp = next(x for x in m2.routes if x.name == "QC→PK")
    used, packs = r2["_model"]["routes"]["QC→PK"]["used"], r2["PK"]["arrivals"]
    group_ok = used == 4 * packs + len(grp.buffer)
    return cnt, {k: v["blocked_share"] for k, v in rt.items()}, group_ok, packs, used


def audit(pool, n=N_RUNS):
    res = pool.map(_audit, [700 + s for s in range(n)])
    tot = {"M1": [0, 0], "toQC": [0, 0], "fb_in_maint": 0, "blocked_toQC": 0,
           "M1_choice": {"M1→FA": 0, "M1→FB": 0, "M1→FR": 0}, "QC": {"QC→PK": 0, "QC→M1": 0, "QC→Брак": 0}}
    bshare = {}
    for cnt, bs, gok, _, _ in res:
        for k in ("M1", "toQC"):
            tot[k][0] += cnt[k][0]
            tot[k][1] += cnt[k][1]
        tot["fb_in_maint"] += cnt["fb_in_maint"]
        tot["blocked_toQC"] += cnt["blocked_toQC"]
        for k in tot["M1_choice"]:
            tot["M1_choice"][k] += cnt["M1_choice"][k]
        for k in tot["QC"]:
            tot["QC"][k] += cnt["QC"][k]
        for k, v in bs.items():
            bshare.setdefault(k, []).append(v)
    obs = [tot["QC"][k] for k in ("QC→PK", "QC→M1", "QC→Брак")]
    exp = [sum(obs) * p for p in (0.85, 0.10, 0.05)]
    chi2 = sum((o - e) ** 2 / e for o, e in zip(obs, exp))
    tot["chi2"] = chi2
    tot["chi2_crit"] = float(stats.chi2.ppf(0.95, 2))
    tot["chi2_p"] = float(1 - stats.chi2.cdf(chi2, 2))
    tot["group_ok"] = all(x[2] for x in res)
    tot["packs"] = sum(x[3] for x in res)
    tot["parts_to_pk"] = sum(x[4] for x in res)
    tot["blocked_share"] = {k: st.mean(v) for k, v in bshare.items()}
    return tot


# ---------------- Е4: пріоритети -----------------------------------------
def priorities(pool):
    levels = ["A>B>R", "B>A>R", "A=B>R", "A=B=R"]
    groups = {lv: series(pool, {"prio": lv}, base_seed=900) for lv in levels}
    out = {"levels": levels, "means": {lv: mean_of(groups[lv]) for lv in levels},
           "sds": {lv: st.stdev(r["time"] for r in groups[lv]) for lv in levels}}
    for key in ("time", "throughput"):
        data = [[r[key] for r in groups[lv]] for lv in levels]
        q, p = len(data), len(data[0])
        mj = [st.mean(d) for d in data]
        gm = st.mean(mj)
        Df = p * sum((m - gm) ** 2 for m in mj) / (q - 1)
        Dr = sum((x - m) ** 2 for d, m in zip(data, mj) for x in d) / (q * (p - 1))
        F = Df / Dr
        out[key] = {"D_f": Df, "D_r": Dr, "F": F, "F_crit": float(stats.f.ppf(0.95, q - 1, q * (p - 1))),
                    "p_value": float(1 - stats.f.cdf(F, q - 1, q * (p - 1)))}
    rows = [[lv, i + 1, r["time"], r["throughput"], r["share_fa"], r["share_fb"], r["share_fr"]]
            for lv in levels for i, r in enumerate(groups[lv])]
    save_csv("priorities.csv", ["prio", "run", "time", "throughput", "share_fa", "share_fb", "share_fr"], rows)
    # окремо: найвищий пріоритет у гілки без блокування - нестійкий режим
    unst = [demo_line.run(tmod=30000, warmup=0, seed=s, prio="R>A>B") for s in range(3)]
    out["R>A>B"] = mean_of(unst)
    return out


# ---------------- Е5: параметри умов --------------------------------------
def sweep(pool, name, values, build_params):
    rows, res = [], {}
    for v in values:
        rr = series(pool, build_params(v), base_seed=1100)
        mm = mean_of(rr)
        mm["time_sd"] = st.stdev(r["time"] for r in rr)
        res[v] = mm
        rows.append([v] + [mm[k] for k in ("time", "time_sd", "L", "throughput", "share_fa", "share_fb",
                                           "share_fr", "b_fa", "b_fb", "b_fr", "q_fr", "p_fail_qc")])
    save_csv(f"sweep_{name}.csv", [name, "time", "time_sd", "L", "throughput", "share_fa", "share_fb",
                                   "share_fr", "b_fa", "b_fb", "b_fr", "q_fr", "p_fail_qc"], rows)
    return res


def conditions(pool):
    out = {}
    out["K"] = sweep(pool, "K", [0, 1, 2, 3, 4, 6], lambda v: {"KA": v, "KB": v})
    out["TO"] = sweep(pool, "TO", [0, 15, 30, 60, 90, 120], lambda v: {"TO": v})
    out["KC"] = sweep(pool, "KC", [1, 2, 3, 4, 5, 6], lambda v: {"KC": v})
    to = sorted(out["TO"])
    out["reg_TO_share_fb"] = regress(to, [out["TO"][v]["share_fb"] for v in to])
    out["reg_TO_share_fr"] = regress(to, [out["TO"][v]["share_fr"] for v in to])
    out["reg_TO_time"] = regress(to, [out["TO"][v]["time"] for v in to], deg=2)
    return out


# ---------------- Е6: блокування проти відмови ---------------------------
def block_vs_refuse(pool):
    out = {"block": {}, "refuse": {}}
    rows = []
    for kc in (1, 2, 3, 4, 5):
        for mode, flag in (("block", True), ("refuse", False)):
            mm = mean_of(series(pool, {"KC": kc, "qc_block": flag}, base_seed=1300))
            out[mode][kc] = mm
            rows.append([kc, mode, mm["time"], mm["throughput"], mm["p_fail_qc"], mm["b_fa"], mm["L"]])
    save_csv("block_vs_refuse.csv", ["KC", "mode", "time", "throughput", "p_fail_qc", "b_fa", "L"], rows)
    return out


# ---------------- Е7: складність ------------------------------------------
def tandem(n, seed=1):
    src = Create("Src", Exp(1.0))
    st_ = [Process(f"S{i}", Exp(0.7), max_queue=(math.inf if i == 0 else 2)) for i in range(n)]
    out = Dispose("Out")
    src.to(st_[0])
    for a, b in zip(st_, st_[1:]):
        a.add_route(b, block=f"L({b.name}) = 2 ∧ K({b.name}) ≠ 0")
    st_[-1].to(out)
    return Model(src, *st_, out, seed=seed)


def fan(n, seed=1):
    """Розгалуження на n гілок з пріоритетами n, n-1, …, 1 і умовами блокування;
    остання гілка - без блокування."""
    src = Create("Src", Exp(0.25))
    hub = Process("H", Exp(0.2))
    br = [Process(f"B{i}", Exp(1.0 + 0.2 * i), max_queue=1) for i in range(n)]
    out = Dispose("Out")
    src.to(hub)
    for i, b in enumerate(br):
        cond = None if i == n - 1 else f"L(B{i}) = 1 ∧ K(B{i}) ≠ 0"
        hub.add_route(b, priority=n - i, block=cond)
        b.to(out)
    br[-1].max_queue = math.inf
    return Model(src, hub, *br, out, seed=seed)


def _timeit(build, tmod, reps=3):
    times, ev = [], []
    for s in range(reps):
        m = build(s)
        t0 = time.perf_counter()
        r = m.simulate(tmod)
        times.append(time.perf_counter() - t0)
        ev.append(r["_model"]["events"])
    return st.mean(ev), st.mean(times)


def complexity():
    rows_T = []
    for T in (5000, 10000, 20000, 40000, 80000):
        ev, ct = _timeit(lambda s: demo_line.build(seed=s), float(T))
        rows_T.append([T, ev, ct, ev / ct])
    rows_N = []
    for n in (1, 2, 5, 10, 20, 30, 40, 50, 60):
        ev, ct = _timeit(lambda s: tandem(n, s), 5000.0)
        rows_N.append([n, ev, ct, ct / ev * 1e6])
    rows_B = []
    for n in (2, 4, 8, 16, 32, 64):
        ev, ct = _timeit(lambda s: fan(n, s), 20000.0)
        rows_B.append([n, ev, ct, ct / ev * 1e6])
    save_csv("complexity_T.csv", ["Tmod", "events", "cpu_s", "events_per_s"], rows_T)
    save_csv("complexity_N.csv", ["N", "events", "cpu_s", "us_per_event"], rows_N)
    save_csv("complexity_B.csv", ["branches", "events", "cpu_s", "us_per_event"], rows_B)
    return {"rows_T": rows_T, "rows_N": rows_N, "rows_B": rows_B,
            "reg_T": regress([r[0] for r in rows_T], [r[2] for r in rows_T]),
            "reg_N": regress([r[0] for r in rows_N], [r[2] for r in rows_N], deg=2),
            "reg_N_event": regress([r[0] for r in rows_N], [r[3] for r in rows_N]),
            "reg_B_event": regress([r[0] for r in rows_B], [r[3] for r in rows_B])}


def proposals(pool, variants):
    out = {}
    for name, params in variants.items():
        out[name] = mean_of(series(pool, params, base_seed=1500))
        out[name]["params"] = params
    return out


if __name__ == "__main__":
    summary = {}
    t0 = time.time()
    summary["transient"] = transient()
    TMOD = float(max(50000, math.ceil(summary["transient"]["T_est"] / 10000) * 10000))
    summary["TMOD"] = TMOD
    print("Е1", summary["transient"], TMOD, time.time() - t0, flush=True)
    with Pool(2) as pool:
        summary["n_runs"] = n_runs_study(pool)
        print("Е2", summary["n_runs"], time.time() - t0, flush=True)
        summary["audit"] = audit(pool)
        print("Е3", summary["audit"], time.time() - t0, flush=True)
        summary["priorities"] = priorities(pool)
        print("Е4", {k: v for k, v in summary["priorities"].items() if k in ("time", "throughput")}, time.time() - t0, flush=True)
        summary["conditions"] = conditions(pool)
        print("Е5", time.time() - t0, flush=True)
        summary["block_vs_refuse"] = block_vs_refuse(pool)
        print("Е6", time.time() - t0, flush=True)
    summary["complexity"] = complexity()
    print("Е7", {k: v for k, v in summary["complexity"].items() if k.startswith("reg")}, time.time() - t0, flush=True)
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print("готово за", time.time() - t0, "с")
