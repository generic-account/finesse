# finesse/export/verilog.py

from __future__ import annotations

from typing import Dict, List, Optional

from ..core import FSM, State, Transition


def _state_bits(num_states: int) -> int:
    if num_states <= 1:
        return 1
    n = num_states - 1
    bits = 0
    while n > 0:
        bits += 1
        n >>= 1
    return bits


def emit_fsm_oneprocess_enum(
    fsm: FSM,
    module_name: Optional[str] = None,
    *,
    clk: str = "clk",
    rst: str = "rst",
) -> str:
    """
    Emit a SystemVerilog module for the given FSM.

    Style:
      - typedef enum logic [N-1:0] { S0, S1, ... } state_t;
      - one-process FSM: always_ff @(posedge clk) with case (state_q)
      - explicit "stay in same state" transitions in an else block

    Args:
        fsm: the FSM to emit
        module_name: name of the Verilog module (defaults to fsm.name)
        clk: clock signal name
        rst: reset signal name (active-high, synchronous)

    Returns:
        A string containing the Verilog/SystemVerilog code.
    """
    if module_name is None:
        module_name = fsm.name

    # Order states deterministically
    states: List[State] = list(fsm.states.values())
    if not states:
        raise ValueError("FSM has no states")

    # Determine reset state
    if fsm.default_state is not None:
        reset_state_name = fsm.default_state.name
    else:
        reset_state_name = states[0].name

    # Compute bits for enum
    state_bits = _state_bits(len(states))

    lines: List[str] = []

    # Module header
    lines.append(f"module {module_name} (")

    # Build port list without commas first
    ports: List[str] = []

    # clk and rst
    ports.append(f"    input  logic {clk}")
    ports.append(f"    input  logic {rst}")

    # FSM inputs
    for name, width in fsm.inputs.items():
        if width <= 1:
            ports.append(f"    input  logic {name}")
        else:
            ports.append(f"    input  logic [{width-1}:0] {name}")

    # Automatically generated outputs
    ports.append("    output logic ready_o")
    ports.append("    output logic done_o")

    # Emit with trailing commas on all but the last
    for i, p in enumerate(ports):
        if i < len(ports) - 1:
            lines.append(p + ",")
        else:
            lines.append(p)

    lines.append(");")
    lines.append("")

    # State enum
    lines.append(f"    typedef enum logic [{state_bits-1}:0] {{")
    for i, s in enumerate(states):
        sep = "," if i < len(states) - 1 else ""
        lines.append(f"        {s.name}{sep}")
    lines.append("    } state_t;")
    lines.append("")
    lines.append("    state_t state_q;")
    lines.append("")

    # One-process FSM
    lines.append(f"    always_ff @(posedge {clk}) begin")
    lines.append(f"        if ({rst}) begin")
    lines.append(f"            state_q <= {reset_state_name};")
    lines.append("            ready_o <= 1'b1;")
    lines.append("            done_o  <= 1'b0;")
    lines.append("        end else begin")
    lines.append("            ready_o <= 1'b0;")
    lines.append("            done_o  <= 1'b0;")
    lines.append("            case (state_q)")

    # Group transitions by source state
    transitions_by_src: Dict[str, List[Transition]] = {s.name: [] for s in states}
    for t in fsm.transitions:
        transitions_by_src[t.src].append(t)

    # Per-state case arms
    for s in states:
        lines.append(f"                {s.name}: begin")
        outgoing = transitions_by_src.get(s.name, [])

        # Idle/reset state: ready_o high, done_o low
        if s.name == reset_state_name:
            lines.append("                    ready_o <= 1'b1;")
            lines.append("                    done_o  <= 1'b0;")

        # Terminal states (no outgoing transitions, non-idle): done_o high
        elif not outgoing:
            lines.append("                    ready_o <= 1'b0;")
            lines.append("                    done_o  <= 1'b1;")

        if outgoing:
            for idx, t in enumerate(outgoing):
                cond = t.cond.to_verilog()
                if idx == 0:
                    lines.append(f"                    if ({cond}) begin")
                else:
                    lines.append(f"                    else if ({cond}) begin")
                lines.append(f"                        state_q <= {t.dst};")
                lines.append("                    end")
            # Explicit stay in same state (compact one-line form)
            lines.append(f"                    else state_q <= {s.name};")
        else:
            # No outgoing transitions: go back to reset/idle state
            lines.append(f"                    state_q <= {reset_state_name};")

        lines.append("                end")

    # Default case
    lines.append("                default: begin")
    lines.append(f"                    state_q <= {reset_state_name};")
    lines.append("                end")

    lines.append("            endcase")
    lines.append("        end")
    lines.append("    end")
    lines.append("")
    lines.append("endmodule")
    lines.append("")

    return "\n".join(lines)
