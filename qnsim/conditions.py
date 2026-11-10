"""Умови блокування маршруту B(S, t) у логіко-алгебраїчному записі.

Умова - це логічний вираз від поточного стану елементів мережі S та
модельного часу t. Якщо B(S, t) = 1, маршрут заблоковано.

Граматика (у дужках - еквівалентні ASCII-позначення):

    вираз      := диз'юнкція
    диз'юнкція := кон'юнкція { "∨" (or, ||) кон'юнкція }
    кон'юнкція := заперечення { "∧" (and, &&) заперечення }
    заперечення:= "¬" (not, !) заперечення | порівняння
    порівняння := сума [ відношення сума ] | сума "∈" інтервал
    відношення := "=" (==) | "≠" (!=) | "<" | "≤" (<=) | ">" | "≥" (>=)
    інтервал   := ("[" | "(") сума ";" сума ("]" | ")")
    сума       := добуток { ("+" | "-") добуток }
    добуток    := множник { ("·" (*) | "/" | "mod" (%)) множник }
    множник    := число | "t" | константа | функція "(" елемент ")"
                  | "(" вираз ")" | "-" множник | "∞"

Функції стану СМО X:
    L(X)   - кількість вимог у черзі;
    K(X)   - кількість зайнятих каналів (у стані 1 або 2);
    Z(X)   - кількість каналів, що обслуговують вимогу (стан 1);
    Y(X)   - кількість заблокованих каналів (стан 2);
    N(X)   - кількість вимог у СМО, N = L + K;
    F(X)   - кількість вільних каналів;
    M(X)   - кількість каналів;  MAX(X) - обмеження черги.
Константи (наприклад KA) задаються словником params моделі або умови.

Приклади:  "L(FA) = KA ∧ K(FA) ≠ 0",
           "L(M1) + L(M2) > 25",
           "N(FA) ≥ 3 ∨ t mod 480 ∈ [450; 480)".

Час може входити до умови лише у вигляді t або t mod P, що порівнюється
з константою, - тоді моменти зміни значення умови обчислюються точно і
алгоритм імітації переглядає заблоковані елементи саме в ці моменти.
"""
import math
import re

INF = math.inf

_FUNCS = ("MAX", "L", "K", "Z", "Y", "N", "F", "M")

_TOKEN = re.compile(r"""
    (?P<num>\d+(?:[.,]\d+)?)
  | (?P<op><=|>=|==|!=|&&|\|\||[≤≥≠∧∨¬=<>+\-*/·%()\[\];∈!∞])
  | (?P<name>[A-Za-zА-Яа-яІіЇїЄєҐґ_][A-Za-zА-Яа-яІіЇїЄєҐґ_0-9]*)
  | (?P<ws>\s+)
""", re.X)

_ALIASES = {"<=": "≤", ">=": "≥", "==": "=", "!=": "≠", "&&": "∧", "||": "∨", "!": "¬",
            "and": "∧", "or": "∨", "not": "¬", "*": "·", "%": "mod", "in": "∈"}


class ConditionError(ValueError):
    pass


def _tokenize(text):
    out, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ConditionError(f"невідомий символ «{text[pos]}» в умові «{text}»")
        pos = m.end()
        if m.lastgroup == "ws":
            continue
        v = m.group()
        if m.lastgroup == "num":
            out.append(("num", float(v.replace(",", "."))))
        elif m.lastgroup == "name":
            low = v.lower()
            if low in ("and", "or", "not", "mod", "in"):
                out.append(("op", _ALIASES.get(low, low)))
            elif v == "t":
                out.append(("t", None))
            elif v in _FUNCS:
                out.append(("func", v))
            else:
                out.append(("name", v))
        else:
            out.append(("op", _ALIASES.get(v, v)))
    out.append(("end", None))
    return out


# ---------------------------------------------------------------- вузли AST
class _Node:
    uses_t = False
    uses_state = False


class _Num(_Node):
    def __init__(self, v):
        self.v = v

    def compile(self, b):
        v = self.v
        return lambda t: v

    def const(self, b):
        return self.v


class _Const(_Node):
    def __init__(self, name):
        self.name = name

    def compile(self, b):
        v = b.const(self.name)
        return lambda t: v

    def const(self, b):
        return b.const(self.name)


class _Time(_Node):
    uses_t = True

    def compile(self, b):
        return lambda t: t


class _Func(_Node):
    uses_state = True

    def __init__(self, f, elem):
        self.f, self.elem = f, elem

    def compile(self, b):
        e = b.element(self.elem)
        f = self.f
        if not hasattr(e, "channels"):
            raise ConditionError(f"функція {f}() застосовна лише до СМО, а «{self.elem}» не є СМО")
        if f == "L":
            return lambda t: len(e.queue)
        if f == "K":
            return lambda t: sum(1 for c in e.channels if c.state != 0)
        if f == "Z":
            return lambda t: sum(1 for c in e.channels if c.state == 1)
        if f == "Y":
            return lambda t: sum(1 for c in e.channels if c.state == 2)
        if f == "N":
            return lambda t: len(e.queue) + sum(1 for c in e.channels if c.state != 0)
        if f == "F":
            return lambda t: sum(1 for c in e.channels if c.state == 0)
        if f == "M":
            return lambda t: e.m
        if f == "MAX":
            return lambda t: e.max_queue
        raise ConditionError(f)


