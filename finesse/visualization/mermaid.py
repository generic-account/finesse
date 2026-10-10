from typing import List

from ..core.fsm import FSM


def to_mermaid(fsm: FSM, show_conditions: bool = True) -> str:
    lines: List[str] = ["stateDiagram-v2"]

    if fsm.default_state is not None:
        lines.append(f"    [*] --> {fsm.default_state.name}")

    for s in fsm.states.values():
        lines.append(f"    state {s.name}")

    for t in fsm.transitions:
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
