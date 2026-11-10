"""Елементи мережі масового обслуговування.

Create   - надходження вимог ззовні;
Process  - система масового обслуговування (СМО): m ідентичних каналів
           з чергою обмеженої або необмеженої довжини;
Dispose  - вихід вимог з мережі (збір статистики часу перебування);
Route    - дуга маршруту з пріоритетом, ймовірністю, умовою блокування
           та числовим параметром групування/розгрупування.

Стан каналу обслуговування K ∈ {0, 1, 2}:
    0 - вільний, 1 - зайнятий обслуговуванням, 2 - заблокований
    (обслуговування завершено, але вийти з каналу неможливо, бо всі
    маршрути на виході заблоковані).
"""
import heapq
import math
from collections import deque
from itertools import count

from .conditions import as_condition
from .distributions import as_delay

INF = math.inf
FREE, BUSY, BLOCKED = 0, 1, 2


class Job:
    """Вимога (запит, деталь, повідомлення), що рухається мережею."""
    __slots__ = ("id", "t_create", "t_enter", "type", "priority", "attrs", "pending")

    def __init__(self, jid, t, jtype=0, priority=0):
        self.id = jid
        self.t_create = t
        self.t_enter = t
        self.type = jtype
        self.priority = priority
        self.attrs = {}
        self.pending = None      # маршрут, обраний у строгому ймовірнісному режимі

    def __repr__(self):
        return f"#{self.id}"


class Route:
    """Дуга маршруту від елемента до наступної СМО.

    priority    - пріоритет вибору маршруту (число, що стоїть на маршруті);
                  більше значення - вищий пріоритет;
    probability - відносна вага (ймовірність) вибору серед маршрутів
                  однакового пріоритету;
    block       - умова блокування B(S, t): логіко-алгебраїчний вираз
                  (рядок або Condition), напр. "L(FA) = KA ∧ K(FA) ≠ 0";
    group       - дуга з числовим параметром k: k вимог, що пройшли дугою,
                  об'єднуються в одну (групування);
    split       - дуга з параметром 1/k: одна вимога перетворюється на k
                  ідентичних (розгрупування).
    """

    def __init__(self, source, target, priority=0, probability=1.0,
                 block=None, group=1, split=1, name=None):
        if callable(priority) or not isinstance(priority, (int, float)):
            raise TypeError("пріоритет маршруту задається числом")
        if probability < 0:
            raise ValueError("ймовірність не може бути від'ємною")
        if group < 1 or split < 1 or (group > 1 and split > 1):
            raise ValueError("дуга або групує (group=k), або розгруповує (split=k)")
        self.source = source
        self.target = target
        self.priority = priority
        self.probability = float(probability)
        self.block = as_condition(block)
        self.group = int(group)
        self.split = int(split)
        self.name = name or f"{source.name}→{target.name}"
        self.buffer = []
        self.reset_stats()

    def reset_stats(self):
        self.n_used = 0            # скільки разів маршрут обрано
        self.n_blocked_checks = 0  # скільки разів маршрут виявився заблокованим при виборі
        self.ts_sum = 0.0          # сумарний час перебування в мережі вимог, що пройшли дугою
        self.blocked_time = 0.0    # тривалість блокування (у режимі route_stats)

    def is_blocked(self, model, t):
        return self.block is not None and self.block(model, t)

    def describe(self):
        parts = [self.name, f"r = {self.priority:g}"]
        if self.probability != 1.0:
            parts.append(f"p = {self.probability:g}")
        if self.block is not None:
            parts.append(f"B: {self.block.text}")
        if self.group > 1:
            parts.append(f"групування {self.group}")
        if self.split > 1:
            parts.append(f"розгрупування 1/{self.split}")
        return ", ".join(parts)