class _Bin(_Node):
    OPS = {
        "+": lambda a, b: a + b, "-": lambda a, b: a - b, "·": lambda a, b: a * b,
        "/": lambda a, b: a / b if b else INF, "mod": lambda a, b: a % b,
        "=": lambda a, b: a == b, "≠": lambda a, b: a != b, "<": lambda a, b: a < b,
        "≤": lambda a, b: a <= b, ">": lambda a, b: a > b, "≥": lambda a, b: a >= b,
    }

    def __init__(self, op, a, b):
        self.op, self.a, self.b = op, a, b
        self.uses_t = a.uses_t or b.uses_t
        self.uses_state = a.uses_state or b.uses_state

    def compile(self, bd):
        fa, fb, fn = self.a.compile(bd), self.b.compile(bd), self.OPS[self.op]
        return lambda t: fn(fa(t), fb(t))

    def const(self, b):
        if self.uses_t or self.uses_state:
            raise ConditionError("очікувалась константа")
        return self.OPS[self.op](self.a.const(b), self.b.const(b))


class _And(_Node):
    def __init__(self, items):
        self.items = items
        self.uses_t = any(i.uses_t for i in items)
        self.uses_state = any(i.uses_state for i in items)

    def compile(self, b):
        fs = [i.compile(b) for i in self.items]
        return lambda t: all(f(t) for f in fs)


class _Or(_And):
    def compile(self, b):
        fs = [i.compile(b) for i in self.items]
        return lambda t: any(f(t) for f in fs)


class _Not(_Node):
    def __init__(self, a):
        self.a = a
        self.uses_t, self.uses_state = a.uses_t, a.uses_state

    def compile(self, b):
        f = self.a.compile(b)
        return lambda t: not f(t)


class _Neg(_Bin):
    def __init__(self, a):
        super().__init__("-", _Num(0.0), a)


# ---------------------------------------------------------------- розбір
class _Parser:
    def __init__(self, text):
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def take(self, kind=None, val=None):
        k, v = self.toks[self.i]
        if (kind and k != kind) or (val is not None and v != val):
            exp = val if val is not None else kind
            raise ConditionError(f"в умові «{self.text}» очікувалось «{exp}», отримано «{v}»")
        self.i += 1
        return v

    def is_op(self, *vals):
        k, v = self.peek()
        return k == "op" and v in vals

    def parse(self):
        node = self.disj()
        if self.peek()[0] != "end":
            raise ConditionError(f"зайві символи в умові «{self.text}»")
        return node

    def disj(self):
        items = [self.conj()]
        while self.is_op("∨"):
            self.take()
            items.append(self.conj())
        return items[0] if len(items) == 1 else _Or(items)

    def conj(self):
        items = [self.neg()]
        while self.is_op("∧"):
            self.take()
            items.append(self.neg())
        return items[0] if len(items) == 1 else _And(items)

    def neg(self):
        if self.is_op("¬"):
            self.take()
            return _Not(self.neg())
        return self.cmp()

    def cmp(self):
        a = self.sum()
        if self.is_op("=", "≠", "<", "≤", ">", "≥"):
            op = self.take()
            return _Bin(op, a, self.sum())
        if self.is_op("∈"):
            self.take()
            lo_inc = self.take("op") == "["
            lo = self.sum()
            self.take("op", ";")
            hi = self.sum()
            hi_inc = self.take("op") == "]"
            return _And([_Bin("≥" if lo_inc else ">", a, lo), _Bin("≤" if hi_inc else "<", a, hi)])
        return a

    def sum(self):
        a = self.prod()
        while self.is_op("+", "-"):
            op = self.take()
            a = _Bin(op, a, self.prod())
        return a

    def prod(self):
        a = self.atom()
        while self.is_op("·", "/", "mod"):
            op = self.take()
            a = _Bin(op, a, self.atom())
        return a

    def atom(self):
        k, v = self.peek()
        if k == "num":
            self.take()
            return _Num(v)
        if k == "t":
            self.take()
            return _Time()
        if k == "name":
            self.take()
            return _Const(v)
        if k == "func":
            self.take()
            self.take("op", "(")
            el = self.take("name") if self.peek()[0] == "name" else str(self.take("num"))
            self.take("op", ")")
            return _Func(v, el)
        if self.is_op("∞"):
            self.take()
            return _Num(INF)
        if self.is_op("-"):
            self.take()
            return _Neg(self.atom())
        if self.is_op("("):
            self.take()
            n = self.disj()
            self.take("op", ")")
            return n
        raise ConditionError(f"неочікуваний символ «{v}» в умові «{self.text}»")


