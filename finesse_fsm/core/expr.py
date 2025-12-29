from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Union


ExprLike = Union["Expr", int, bool]


def _to_expr(value: ExprLike) -> "Expr":
    if isinstance(value, Expr):
        return value
    return Const(int(value))


class Expr(ABC):
    """Base class for small boolean/bitvector expressions."""

    @abstractmethod
    def eval(self, inputs: Dict[str, int]) -> int:
        """Evaluate expression with given input values (int or bool)."""
        raise NotImplementedError

    @abstractmethod
    def to_verilog(self) -> str:
        """Render expression as a Verilog/SystemVerilog expression string."""
        raise NotImplementedError

    # Logical / bitwise ops (we treat them logically for conditions)
    def __and__(self, other: ExprLike) -> "Expr":
        return BinOp("and", self, _to_expr(other))

    def __or__(self, other: ExprLike) -> "Expr":
        return BinOp("or", self, _to_expr(other))

    def __xor__(self, other: ExprLike) -> "Expr":
        return BinOp("xor", self, _to_expr(other))

    def __invert__(self) -> "Expr":
        # Use ~expr in Python as logical NOT in the DSL
        return UnaryOp("not", self)

    # Comparisons
    def __eq__(self, other: object) -> "Expr":  # type: ignore[override]
        # note: this changes equality semantics for Expr; that's fine here.
        return BinOp("eq", self, _to_expr(other))  # type: ignore[arg-type]

    def __ne__(self, other: object) -> "Expr":  # type: ignore[override]
        return BinOp("ne", self, _to_expr(other))  # type: ignore[arg-type]

    def __lt__(self, other: ExprLike) -> "Expr":
        return BinOp("lt", self, _to_expr(other))

    def __le__(self, other: ExprLike) -> "Expr":
        return BinOp("le", self, _to_expr(other))

    def __gt__(self, other: ExprLike) -> "Expr":
        return BinOp("gt", self, _to_expr(other))

    def __ge__(self, other: ExprLike) -> "Expr":
        return BinOp("ge", self, _to_expr(other))


@dataclass(frozen=True, eq=False)
class Sig(Expr):
    """Reference to an input signal by name."""

    name: str

    def eval(self, inputs: Dict[str, int]) -> int:
        return int(inputs.get(self.name, 0))

    def to_verilog(self) -> str:
        return self.name


@dataclass(frozen=True, eq=False)
class Const(Expr):
    """Integer constant (often 0 or 1 for conditions)."""

    value: int

    def eval(self, inputs: Dict[str, int]) -> int:
        return int(self.value)

    def to_verilog(self) -> str:
        if self.value in (0, 1):
            return f"1'b{self.value}"
        return str(self.value)


@dataclass(frozen=True, eq=False)
class UnaryOp(Expr):
    op: str   # "not"
    expr: Expr

    def eval(self, inputs: Dict[str, int]) -> int:
        v = bool(self.expr.eval(inputs))
        if self.op == "not":
            return int(not v)
        raise ValueError(f"Unknown unary op {self.op!r}")

    def to_verilog(self) -> str:
        if self.op == "not":
            return f"!({self.expr.to_verilog()})"
        raise ValueError(f"Unknown unary op {self.op!r}")

@dataclass(frozen=True, eq=False)
class BinOp(Expr):
    op: str   # "and", "or", "xor", "eq", "ne", "lt", "le", "gt", "ge"
    left: Expr
    right: Expr

    def eval(self, inputs: Dict[str, int]) -> int:
        lv = self.left.eval(inputs)
        rv = self.right.eval(inputs)

        if self.op == "and":
            return int(bool(lv) and bool(rv))
        if self.op == "or":
            return int(bool(lv) or bool(rv))
        if self.op == "xor":
            return int(bool(lv) ^ bool(rv))
        if self.op == "eq":
            return int(lv == rv)
        if self.op == "ne":
            return int(lv != rv)
        if self.op == "lt":
            return int(lv < rv)
        if self.op == "le":
            return int(lv <= rv)
        if self.op == "gt":
            return int(lv > rv)
        if self.op == "ge":
            return int(lv >= rv)

        raise ValueError(f"Unknown binary op {self.op!r}")

    def to_verilog(self) -> str:
        l = self.left.to_verilog()
        r = self.right.to_verilog()

        if self.op == "and":
            return f"({l} && {r})"
        if self.op == "or":
            return f"({l} || {r})"
        if self.op == "xor":
            return f"({l} ^ {r})"
        if self.op == "eq":
            return f"({l} == {r})"
        if self.op == "ne":
            return f"({l} != {r})"
        if self.op == "lt":
            return f"({l} < {r})"
        if self.op == "le":
            return f"({l} <= {r})"
        if self.op == "gt":
            return f"({l} > {r})"
        if self.op == "ge":
            return f"({l} >= {r})"

        raise ValueError(f"Unknown binary op {self.op!r}")


# Small helpers for user code
def sig(name: str) -> Expr:
    return Sig(name)


def const(v: int | bool) -> Expr:
    return Const(int(v))
