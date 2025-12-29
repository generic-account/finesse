# backtrack_example.py
from finesse_fsm import FSM, State, Transition
from finesse_fsm.export.verilog import emit_fsm_oneprocess_enum
from finesse_fsm.core.expr import sig, const


def build_backtrack_fsm() -> FSM:
    """
    FSM model of the C++ backtrack(Solver &s) function.

    Each original enum State is a State here.
    Branch conditions are modeled as boolean inputs (0/1) using the Expr DSL.
    """

    # Boolean inputs that drive the FSM decisions.
    # All are 1-bit flags.
    inputs = {
        # CHECK_ROOT
        "decision_levels_zero": 1,

        # CUT_LOADED
        "cut_lt_trail_size": 1,

        # DV_LOOP_REASON_LOADED
        "reason_is_unit_decision": 1,   # mem_resp_i == -1
        "has_more_trail_after_i": 1,    # (i + 1) < trail_size

        # BACKTRACK_LOOP
        "trail_nonempty_from_cut": 1,   # (trail_size - 1) >= cut

        # BACKTRACK_LOOP_VAR_LOADED
        "i_lt_prop_head": 1,
        "is_conflict_var": 1,           # var == conflict_var_idx

        # UNDO_LOOP_CLAUSE_CNT_LOADED
        "revert_len_gt_zero": 1,        # revert_len > 0

        # UNDO_LOOP_UC_UPDATED
        "has_more_clauses_to_revert": 1,  # (j + 1) < revert_len

        # BACKTRACK_LOOP_CLEAR_VAR
        "has_more_trail_to_unwind": 1,  # (i - 1) >= cut

        # POST_BACKTRACK_LOOP
        "can_flip_decision_var": 1,     # decision_var != -1 && !phase_tried[decision_var]
    }

    fsm = FSM(name="backtrack_fsm", inputs=inputs)

    # States mirroring the C++ enum State
    states = [
        State("CHECK_ROOT", side_effect=False),
        State("CUT_LOADED"),
        State("DV_LOOP_VAR_LOADED"),
        State("DV_LOOP_REASON_LOADED"),
        State("BACKTRACK_LOOP"),
        State("BACKTRACK_LOOP_VAR_LOADED"),
        State("UNDO_LOOP"),
        State("UNDO_LOOP_CLAUSE_LIST_LOADED"),
        State("UNDO_LOOP_CLAUSE_CNT_LOADED"),
        State("UNDO_LOOP_LIT_LOADED"),
        State("UNDO_LOOP_UC_LOADED"),
        State("UNDO_LOOP_UC_UPDATED"),
        State("BACKTRACK_LOOP_CLEAR_VAR"),
        State("POST_BACKTRACK_LOOP"),
        State("ENQUEUE_FLIPPED"),
        State("PROPAGATE"),
        State("UNSAT"),
    ]

    # CHECK_ROOT is the initial state in the C++ code
    fsm.add_states(states, default="CHECK_ROOT")

    # --- Transitions using Expr conditions ---

    # CHECK_ROOT:
    # if (s.decision_levels == 0) state = UNSAT; else state = CUT_LOADED;
    fsm.add_transition(
        Transition(
            src="CHECK_ROOT",
            dst="UNSAT",
            cond=(sig("decision_levels_zero") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="CHECK_ROOT",
            dst="CUT_LOADED",
            cond=(sig("decision_levels_zero") == 0),
        )
    )

    # CUT_LOADED:
    # if (cut < s.trail_size) state = DV_LOOP_VAR_LOADED; else state = BACKTRACK_LOOP;
    fsm.add_transition(
        Transition(
            src="CUT_LOADED",
            dst="DV_LOOP_VAR_LOADED",
            cond=(sig("cut_lt_trail_size") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="CUT_LOADED",
            dst="BACKTRACK_LOOP",
            cond=(sig("cut_lt_trail_size") == 0),
        )
    )

    # DV_LOOP_VAR_LOADED:
    # always load reason_clause[var] -> DV_LOOP_REASON_LOADED
    fsm.add_transition(
        Transition(
            src="DV_LOOP_VAR_LOADED",
            dst="DV_LOOP_REASON_LOADED",
            cond=const(1),
        )
    )

    # DV_LOOP_REASON_LOADED:
    # if (mem_resp_i == -1) { decision_var = var; state = BACKTRACK_LOOP; }
    # else if ((i + 1) < trail_size) { i++; state = DV_LOOP_VAR_LOADED; }
    # else { state = BACKTRACK_LOOP; }
    fsm.add_transition(
        Transition(
            src="DV_LOOP_REASON_LOADED",
            dst="BACKTRACK_LOOP",
            cond=(sig("reason_is_unit_decision") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="DV_LOOP_REASON_LOADED",
            dst="DV_LOOP_VAR_LOADED",
            cond=((sig("reason_is_unit_decision") == 0) & (sig("has_more_trail_after_i") == 1)),
        )
    )
    fsm.add_transition(
        Transition(
            src="DV_LOOP_REASON_LOADED",
            dst="BACKTRACK_LOOP",
            cond=((sig("reason_is_unit_decision") == 0) & (sig("has_more_trail_after_i") == 0)),
        )
    )

    # BACKTRACK_LOOP:
    # if (s.trail_size - 1 >= cut) state = BACKTRACK_LOOP_VAR_LOADED;
    # else state = POST_BACKTRACK_LOOP;
    fsm.add_transition(
        Transition(
            src="BACKTRACK_LOOP",
            dst="BACKTRACK_LOOP_VAR_LOADED",
            cond=(sig("trail_nonempty_from_cut") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="BACKTRACK_LOOP",
            dst="POST_BACKTRACK_LOOP",
            cond=(sig("trail_nonempty_from_cut") == 0),
        )
    )

    # BACKTRACK_LOOP_VAR_LOADED:
    # if (i < prop_head || is_conflict_var) state = UNDO_LOOP;
    # else state = BACKTRACK_LOOP_CLEAR_VAR;
    fsm.add_transition(
        Transition(
            src="BACKTRACK_LOOP_VAR_LOADED",
            dst="UNDO_LOOP",
            cond=((sig("i_lt_prop_head") == 1) | (sig("is_conflict_var") == 1)),
        )
    )
    fsm.add_transition(
        Transition(
            src="BACKTRACK_LOOP_VAR_LOADED",
            dst="BACKTRACK_LOOP_CLEAR_VAR",
            cond=((sig("i_lt_prop_head") == 0) & (sig("is_conflict_var") == 0)),
        )
    )

    # UNDO_LOOP:
    # loads clause list based on var_value -> UNDO_LOOP_CLAUSE_LIST_LOADED
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP",
            dst="UNDO_LOOP_CLAUSE_LIST_LOADED",
            cond=const(1),
        )
    )

    # UNDO_LOOP_CLAUSE_LIST_LOADED:
    # loads var_negative_len/var_positive_len -> UNDO_LOOP_CLAUSE_CNT_LOADED
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_CLAUSE_LIST_LOADED",
            dst="UNDO_LOOP_CLAUSE_CNT_LOADED",
            cond=const(1),
        )
    )

    # UNDO_LOOP_CLAUSE_CNT_LOADED:
    # if (revert_len > 0) { j = 0; state = UNDO_LOOP_LIT_LOADED; }
    # else state = BACKTRACK_LOOP_CLEAR_VAR;
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_CLAUSE_CNT_LOADED",
            dst="UNDO_LOOP_LIT_LOADED",
            cond=(sig("revert_len_gt_zero") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_CLAUSE_CNT_LOADED",
            dst="BACKTRACK_LOOP_CLEAR_VAR",
            cond=(sig("revert_len_gt_zero") == 0),
        )
    )

    # UNDO_LOOP_LIT_LOADED:
    # always go to UNDO_LOOP_UC_LOADED
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_LIT_LOADED",
            dst="UNDO_LOOP_UC_LOADED",
            cond=const(1),
        )
    )

    # UNDO_LOOP_UC_LOADED:
    # always go to UNDO_LOOP_UC_UPDATED
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_UC_LOADED",
            dst="UNDO_LOOP_UC_UPDATED",
            cond=const(1),
        )
    )

    # UNDO_LOOP_UC_UPDATED:
    # if ((j + 1) < revert_len) state = UNDO_LOOP_LIT_LOADED;
    # else state = BACKTRACK_LOOP_CLEAR_VAR;
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_UC_UPDATED",
            dst="UNDO_LOOP_LIT_LOADED",
            cond=(sig("has_more_clauses_to_revert") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="UNDO_LOOP_UC_UPDATED",
            dst="BACKTRACK_LOOP_CLEAR_VAR",
            cond=(sig("has_more_clauses_to_revert") == 0),
        )
    )

    # BACKTRACK_LOOP_CLEAR_VAR:
    # if ((i - 1) >= cut) state = BACKTRACK_LOOP_VAR_LOADED;
    # else state = POST_BACKTRACK_LOOP;
    fsm.add_transition(
        Transition(
            src="BACKTRACK_LOOP_CLEAR_VAR",
            dst="BACKTRACK_LOOP_VAR_LOADED",
            cond=(sig("has_more_trail_to_unwind") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="BACKTRACK_LOOP_CLEAR_VAR",
            dst="POST_BACKTRACK_LOOP",
            cond=(sig("has_more_trail_to_unwind") == 0),
        )
    )

    # POST_BACKTRACK_LOOP:
    # if (decision_var != -1 && phase_tried[decision_var] == 0)
    #     state = ENQUEUE_FLIPPED;
    # else { decision_levels--; state = CHECK_ROOT; }
    fsm.add_transition(
        Transition(
            src="POST_BACKTRACK_LOOP",
            dst="ENQUEUE_FLIPPED",
            cond=(sig("can_flip_decision_var") == 1),
        )
    )
    fsm.add_transition(
        Transition(
            src="POST_BACKTRACK_LOOP",
            dst="CHECK_ROOT",
            cond=(sig("can_flip_decision_var") == 0),
        )
    )

    # ENQUEUE_FLIPPED:
    # enqueue(...) then state = PROPAGATE;
    fsm.add_transition(
        Transition(
            src="ENQUEUE_FLIPPED",
            dst="PROPAGATE",
            cond=const(1),
        )
    )

    # PROPAGATE and UNSAT are terminal in this FSM model (no outgoing edges).

    return fsm


def run_demo() -> None:
    """
    Drive the backtrack FSM through a typical "successful backtrack" path:
    - not at root
    - cut < trail_size
    - find a decision var
    - do one backtrack iteration without UNDO_LOOP
    - flip decision var
    - go to PROPAGATE
    """
    fsm = build_backtrack_fsm()

    fsm.reset()
    print(f"Initial state: {fsm.current_state.name}")

    # For each step, we only need to set the inputs relevant to the
    # current state; others default to 0.
    inputs_sequence = [
        # CHECK_ROOT: decision_levels != 0 -> CUT_LOADED
        {"decision_levels_zero": 0},

        # CUT_LOADED: cut < trail_size -> DV_LOOP_VAR_LOADED
        {"cut_lt_trail_size": 1},

        # DV_LOOP_VAR_LOADED: -> DV_LOOP_REASON_LOADED (unconditional)
        {},

        # DV_LOOP_REASON_LOADED: reason_is_unit_decision -> BACKTRACK_LOOP
        {"reason_is_unit_decision": 1},

        # BACKTRACK_LOOP: trail_nonempty_from_cut -> BACKTRACK_LOOP_VAR_LOADED
        {"trail_nonempty_from_cut": 1},

        # BACKTRACK_LOOP_VAR_LOADED: neither i < prop_head nor conflict_var -> CLEAR_VAR
        {"i_lt_prop_head": 0, "is_conflict_var": 0},

        # BACKTRACK_LOOP_CLEAR_VAR: no more trail to unwind -> POST_BACKTRACK_LOOP
        {"has_more_trail_to_unwind": 0},

        # POST_BACKTRACK_LOOP: can_flip_decision_var -> ENQUEUE_FLIPPED
        {"can_flip_decision_var": 1},

        # ENQUEUE_FLIPPED: -> PROPAGATE
        {},
    ]

    visited = fsm.multi_step(inputs_sequence)

    print("Visited states:")
    for step_idx, st in enumerate(visited, start=1):
        print(f"  step {step_idx}: {st.name}")

    print("\nMermaid diagram (without labels):\n")
    print(fsm.to_mermaid(show_conditions=False))

    print("\nMermaid diagram (with labels):\n")
    print(fsm.to_mermaid(show_conditions=True))

    print("\nGenerated Verilog:\n")
    print(emit_fsm_oneprocess_enum(fsm))


if __name__ == "__main__":
    run_demo()
