from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .expr import Expr


@dataclass
class State:
    """
    A single FSM state.

    - name: state identifier
    - side_effect: hint that this state may perform side effects
    - default: set by FSM.add_state(..., default=True)
    - transitions: managed by the FSM (user doesn't modify directly)
    """
    name: str
    side_effect: bool = True
    default: bool = False
    transitions: List["Transition"] = field(default_factory=list)


@dataclass
class Transition:
    """
    A directed edge between two states.

    - src, dst: state names
    - cond: Expr from the small DSL (finesse.core.expr.Expr)
    """
    src: str
    dst: str
    cond: Expr


@dataclass
class FSM:
    """
    Minimal FSM core.

    - name: identifier for this FSM
    - inputs: mapping input name -> bit width
    - states, transitions: internal registries
    - current_state: current state for simulation
    - default_state: reset/initial state
    """
    name: str
    inputs: Dict[str, int]
    states: Dict[str, State] = field(default_factory=dict)
    transitions: List[Transition] = field(default_factory=list)
    current_state: Optional[State] = None
    default_state: Optional[State] = None

    def add_state(self, state: State, *, default: bool = False) -> None:
        """
        Add a state to the FSM.

        Example:
            fsm.add_state(State("IDLE"), default=True)
        """
        if default:
            if self.default_state is not None:
                raise ValueError("FSM cannot have more than one default state")
            state.default = True
            self.default_state = state

        if state.name in self.states:
            raise ValueError(f"State {state.name!r} already exists in FSM {self.name!r}")

        self.states[state.name] = state

        if self.current_state is None and state.default:
            self.current_state = state

    def add_states(self, states: List[State], *, default: Optional[str] = None) -> None:
        """
        Add multiple states at once.

        `default` may be the name of the default state among them.
        """
        for s in states:
            is_default = (default is not None and s.name == default)
            self.add_state(s, default=is_default)

    def add_transition(self, transition: Transition) -> None:
        """
        Add a transition and attach it to the source state.
        """
        if transition.src not in self.states:
            raise ValueError(f"Source state {transition.src!r} not in FSM")
        if transition.dst not in self.states:
            raise ValueError(f"Destination state {transition.dst!r} not in FSM")

        self.transitions.append(transition)
        self.states[transition.src].transitions.append(transition)

    def reset(self) -> None:
        """
        Reset the FSM to its default state.
        """
        if self.default_state is None:
            raise RuntimeError("FSM has no default state defined")
        self.current_state = self.default_state

    def set_state(self, state_name: str) -> None:
        """
        Manually set the current state.
        """
        if state_name not in self.states:
            raise ValueError(f"Unknown state {state_name!r}")
        self.current_state = self.states[state_name]

    def step(self, inputs: Dict[str, int]) -> State:
        """
        Advance the FSM by one step with the given inputs.

        - Checks outgoing transitions from current_state.
        - Takes the first transition whose condition is True.
        - If none match, stays in the current state.
        """
        if self.current_state is None:
            if self.default_state is None:
                raise RuntimeError("FSM has no current_state and no default_state")
            self.current_state = self.default_state

        state = self.current_state
        for t in state.transitions:
            if bool(t.cond.eval(inputs)):
                self.current_state = self.states[t.dst]
                break

        return self.current_state

    def multi_step(self, inputs_seq: List[Dict[str, int]]) -> List[State]:
        """
        Run a sequence of input vectors and return the visited states.
        """
        visited: List[State] = []
        for inp in inputs_seq:
            visited.append(self.step(inp))
        return visited
    
    def to_mermaid(self, show_conditions: bool = True) -> str:
        """
        Produce a Mermaid state diagram (stateDiagram-v2) as a string.

        If show_conditions is True, label edges with the transition condition
        (rendered via Expr.to_verilog()). If False, omit edge labels.
        """
        lines: List[str] = ["stateDiagram-v2"]

        if self.default_state is not None:
            lines.append(f"    [*] --> {self.default_state.name}")

        for s in self.states.values():
            lines.append(f"    state {s.name}")

        for t in self.transitions:
            if show_conditions:
                try:
                    label = t.cond.to_verilog()
                except Exception:
                    label = ""
            else:
                label = ""

            if label:
                lines.append(f"    {t.src} --> {t.dst} : {label}")
            else:
                lines.append(f"    {t.src} --> {t.dst}")

        return "\n".join(lines)

    def visualize(
        self,
        outfile: Optional[str] = None,
        show_conditions: bool = True,
    ) -> str:
        """
        Return the Mermaid diagram, optionally writing it to a file.

        - outfile: if not None, write the diagram text to this path.
        - show_conditions: whether to include transition conditions as labels.
        """
        diagram = self.to_mermaid(show_conditions=show_conditions)
        if outfile is not None:
            with open(outfile, "w", encoding="utf-8") as f:
                f.write(diagram)
        return diagram