class Element:
    """Базовий клас елемента мережі."""

    def __init__(self, name, routing="redistribute", tie="prob", on_block="block"):
        if routing not in ("redistribute", "strict"):
            raise ValueError("routing: 'redistribute' або 'strict'")
        if tie not in ("prob", "first"):
            raise ValueError("tie: 'prob' або 'first'")
        self.name = name
        self.routing = routing
        self.tie = tie
        self.on_block = on_block
        self.routes = []
        self.model = None
        self.tnext = INF

    # ---- маршрутизація --------------------------------------------------
    def add_route(self, target, priority=0, probability=1.0, block=None,
                  group=1, split=1, name=None):
        r = Route(self, target, priority, probability, block, group, split, name)
        self.routes.append(r)
        return r

    def to(self, target, **kw):
        """Скорочений запис add_route, повертає self для ланцюжкового опису."""
        self.add_route(target, **kw)
        return self

    def _pick(self, group):
        if len(group) == 1 or self.tie == "first":
            return group[0]
        weights = [r.probability for r in group]
        total = sum(weights)
        if total <= 0:
            return group[0]
        x = self.model.rng.random() * total
        acc = 0.0
        for r, w in zip(group, weights):
            acc += w
            if x < acc:
                return r
        return group[-1]

    def choose_route(self, job, t):
        """Вибір маршруту слідування.

        Повертає Route, або None, якщо всі допустимі маршрути заблоковані.
        Режим 'redistribute': заблоковані маршрути відкидаються, серед
        відкритих обирається група з найвищим пріоритетом, всередині групи -
        випадковий вибір за ймовірностями (або перший, якщо tie='first').
        Режим 'strict': маршрут розігрується за ймовірностями серед групи
        найвищого пріоритету без урахування блокування; якщо він
        заблокований - вимога чекає саме на цей маршрут.
        """
        m = self.model
        if self.routing == "strict":
            if job.pending is None:
                top = max(r.priority for r in self.routes)
                job.pending = self._pick([r for r in self.routes if r.priority == top])
            r = job.pending
            if r.is_blocked(m, t):
                r.n_blocked_checks += 1
                chosen = None
            else:
                job.pending = None
                r.n_used += 1
                chosen = r
            if m.on_choice is not None:
                m.on_choice(self, chosen, t)
            return chosen

        best, group = None, []
        for r in self.routes:
            if r.is_blocked(m, t):
                r.n_blocked_checks += 1
                continue
            p = r.priority
            if best is None or p > best:
                best, group = p, [r]
            elif p == best:
                group.append(r)
        chosen = None
        if group:
            chosen = self._pick(group)
            chosen.n_used += 1
        if m.on_choice is not None:
            m.on_choice(self, chosen, t)
        return chosen

    def send(self, job, route, t):
        m = self.model
        route.ts_sum += t - job.t_create
        tgt = route.target
        if route.group > 1:
            route.buffer.append(job)
            if len(route.buffer) < route.group:
                if m.tracing:
                    m.log(t, f"{self.name}: вимога {job} очікує на дузі групування "
                             f"({len(route.buffer)}/{route.group})")
                return
            members = route.buffer
            route.buffer = []
            job = m.new_job(t, members[0].type, members[0].priority)
            job.t_create = min(j.t_create for j in members)
            job.attrs["members"] = len(members)
            if m.tracing:
                m.log(t, f"{self.name}: група з {len(members)} вимог об'єднана у вимогу {job} → {tgt.name}")
            tgt.accept(job, t)
            return
        if route.split > 1:
            if m.tracing:
                m.log(t, f"{self.name}: вимога {job} розгрупована на {route.split} → {tgt.name}")
            for _ in range(route.split):
                j = m.new_job(t, job.type, job.priority)
                j.t_create = job.t_create
                tgt.accept(j, t)
            return
        if m.tracing:
            m.log(t, f"{self.name}: вимога {job} → {tgt.name}")
        tgt.accept(job, t)

    # ---- інтерфейс, який реалізують нащадки ---------------------------
    def init(self, model):
        self.model = model

    def on_event(self, t):
        pass

    def try_release(self, entry, t):
        return False

    def accept(self, job, t):
        raise TypeError(f"{self.name} не приймає вимог")

    def can_accept(self):
        return False

    def update_stats(self, dt):
        pass

    def reset_stats(self):
        pass

    def results(self, T):
        return {}

    @property
    def in_element(self):
        return 0


