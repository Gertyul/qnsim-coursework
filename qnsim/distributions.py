"""Генератори випадкових величин часових затримок.

Позначення відповідають навчальному посібнику:
    d            - детерміноване значення,
    exp(d)       - експоненціальний закон із середнім d,
    unif(d, s)   - рівномірний закон на інтервалі (d - s, d + s),
    norm(d, s)   - нормальний закон із середнім d та СКВ s (усічений знизу нулем),
    erl(d, s)    - закон Ерланга із середнім d та СКВ s.
"""
import math


class Delay:
    """Базовий клас генератора часової затримки."""

    mean = 0.0

    def sample(self, rng):
        raise NotImplementedError

    def __repr__(self):
        return self.describe()

    def describe(self):
        return self.__class__.__name__


class Const(Delay):
    def __init__(self, d):
        if d < 0:
            raise ValueError("затримка не може бути від'ємною")
        self.d = float(d)
        self.mean = self.d

    def sample(self, rng):
        return self.d

    def describe(self):
        return f"{self.d:g}"


class Exp(Delay):
    def __init__(self, mean):
        if mean <= 0:
            raise ValueError("середнє значення має бути додатним")
        self.mean = float(mean)

    def sample(self, rng):
        # метод оберненої функції: x = -d * ln(u), u ~ U(0, 1]
        return -self.mean * math.log(1.0 - rng.random())

    def describe(self):
        return f"exp({self.mean:g})"


class Unif(Delay):
    def __init__(self, d, s):
        if s < 0 or d - s < 0:
            raise ValueError("некоректні параметри рівномірного закону")
        self.d, self.s = float(d), float(s)
        self.mean = self.d

    def sample(self, rng):
        return self.d - self.s + 2.0 * self.s * rng.random()

    def describe(self):
        return f"unif({self.d:g}, {self.s:g})"


class Norm(Delay):
    def __init__(self, d, s):
        self.d, self.s = float(d), float(s)
        self.mean = self.d

    def sample(self, rng):
        while True:
            x = rng.gauss(self.d, self.s)
            if x >= 0:
                return x

    def describe(self):
        return f"norm({self.d:g}, {self.s:g})"


class Erl(Delay):
    def __init__(self, d, s):
        if d <= 0 or s <= 0:
            raise ValueError("некоректні параметри закону Ерланга")
        self.d, self.s = float(d), float(s)
        self.k = max(1, round((d / s) ** 2))
        self.mean = self.d

    def sample(self, rng):
        theta = self.d / self.k
        prod = 1.0
        for _ in range(self.k):
            prod *= 1.0 - rng.random()
        return -theta * math.log(prod)

    def describe(self):
        return f"erl({self.d:g}, {self.s:g})"


def as_delay(x):
    """Дозволяє задавати затримку числом (детерміноване значення)."""
    if isinstance(x, Delay):
        return x
    if isinstance(x, (int, float)):
        return Const(x)
    raise TypeError(f"неможливо перетворити {x!r} на генератор затримки")
