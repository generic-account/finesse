from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .fsm import FSM, Transition


@dataclass(frozen=True)
class FSMModel:
    name: str
    inputs: Mapping[str, int]
    states: tuple[str, ...]
    transitions: tuple[Transition, ...]
    default_state: str | None
    outgoing: Mapping[str, tuple[tuple[int, Transition], ...]]

    @classmethod
    def from_fsm(cls, fsm: FSM) -> FSMModel:
        if not fsm.states:
            raise ValueError("FSM has no states")
        if any(not isinstance(width, int) or width < 1 for width in fsm.inputs.values()):
            raise ValueError("Input widths must be positive integers")
        transitions = tuple(fsm.transitions)
        # Group transitions by source state
        outgoing = {state: [] for state in fsm.states}
        for index, transition in enumerate(transitions):
            if transition.src not in fsm.states or transition.dst not in fsm.states:
                raise ValueError("Transition endpoints must be registered states")
            outgoing[transition.src].append((index, transition))
        default = fsm.default_state.name if fsm.default_state is not None else None
        if default is not None and default not in fsm.states:
            raise ValueError(f"Unknown default state {default!r}")
        return cls(
            fsm.name,
            MappingProxyType(dict(fsm.inputs)),
            tuple(fsm.states),
            transitions,
            default,
            MappingProxyType({state: tuple(edges) for state, edges in outgoing.items()}),
        )
