"""Універсальний алгоритм імітації мережі масового обслуговування
з пріоритетом вибору маршруту та блокуванням маршруту за умовою.

Просування часу - до найближчої події; просування моделі - за подіями;
збір статистики - на інтервалах між послідовними подіями.
"""
import math
import random
from itertools import count

from .elements import Create, Dispose, Element, Job, Process

INF = math.inf


class Model:
    def __init__(self, *elements, seed=None, trace=False, event_order="priority",
                 trace_limit=100000, params=None, route_stats=False):
        """params      - значення констант, що використовуються в умовах блокування;
        route_stats - накопичувати тривалість блокування кожного маршруту."""
        if event_order not in ("priority", "random"):
            raise ValueError("event_order: 'priority' або 'random'")
        self.rng = random.Random(seed)
        self.elements = []
        self.tracing = trace
        self.trace_limit = trace_limit
        self.protocol = []
        self.event_order = event_order
        self.params = dict(params or {})
        self.route_stats = route_stats
        self.on_choice = None   # функція on_choice(element, route, t) - для аудиту рішень
        self.t = 0.0
        for e in elements:
            self.add(e)

    # ---- побудова --------------------------------------------------------
    def add(self, *elements):
        for e in elements:
            if not isinstance(e, Element):
                raise TypeError("елемент мережі має бути Create, Process або Dispose")
            if any(x.name == e.name for x in self.elements):
                raise ValueError(f"повторна назва елемента {e.name}")
            self.elements.append(e)
        return self

    def __getitem__(self, name):
        for e in self.elements:
            if e.name == name:
                return e
        raise KeyError(name)

    @property
    def routes(self):
        return [r for e in self.elements for r in e.routes]

    def validate(self):
        names = {id(e) for e in self.elements}
        for r in self.routes:
            if id(r.target) not in names:
                raise ValueError(f"маршрут {r.name} веде до елемента, що не доданий у модель")
        if not any(isinstance(e, Create) for e in self.elements):
            raise ValueError("у мережі немає джерела надходження вимог")
        for r in self.routes:        # розбір і прив'язка умов блокування до елементів
            if r.block is not None:
                r.block.bind(self)

    # ---- службові --------------------------------------------------------
    def log(self, t, text):
        if len(self.protocol) < self.trace_limit:
            self.protocol.append(f"{t:12.4f} | {text}")

    def new_job(self, t, jtype=0, priority=0):
        self.n_jobs += 1
        return Job(self.n_jobs, t, jtype, priority)

    def register_blocked(self, element, channel, t):
        self.blocked.append([t, next(self._bseq), element, channel])

    def exit(self, job, t, src):
        self.n_exit += 1
        self.exit_time_sum += t - job.t_create
        if self.tracing:
            self.log(t, f"{src.name}: вимога {job} залишила мережу")

    def release_blocked(self, t):
        """Перегляд заблокованих елементів у порядку часу блокування.
        Після кожного успішного зняття блокування стан мережі змінився,
        тому перегляд починається спочатку (каскадне розблокування)."""
        progress = True
        while progress and self.blocked:
            progress = False
            for i, entry in enumerate(self.blocked):
                if entry[2].try_release(entry, t):
                    del self.blocked[i]
                    progress = True
                    break

    def _advance(self, dt):
        if dt > 0:
            for e in self.elements:
                e.update_stats(dt)
            if self.route_stats:
                t = self.t
                for r in self._cond_routes:
                    if r.block(self, t):
                        r.blocked_time += dt

    def _reset(self):
        for e in self.elements:
            e.reset_stats()
        for r in self.routes:
            r.reset_stats()
        self.n_exit = 0
        self.exit_time_sum = 0.0

    # ---- алгоритм імітації -----------------------------------------------
    def simulate(self, tmod, warmup=0.0, max_events_per_moment=100000,
                 observer=None, observe_every=None):
        """Імітація на інтервалі [0; tmod].

        warmup   - тривалість перехідного періоду, статистика за який
                   відкидається;
        observer - функція observer(model, t), що викликається з кроком
                   observe_every модельного часу (для дослідження динаміки
                   відгуку, зокрема перехідного періоду)."""
        self.validate()
        self.t = 0.0
        self.n_jobs = 0
        self.n_events = 0
        self.blocked = []
        self._bseq = count()
        self.protocol = []
        for e in self.elements:
            e.init(self)
        for r in self.routes:
            r.buffer = []
        self._reset()
        self._cond_routes = [r for r in self.routes if r.block is not None]
        # умови, значення яких залежить від часу, породжують власні події
        timers = [r.block for r in self._cond_routes if r.block.uses_t]
        processes = [e for e in self.elements if not isinstance(e, Create)]
        creates = [e for e in self.elements if isinstance(e, Create)]
        ordered = processes + creates
        stats_reset = warmup <= 0
        self.t_stat0 = 0.0
        t_obs = observe_every if observer else INF

        while True:
            # 1) момент найближчої події
            tnext = INF
            for e in self.elements:
                if e.tnext < tnext:
                    tnext = e.tnext
            tcond = min((c.next_change(self.t) for c in timers), default=INF)
            tn = min(tnext, tcond)
            # відкидання перехідного періоду
            if not stats_reset and tn >= warmup:
                self._advance(warmup - self.t)
                self.t = warmup
                self._reset()
                self.t_stat0 = warmup
                stats_reset = True
            while t_obs <= min(tn, tmod):
                self._advance(t_obs - self.t)
                self.t = t_obs
                observer(self, t_obs)
                t_obs += observe_every
            if tn > tmod:
                # 2) статистика на останньому інтервалі
                self._advance(tmod - self.t)
                self.t = tmod
                break
            # 2) статистика на інтервалі [t, tn)
            self._advance(tn - self.t)
            # 3) просування часу
            prev_t = self.t
            self.t = t = tn
            # 4) зміна стану моделі
            guard = 0
            while True:
                if self.event_order == "random":
                    due = [e for e in self.elements if e.tnext <= t]
                    self.rng.shuffle(due)
                else:
                    due = [e for e in ordered if e.tnext <= t]
                if not due:
                    break
                for e in due:
                    if e.tnext <= t:
                        self.n_events += 1
                        e.on_event(t)
                self.release_blocked(t)
                guard += 1
                if guard > max_events_per_moment:
                    raise RuntimeError("нескінченний цикл подій з нульовими затримками")
            if tcond <= t:
                self.n_events += 1
                if self.tracing:
                    names = ", ".join(r.name for r in self._cond_routes
                                      if r.block.uses_t and r.block.next_change(prev_t) <= t)
                    self.log(t, f"зміна значення умови блокування за часом (маршрут {names})")
                self.release_blocked(t)
        self.T_stat = tmod - self.t_stat0
        return self.results()

    # ---- результати --------------------------------------------------------
    def results(self):
        T = self.T_stat
        res = {e.name: e.results(T) for e in self.elements}
        n_out = self.n_exit + sum(e.count for e in self.elements if isinstance(e, Dispose))
        ts_sum = self.exit_time_sum + sum(e.ts_sum for e in self.elements if isinstance(e, Dispose))
        res["_model"] = {
            "T": T,
            "events": self.n_events,
            "jobs_created": self.n_jobs,
            "jobs_out": n_out,
            "throughput": n_out / T if T > 0 else 0.0,
            "mean_time_in_system": ts_sum / n_out if n_out else 0.0,
            "in_system_end": sum(e.in_element for e in self.elements) + sum(len(r.buffer) for r in self.routes),
            "routes": {r.name: {"used": r.n_used, "blocked_checks": r.n_blocked_checks,
                                "mean_time": r.ts_sum / r.n_used if r.n_used else 0.0,
                                "blocked_share": r.blocked_time / T if T > 0 else 0.0}
                       for r in self.routes},
        }
        return res

    def report(self, res=None):
        res = res or self.results()
        lines = [f"Час моделювання (збір статистики): {res['_model']['T']:.2f}"]
        for e in self.elements:
            r = res[e.name]
            if isinstance(e, Process):
                lines.append(
                    f"{e.name:>10}: обсл.={r['served']:6d} відм.={r['failures']:5d} "
                    f"Lсер={r['mean_queue']:7.3f} Lmax={r['max_queue']:4d} "
                    f"ρ={r['utilization']:.4f} блок={r['blocked_share']:.4f} "
                    f"Wсер={r['mean_wait']:.3f}")
            elif isinstance(e, Create):
                lines.append(f"{e.name:>10}: створено={r['created']} втрачено={r['lost']} "
                             f"частка призупинення={r['suspended_share']:.4f}")
            elif isinstance(e, Dispose):
                lines.append(f"{e.name:>10}: вийшло={r['count']} продуктивність={r['throughput']:.4f} "
                             f"Tсер={r['mean_time']:.3f} σ={r['std_time']:.3f} Tmax={r['max_time']:.3f}")
        m = res["_model"]
        lines.append(f"Подій: {m['events']}, продуктивність мережі {m['throughput']:.4f}, "
                     f"середній час перебування {m['mean_time_in_system']:.3f}")
        return "\n".join(lines)
