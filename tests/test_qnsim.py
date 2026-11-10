"""Модульні тести бібліотеки qnsim (запуск: python -m pytest tests)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qnsim import (Const, Create, Dispose, Exp, Model, Process, busy, full,  # noqa: E402
                   queue_ge)


def test_deterministic_tandem():
    # детермінована лінія: надходження кожні 2, обробка 1 -> черги немає
    s = Create("S", Const(2.0), first=0.0)
    p = Process("P", Const(1.0))
    o = Dispose("O")
    s.to(p)
    p.to(o)
    r = Model(s, p, o).simulate(100.0)
    assert r["P"]["mean_queue"] == 0
    assert abs(r["P"]["utilization"] - 0.5) < 0.02
    assert r["O"]["count"] == 50


def test_priority_route_always_first_when_open():
    s = Create("S", Const(10.0), first=0.0)
    a = Process("A", Const(1.0), max_queue=0)
    b = Process("B", Const(1.0), max_queue=0)
    o = Dispose("O")
    s.add_route(a, priority=5, block=busy(a))
    s.add_route(b, priority=1, block=busy(b))
    a.to(o)
    b.to(o)
    r = Model(s, a, b, o).simulate(1000.0)
    assert r["A"]["arrivals"] > 0 and r["B"]["arrivals"] == 0


def test_blocking_holds_channel():
    # друга фаза надто повільна, буфер 0 -> перша фаза блокується
    s = Create("S", Const(1.0), first=0.0)
    p1 = Process("P1", Const(1.0))
    p2 = Process("P2", Const(3.0), max_queue=0)
    o = Dispose("O")
    s.to(p1)
    p1.add_route(p2, block=full(p2))
    p2.to(o)
    r = Model(s, p1, p2, o).simulate(300.0)
    assert r["P1"]["blocked_share"] > 0.5
    assert r["P2"]["failures"] == 0      # блокування замість відмови
    assert abs(r["O"]["throughput"] - 1 / 3) < 0.01


def test_source_suspension():
    s = Create("S", Exp(0.5), on_block="wait")
    p = Process("P", Exp(1.0), max_queue=2)
    o = Dispose("O")
    s.add_route(p, block=queue_ge(p, 2))
    p.to(o)
    r = Model(s, p, o, seed=3).simulate(5000.0)
    assert r["P"]["failures"] == 0
    assert r["S"]["suspended_share"] > 0
    assert r["P"]["max_queue"] <= 2


def test_reproducibility():
    def run():
        s = Create("S", Exp(1.0))
        p = Process("P", Exp(0.9), channels=2)
        o = Dispose("O")
        s.to(p)
        p.to(o)
        return Model(s, p, o, seed=42).simulate(2000.0)["O"]["mean_time"]
    assert run() == run()


def test_condition_parser():
    from qnsim import Condition, ConditionError
    c = Condition("L(A) + L(B) > 25 and not (K(A) == 0)")
    assert c.text == "L(A) + L(B) > 25 ∧ ¬ (K(A) = 0)"
    for bad in ("L(A) = = 1", "L(A) > ", "foo(A) > 1"):
        try:
            Condition(bad)
        except ConditionError:
            pass
        else:
            raise AssertionError(bad)


def test_time_condition_next_change():
    s = Create("S", Exp(1.0), on_block="lose")
    p = Process("P", Exp(0.1), channels=50)
    o = Dispose("O")
    r = s.add_route(p, block="t mod 60 ∈ [50; 60)")
    p.to(o)
    m = Model(s, p, o, seed=1)
    m.simulate(10.0)
    assert r.block.next_change(10.0) == 50.0
    assert r.block.next_change(50.0) == 60.0


def test_unknown_element_in_condition():
    from qnsim import ConditionError
    s = Create("S", Exp(1.0))
    p = Process("P", Exp(0.5))
    o = Dispose("O")
    s.add_route(p, block="L(X) > 2")
    p.to(o)
    try:
        Model(s, p, o).simulate(10.0)
    except ConditionError:
        return
    raise AssertionError("очікувалась помилка")


def test_group_arc():
    s = Create("S", Const(1.0), first=0.0)
    p = Process("P", Const(0.5))
    o = Dispose("O")
    s.add_route(p, group=4)
    p.to(o)
    r = Model(s, p, o).simulate(100.5)
    assert r["O"]["count"] == 25