class Create(Element):
    """Надходження вимог ззовні з часовою затримкою delay між вимогами.

    on_block='wait' - якщо всі маршрути заблоковані, надходження
                      призупиняється (t0 := ∞) до зняття блокування,
                      після чого вимога надходить у момент зняття;
    on_block='lose' - вимога, що надійшла при заблокованому маршруті,
                      втрачається (лічильник lost), надходження триває.
    """

    def __init__(self, name, delay, first=None, on_block="wait", limit=None,
                 job_type=0, job_priority=0, **kw):
        super().__init__(name, on_block=on_block, **kw)
        if on_block not in ("wait", "lose"):
            raise ValueError("Create.on_block: 'wait' або 'lose'")
        self.delay = as_delay(delay)
        self.first = first
        self.limit = limit
        self.job_type = job_type
        self.job_priority = job_priority
        self.suspended = False
        self.reset_stats()

    def init(self, model):
        super().init(model)
        self.suspended = False
        self.tnext = self.first if self.first is not None else self.delay.sample(model.rng)

    def reset_stats(self):
        self.created = 0
        self.lost = 0
        self.suspended_time = 0.0

    def _new_job(self, t):
        j = self.model.new_job(t, self.job_type, self.job_priority)
        return j

    def _schedule_next(self, t):
        if self.limit is not None and self.model.n_jobs >= self.limit:
            self.tnext = INF
        else:
            self.tnext = t + self.delay.sample(self.model.rng)

    def on_event(self, t):
        m = self.model
        job = self._new_job(t)
        route = self.choose_route(job, t)
        if route is None:
            if self.on_block == "lose":
                self.lost += 1
                if m.tracing:
                    m.log(t, f"{self.name}: вимога {job} втрачена - маршрут заблоковано")
                self._schedule_next(t)
            else:
                m.n_jobs -= 1  # вимога фактично не надійшла
                self.suspended = True
                self.tnext = INF
                m.register_blocked(self, None, t)
                if m.tracing:
                    m.log(t, f"{self.name}: надходження призупинено - маршрут заблоковано")
            return
        self.created += 1
        self._schedule_next(t)
        self.send(job, route, t)

    def try_release(self, entry, t):
        job = self._new_job(t)
        route = self.choose_route(job, t)
        if route is None:
            self.model.n_jobs -= 1  # номер вимоги не витрачаємо
            return False
        self.suspended = False
        self.created += 1
        if self.model.tracing:
            self.model.log(t, f"{self.name}: блокування знято, надходження відновлено")
        self._schedule_next(t)
        self.send(job, route, t)
        return True

    def update_stats(self, dt):
        if self.suspended:
            self.suspended_time += dt

    def results(self, T):
        return {"created": self.created, "lost": self.lost,
                "p_lost": self.lost / (self.created + self.lost) if self.created + self.lost else 0.0,
                "suspended_share": self.suspended_time / T if T > 0 else 0.0}


class _Channel:
    __slots__ = ("idx", "state", "tnext", "job", "since")

    def __init__(self, idx):
        self.idx = idx
        self.state = FREE
        self.tnext = INF
        self.job = None
        self.since = 0.0


class _Queue:
    """Черга з дисципліною FIFO, LIFO або за пріоритетом вимоги."""

    def __init__(self, discipline):
        self.discipline = discipline
        self._seq = count()
        if callable(discipline) or discipline == "PRIORITY":
            self._key = discipline if callable(discipline) else (lambda j: j.priority)
            self._h = []
        elif discipline in ("FIFO", "LIFO"):
            self._d = deque()
        else:
            raise ValueError("дисципліна черги: 'FIFO', 'LIFO', 'PRIORITY' або функція")

    def push(self, job):
        if hasattr(self, "_h"):
            heapq.heappush(self._h, (-self._key(job), next(self._seq), job))
        else:
            self._d.append(job)

    def pop(self):
        if hasattr(self, "_h"):
            return heapq.heappop(self._h)[2]
        return self._d.popleft() if self.discipline == "FIFO" else self._d.pop()

    def __len__(self):
        return len(self._h) if hasattr(self, "_h") else len(self._d)


