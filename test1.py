from finesse_fsm import FSM, State, Transition
from finesse_fsm.core.expr import sig, const


def build_fsm() -> FSM:
    # Define input signals (name -> bit width)
    inputs = {
        "start": 1,
        "done": 1,
    }

    fsm = FSM(name="example_fsm", inputs=inputs)

    # Define states
    idle = State("IDLE", side_effect=False)
    busy = State("BUSY", side_effect=True)
    done = State("DONE", side_effect=False)

    # Register states, marking IDLE as the default
    fsm.add_states([idle, busy, done], default="IDLE")

    # Add transitions with Expr conditions

    # IDLE -> BUSY when start == 1
    fsm.add_transition(
        Transition(
            src="IDLE",
            dst="BUSY",
            cond=(sig("start") == 1),
        )
    )

    # BUSY -> DONE when done == 1
    fsm.add_transition(
        Transition(
            src="BUSY",
            dst="DONE",
            cond=(sig("done") == 1),
        )
    )

    # DONE -> IDLE unconditionally
    fsm.add_transition(
        Transition(
            src="DONE",
            dst="IDLE",
            cond=const(1),
        )
    )

    return fsm


def run_demo() -> None:
    fsm = build_fsm()

    # Reset FSM to default state
    fsm.reset()
    print(f"Initial state: {fsm.current_state.name}")

    # Define a simple input sequence
    input_sequence = [
        {"start": 0, "done": 0},  # stay in IDLE
        {"start": 1, "done": 0},  # go to BUSY
        {"start": 0, "done": 0},  # stay in BUSY
        {"start": 0, "done": 1},  # go to DONE
        {"start": 0, "done": 0},  # go back to IDLE (unconditional)
    ]

    visited = fsm.multi_step(input_sequence)

    print("Visited states:")
    for i, st in enumerate(visited, start=1):
        print(f"  step {i}: {st.name}")

    # Generate a Mermaid diagram
    diagram = fsm.visualize("fsm_test1.mmd", show_conditions=False)
    print("\nMermaid diagram written to fsm_test1.mmd")
    print("Diagram preview:\n")
    print(diagram)


if __name__ == "__main__":
    run_demo()
