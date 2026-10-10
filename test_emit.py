from finesse.core import FSM, State, Transition
from finesse.core.expr import const, sig
from finesse.export.verilog import emit_fsm_oneprocess_enum


def build_simple_fsm() -> FSM:
    fsm = FSM(name="example_fsm", inputs={"start": 1, "done": 1})

    idle = State("S_IDLE", side_effect=False)
    busy = State("S_BUSY")
    done = State("S_DONE", side_effect=False)

    fsm.add_states([idle, busy, done], default="S_IDLE")

    fsm.add_transition(Transition("S_IDLE", "S_BUSY", sig("start") == 1))
    fsm.add_transition(Transition("S_BUSY", "S_DONE", sig("done") == 1))
    fsm.add_transition(Transition("S_DONE", "S_IDLE", const(1)))

    return fsm


if __name__ == "__main__":
    fsm = build_simple_fsm()
    verilog = emit_fsm_oneprocess_enum(fsm)
    print(verilog)