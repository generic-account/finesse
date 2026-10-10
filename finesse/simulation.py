from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .core.fsm import FSM


@dataclass(frozen=True)
class Step:
    cycle: int
    src: str
    dst: str
    transition_id: int | None
    inputs: Mapping[str, int]


@dataclass
class Statistics:
    cycles: int = 0
    state_cycles: Counter[str] = field(default_factory=Counter)
    transition_counts: Counter[int] = field(default_factory=Counter)
    transition_matrix: Counter[tuple[str, str]] = field(default_factory=Counter)
    holds: Counter[str] = field(default_factory=Counter)

    def observe(self, step: Step) -> None:
        self.cycles += 1
        self.state_cycles[step.src] += 1
        self.transition_matrix[step.src, step.dst] += 1
        if step.transition_id is None:
            self.holds[step.src] += 1
        else:
            self.transition_counts[step.transition_id] += 1

    def switching_cost(self, encoding: Mapping[str, int]) -> int:
        states = {state for pair in self.transition_matrix for state in pair}
        if not states <= encoding.keys():
            raise ValueError("Encoding must include every observed state")
        codes = list(encoding.values())
        if any(not isinstance(code, int) or code < 0 for code in codes):
            raise ValueError("Encoding values must be nonnegative integers")
        if len(set(codes)) != len(codes):
            raise ValueError("Encoding values must be unique")
        return sum(
            count * (encoding[src] ^ encoding[dst]).bit_count()
            for (src, dst), count in self.transition_matrix.items()
        )


class Simulator:
    def __init__(self, fsm: FSM, *, initial_state: str | None = None, record: bool = True):
        self.model = fsm.compile()
        self.initial_state = (
            initial_state if initial_state is not None else self.model.default_state
        )
        if self.initial_state is None:
            raise RuntimeError("FSM has no default state; supply initial_state")
        if self.initial_state not in self.model.states:
            raise ValueError(f"Unknown state {self.initial_state!r}")
        self.record = record
        self.reset()

    def reset(self) -> None:
        self.current_state = self.initial_state
        self.trace: list[Step] = []
        self.statistics = Statistics()

    def step(self, inputs: Mapping[str, int]) -> Step:
        unknown = inputs.keys() - self.model.inputs.keys()
        if unknown:
            raise ValueError(f"Unknown inputs: {sorted(unknown)}")
        values = {name: inputs.get(name, 0) for name in self.model.inputs}
        for name, value in values.items():
            if not isinstance(value, int) or not 0 <= value < 1 << self.model.inputs[name]:
                raise ValueError(f"Input {name!r} does not fit its declared width")
        src = self.current_state
        dst, transition_id = src, None
        for index, transition in self.model.outgoing[src]:
            if transition.cond.eval(values):
                dst, transition_id = transition.dst, index
                break
        step = Step(self.statistics.cycles + 1, src, dst, transition_id, MappingProxyType(values))
        self.current_state = dst
        self.statistics.observe(step)
        if self.record:
            self.trace.append(step)
        return step

    def run(self, inputs_seq: Iterable[Mapping[str, int]]) -> Simulator:
        for inputs in inputs_seq:
            self.step(inputs)
        return self

    @property
    def uncovered_transitions(self) -> tuple[int, ...]:
        return tuple(
            index
            for index in range(len(self.model.transitions))
            if not self.statistics.transition_counts[index]
        )

    def view(self, *, show: bool = True):
        from .visualization.viewer import SimulationViewer

        viewer = SimulationViewer(self)
        if show:
            viewer.show()
        return viewer
