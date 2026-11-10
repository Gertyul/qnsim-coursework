"""Демонстраційна мережа: ділянка механічної обробки деталей.

У мережі поєднано всі види розгалужень маршруту:
  * M1 → FA / FB / FR - розгалуження за пріоритетом на три гілки:
      FA (r = 3) - з блокуванням за станом СМО FA;
      FB (r = 2) - з блокуванням за станом СМО FB або за часом
                   (технічне обслуговування в кінці кожної зміни);
      FR (r = 1) - резервна ручна обробка, гілка лише з пріоритетом, без блокування;
  * FA, FB, FR → QC - маршрути з блокуванням за станом СМО QC
    (якщо накопичувач контролю заповнений, верстат утримує деталь);
  * QC → PK / M1 / Брак - розгалуження з ймовірностями 0,85 / 0,10 / 0,05;
  * QC → PK - дуга з числовим параметром 4 (чотири деталі пакуються в одну упаковку).
Час - у хвилинах.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qnsim import Create, Dispose, Exp, Model, Process  # noqa: E402

COND_FA = "L(FA) = KA ∧ K(FA) ≠ 0"
COND_FB = "(L(FB) = KB ∧ K(FB) ≠ 0) ∨ t mod 480 ∈ [480 − TO; 480)"
COND_QC = "L(QC) = KC ∧ K(QC) ≠ 0"

DEFAULTS = dict(
    t_arr=2.0,    # середній інтервал надходження заготовок
    t_m1=1.4,     # токарна обробка M1
    t_fa=2.5,     # фрезерування на сучасному верстаті FA
    t_fb=4.0,     # фрезерування на старому верстаті FB
    t_fr=6.0,     # резервна ручна обробка FR
    t_qc=1.4,     # контроль якості
    t_pk=4.0,     # пакування упаковки
    KA=2, KB=2, KC=3,   # ємності накопичувачів перед FA, FB, QC
    TO=30,        # тривалість техобслуговування FB наприкінці 480-хвилинної зміни
    p_ok=0.85, p_rw=0.10, p_sc=0.05,   # ймовірності на виході QC
    prio="A>B>R",  # порядок пріоритетів гілок з M1
    qc_block=True,  # маршрути до QC блокуються (False - деталь отримує відмову)
    cond_fa=COND_FA,  # умова блокування M1→FA (None - маршрут без блокування)
    cond_fb=COND_FB,  # умова блокування M1→FB (None - маршрут без блокування)
)

# порядки пріоритетів гілок з M1: (r_FA, p_FA), (r_FB, p_FB), (r_FR, p_FR)
PRIO = {
    "A>B>R": ((3, 1.0), (2, 1.0), (1, 1.0)),
    "B>A>R": ((2, 1.0), (3, 1.0), (1, 1.0)),
    "A=B>R": ((2, 0.5), (2, 0.5), (1, 1.0)),
    "A=B=R": ((1, 0.5), (1, 0.35), (1, 0.15)),
    "R>A>B": ((2, 1.0), (1, 1.0), (3, 1.0)),
}

def build(seed=None, trace=False, route_stats=False, **params):
    p = dict(DEFAULTS)
    p.update(params)
    src = Create("Надходження", Exp(p["t_arr"]))
    m1 = Process("M1", Exp(p["t_m1"]))
    fa = Process("FA", Exp(p["t_fa"]), max_queue=p["KA"])
    fb = Process("FB", Exp(p["t_fb"]), max_queue=p["KB"])
    fr = Process("FR", Exp(p["t_fr"]))
    qc = Process("QC", Exp(p["t_qc"]), max_queue=p["KC"])
    pk = Process("PK", Exp(p["t_pk"]))
    store = Dispose("Склад")
    scrap = Dispose("Брак")

    src.to(m1)
    (ra, pa), (rb, pb), (rr, pr) = PRIO[p["prio"]]
    m1.add_route(fa, priority=ra, probability=pa, block=p["cond_fa"], name="M1→FA")
    m1.add_route(fb, priority=rb, probability=pb, block=p["cond_fb"].replace("−", "-") if p["cond_fb"] else None, name="M1→FB")
    m1.add_route(fr, priority=rr, probability=pr, name="M1→FR")
    cq = COND_QC if p["qc_block"] else None
    for x in (fa, fb, fr):
        x.add_route(qc, block=cq, name=f"{x.name}→QC")
    qc.add_route(pk, probability=p["p_ok"], group=4, name="QC→PK")
    qc.add_route(m1, probability=p["p_rw"], name="QC→M1")
    qc.add_route(scrap, probability=p["p_sc"], name="QC→Брак")
    pk.add_route(store, name="PK→Склад")
    consts = {k: p[k] for k in ("KA", "KB", "KC", "TO")}
    return Model(src, m1, fa, fb, fr, qc, pk, store, scrap, seed=seed, trace=trace,
                 params=consts, route_stats=route_stats)


def run(tmod=10000.0, warmup=0.0, seed=None, **params):
    """Один прогін; повертає словник відгуків моделі."""
    model = build(seed=seed, **params)
    r = model.simulate(tmod, warmup=warmup)
    rt = r["_model"]["routes"]
    used = {k: rt[k]["used"] for k in ("M1→FA", "M1→FB", "M1→FR")}
    tot = max(1, sum(used.values()))
    procs = ("M1", "FA", "FB", "FR", "QC")
    L = sum(r[n]["mean_queue"] + (r[n]["utilization"] + r[n]["blocked_share"]) * model[n].m for n in procs)
    qc_in = r["QC"]["arrivals"]
    return {
        "time": rt["QC→PK"]["mean_time"],          # час обробки придатної деталі (до пакування), хв
        "L": L,                                      # середня кількість деталей на ділянці
        "throughput": 4 * r["Склад"]["throughput"],  # придатних деталей / хв
        "scrap": r["Брак"]["throughput"],
        "share_fa": used["M1→FA"] / tot, "share_fb": used["M1→FB"] / tot, "share_fr": used["M1→FR"] / tot,
        "q_m1": r["M1"]["mean_queue"], "q_fr": r["FR"]["mean_queue"],
        "u_m1": r["M1"]["utilization"], "u_fa": r["FA"]["utilization"], "u_fb": r["FB"]["utilization"],
        "u_fr": r["FR"]["utilization"], "u_qc": r["QC"]["utilization"], "u_pk": r["PK"]["utilization"],
        "b_fa": r["FA"]["blocked_share"], "b_fb": r["FB"]["blocked_share"], "b_fr": r["FR"]["blocked_share"],
        "p_fail_qc": r["QC"]["failures"] / qc_in if qc_in else 0.0,
        "T": r["_model"]["T"], "events": r["_model"]["events"],
    }


if __name__ == "__main__":
    model = build(seed=12345)
    res = model.simulate(20000.0, warmup=2000.0)
    print(model.report(res))
    for k, v in res["_model"]["routes"].items():
        print(f"{k:>10}: обрано {v['used']:6d}, час у мережі {v['mean_time']:.2f}")