class Process(Element):
    """СМО з m ідентичними каналами та чергою.

    max_queue - обмеження довжини черги (INF - необмежена, 0 - без черги);
    queue     - дисципліна черги;
    on_block  - 'block': при заблокованих маршрутах канал переходить у
                стан 2 і утримує вимогу; 'lose': вимога вилучається.
    Вимога, що надійшла до заповненої СМО, отримує відмову (failures).
    """

    def __init__(self, name, delay, channels=1, max_queue=INF, queue="FIFO",
                 on_block="block", record=False, **kw):
        super().__init__(name, on_block=on_block, **kw)
        if on_block not in ("block", "lose"):
            raise ValueError("Process.on_block: 'block' або 'lose'")
        if channels < 1:
            raise ValueError("кількість каналів має бути ≥ 1")
        self.delay = as_delay(delay)
        self.m = int(channels)
        self.max_queue = max_queue
        self.discipline = queue
        self.record = record
        self.channels = [_Channel(i) for i in range(self.m)]
        self.queue = _Queue(queue)
        self.reset_stats()

    def init(self, model):
        super().init(model)
        self.channels = [_Channel(i) for i in range(self.m)]
        self.queue = _Queue(self.discipline)
        self.tnext = INF

    # ---- стан ------------------------------------------------------------
    @property
    def queue_len(self):
        return len(self.queue)

    @property
    def free_channels(self):
        return sum(1 for c in self.channels if c.state == FREE)

    @property
    def busy_channels(self):
        return sum(1 for c in self.channels if c.state == BUSY)

    @property
    def blocked_channels(self):
        return sum(1 for c in self.channels if c.state == BLOCKED)

    @property
    def in_element(self):
        return len(self.queue) + sum(1 for c in self.channels if c.state != FREE)

    def can_accept(self):
        if len(self.queue) < self.max_queue:
            return True
        for c in self.channels:
            if c.state == FREE:
                return True
        return False

    def _update_tnext(self):
        tn = INF
        for c in self.channels:
            if c.state == BUSY and c.tnext < tn:
                tn = c.tnext
        self.tnext = tn

    # ---- статистика ------------------------------------------------------
    def reset_stats(self):
        self.arrivals = 0
        self.failures = 0
        self.served = 0          # завершених обслуговувань
        self.departures = 0      # вимог, що залишили СМО
        self.lost_blocked = 0
        self.n_blocks = 0
        self.sum_queue = 0.0
        self.sum_busy = 0.0
        self.sum_blocked = 0.0
        self.max_queue_obs = len(self.queue) if hasattr(self, "queue") else 0
        self.wait_n = 0
        self.wait_sum = 0.0
        self.wait_sq = 0.0
        self.wait_max = 0.0
        self.waits = [] if self.record else None

    def update_stats(self, dt):
        q = len(self.queue)
        b = bl = 0
        for c in self.channels:
            if c.state == BUSY:
                b += 1
            elif c.state == BLOCKED:
                bl += 1
        self.sum_queue += q * dt
        self.sum_busy += b * dt
        self.sum_blocked += bl * dt

    # ---- події -----------------------------------------------------------
    def accept(self, job, t):
        m = self.model
        self.arrivals += 1
        for c in self.channels:
            if c.state == FREE:
                job.t_enter = t
                self._start(c, job, t)
                return True
        if len(self.queue) < self.max_queue:
            job.t_enter = t
            self.queue.push(job)
            if len(self.queue) > self.max_queue_obs:
                self.max_queue_obs = len(self.queue)
            if m.tracing:
                m.log(t, f"{self.name}: вимога {job} стала в чергу, L={len(self.queue)}")
            return True
        self.failures += 1
        if m.tracing:
            m.log(t, f"{self.name}: відмова вимозі {job} - немає місця")
        return False

    def _start(self, c, job, t):
        w = t - job.t_enter
        self.wait_n += 1
        self.wait_sum += w
        self.wait_sq += w * w
        if w > self.wait_max:
            self.wait_max = w
        if self.waits is not None:
            self.waits.append(w)
        c.state = BUSY
        c.job = job
        c.tnext = t + self.delay.sample(self.model.rng)
        if c.tnext < self.tnext:
            self.tnext = c.tnext
        if self.model.tracing:
            self.model.log(t, f"{self.name}[{c.idx}]: початок обслуговування {job}, вихід о {c.tnext:.4f}")

    def on_event(self, t):
        for c in self.channels:
            if c.state == BUSY and c.tnext <= t:
                self._complete(c, t)
        self._update_tnext()

    def _complete(self, c, t):
        m = self.model
        job = c.job
        self.served += 1
        if not self.routes:
            self._depart(c, job, None, t)
            return
        route = self.choose_route(job, t)
        if route is None:
            if self.on_block == "lose":
                self.lost_blocked += 1
                if m.tracing:
                    m.log(t, f"{self.name}[{c.idx}]: вимога {job} вилучена - маршрути заблоковані")
                self._depart(c, job, False, t)
                return
            c.state = BLOCKED
            c.tnext = INF
            c.since = t
            self.n_blocks += 1
            m.register_blocked(self, c, t)
            if m.tracing:
                m.log(t, f"{self.name}[{c.idx}]: блокування - вимога {job} не може вийти")
            return
        self._depart(c, job, route, t)

    def _depart(self, c, job, route, t):
        c.state = FREE
        c.job = None
        c.tnext = INF
        self.departures += 1
        if len(self.queue) > 0:
            self._start(c, self.queue.pop(), t)
        self._update_tnext()
        if route is None:
            self.model.exit(job, t, self)
        elif route is not False:
            self.send(job, route, t)

    def try_release(self, entry, t):
        c = entry[3]
        route = self.choose_route(c.job, t)
        if route is None:
            return False
        if self.model.tracing:
            self.model.log(t, f"{self.name}[{c.idx}]: блокування знято (тривало {t - c.since:.4f})")
        self._depart(c, c.job, route, t)
        return True

    def results(self, T):
        mean_w = self.wait_sum / self.wait_n if self.wait_n else 0.0
        var_w = self.wait_sq / self.wait_n - mean_w ** 2 if self.wait_n else 0.0
        return {
            "arrivals": self.arrivals,
            "served": self.served,
            "departures": self.departures,
            "failures": self.failures,
            "p_fail": self.failures / self.arrivals if self.arrivals else 0.0,
            "mean_queue": self.sum_queue / T if T > 0 else 0.0,
            "max_queue": self.max_queue_obs,
            "utilization": self.sum_busy / (T * self.m) if T > 0 else 0.0,
            "blocked_share": self.sum_blocked / (T * self.m) if T > 0 else 0.0,
            "n_blocks": self.n_blocks,
            "lost_blocked": self.lost_blocked,
            "p_lost_blocked": self.lost_blocked / self.served if self.served else 0.0,
            "mean_wait": mean_w,
            "std_wait": math.sqrt(max(var_w, 0.0)),
            "max_wait": self.wait_max,
        }