def _pretty(text):
    """Нормалізований запис умови з математичними символами."""
    s = text
    for a, b in (("<=", "≤"), (">=", "≥"), ("!=", "≠"), ("==", "="), ("&&", "∧"), ("||", "∨")):
        s = s.replace(a, b)
    s = re.sub(r"\band\b", "∧", s)
    s = re.sub(r"\bor\b", "∨", s)
    s = re.sub(r"\bnot\b", "¬", s)
    s = s.replace("*", "·")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- часові точки
def _time_points(node, b, t0, out):
    """Збирає моменти > t0, у які може змінитись значення порівнянь з t."""
    if isinstance(node, (_And, _Or)):
        for i in node.items:
            _time_points(i, b, t0, out)
        return
    if isinstance(node, _Not):
        _time_points(node.a, b, t0, out)
        return
    if isinstance(node, _Bin) and node.op in ("=", "≠", "<", "≤", ">", "≥") and node.uses_t:
        side, other = (node.a, node.b) if node.a.uses_t else (node.b, node.a)
        if other.uses_t or other.uses_state or side.uses_state:
            raise ConditionError("час t має порівнюватись з константою")
        c = other.const(b)
        if isinstance(side, _Time):
            if c > t0:
                out.append(c)
            return
        if isinstance(side, _Bin) and side.op == "mod" and isinstance(side.a, _Time) and not side.b.uses_t:
            P = side.b.const(b)
            base = t0 - (t0 % P)
            for cand in (base + c, base + P + c, base + P):
                if cand > t0 + 1e-12:
                    out.append(cand)
            return
        raise ConditionError("час може входити до умови лише як t або t mod P")
    if node.uses_t:
        raise ConditionError("час t може використовуватись лише в порівняннях з константою")


class _Binder:
    def __init__(self, model, params):
        self.model, self.params = model, params

    def element(self, name):
        try:
            return self.model[name]
        except KeyError:
            raise ConditionError(f"в умові згадано елемент «{name}», якого немає в мережі") from None

    def const(self, name):
        if name in self.params:
            return float(self.params[name])
        if self.model is not None and name in self.model.params:
            return float(self.model.params[name])
        raise ConditionError(f"невідома константа «{name}» в умові")


class Condition:
    """Умова блокування маршруту, задана логіко-алгебраїчним виразом."""

    def __init__(self, expr, params=None):
        if not isinstance(expr, str):
            raise TypeError("умова блокування задається рядком-виразом, напр. \"L(FA) = KA ∧ K(FA) ≠ 0\"")
        self.text = _pretty(expr)
        self.params = dict(params or {})
        self.ast = _Parser(expr).parse()
        self._fn = None
        self._model = None
        self.uses_t = self.ast.uses_t

    def bind(self, model):
        """Прив'язка імен елементів і констант до моделі (виконується один раз)."""
        b = _Binder(model, self.params)
        self._fn = self.ast.compile(b)
        self._binder = b
        self._model = model
        if self.uses_t:
            _time_points(self.ast, b, 0.0, [])   # перевірка допустимості часової частини
        return self

    def __call__(self, model, t):
        if self._model is not model:
            self.bind(model)
        return bool(self._fn(t))

    def next_change(self, t):
        if not self.uses_t:
            return INF
        pts = []
        _time_points(self.ast, self._binder, t, pts)
        return min(pts, default=INF)

    def __and__(self, other):
        other = as_condition(other)
        return Condition(f"({self.text}) ∧ ({other.text})", {**self.params, **other.params})

    def __or__(self, other):
        other = as_condition(other)
        return Condition(f"({self.text}) ∨ ({other.text})", {**self.params, **other.params})

    def __invert__(self):
        return Condition(f"¬({self.text})", self.params)

    def __repr__(self):
        return self.text


def as_condition(c):
    if c is None or isinstance(c, Condition):
        return c
    if isinstance(c, str):
        return Condition(c)
    raise TypeError("умова блокування має бути рядком-виразом або Condition")


# ---- типові умови (скорочення, що будують той самий вираз) -----------------
def _n(target):
    return target if isinstance(target, str) else target.name


def full(target):
    """СМО заповнена: черга досягла обмеження і вільних каналів немає."""
    n = _n(target)
    return Condition(f"L({n}) = MAX({n}) ∧ F({n}) = 0")


def busy(target):
    """У СМО немає вільного каналу."""
    n = _n(target)
    return Condition(f"F({n}) = 0")


def queue_ge(target, k):
    return Condition(f"L({_n(target)}) ≥ {k}")


def in_system_ge(elements, k):
    return Condition(" + ".join(f"N({_n(e)})" for e in elements) + f" ≥ {k}")


def time_window(start, end, period):
    return Condition(f"t mod {period:g} ∈ [{start:g}; {end:g})")