class Dispose(Element):
    """Вихід вимог з мережі зі збором статистики часу перебування."""

    def __init__(self, name="Вихід", record=False):
        super().__init__(name)
        self.record = record
        self.reset_stats()

    def can_accept(self):
        return True

    def reset_stats(self):
        self.count = 0
        self.ts_sum = 0.0
        self.ts_sq = 0.0
        self.ts_max = 0.0
        self.ts_min = INF
        self.times = [] if self.record else None

    def accept(self, job, t):
        self.count += 1
        ts = t - job.t_create
        self.ts_sum += ts
        self.ts_sq += ts * ts
        if ts > self.ts_max:
            self.ts_max = ts
        if ts < self.ts_min:
            self.ts_min = ts
        if self.times is not None:
            self.times.append(ts)
        if self.model.tracing:
            self.model.log(t, f"{self.name}: вимога {job} залишила мережу, час перебування {ts:.4f}")
        return True

    def results(self, T):
        n = self.count
        mean = self.ts_sum / n if n else 0.0
        var = self.ts_sq / n - mean ** 2 if n else 0.0
        return {"count": n, "throughput": n / T if T > 0 else 0.0,
                "mean_time": mean, "std_time": math.sqrt(max(var, 0.0)),
                "min_time": self.ts_min if n else 0.0, "max_time": self.ts_max}
