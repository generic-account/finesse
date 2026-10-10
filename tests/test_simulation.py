import unittest
from dataclasses import FrozenInstanceError

from finesse import FSM, State, Transition
from finesse.core.expr import const, sig
from finesse.export.verilog import emit_fsm_oneprocess_enum


def build_fsm():
    fsm = FSM("test", {"go": 1, "value": 3})
    fsm.add_states([State("IDLE"), State("BUSY"), State("DONE")], default="IDLE")
    fsm.add_transition(Transition("IDLE", "BUSY", sig("go")))
    fsm.add_transition(Transition("BUSY", "BUSY", sig("value") == 1))
    fsm.add_transition(Transition("BUSY", "DONE", sig("value") == 2))
    fsm.add_transition(Transition("BUSY", "DONE", sig("value") >= 2))
    return fsm


class SimulationTests(unittest.TestCase):
    def test_priority_parallel_edges_and_holds(self):
        sim = build_fsm().simulator().run([{}, {"go": 1}, {"value": 1}, {}, {"value": 2}, {}])
        self.assertEqual([step.transition_id for step in sim.trace], [None, 0, 1, None, 2, None])
        self.assertEqual(sim.statistics.cycles, 6)
        self.assertEqual(sim.statistics.state_cycles, {"IDLE": 2, "BUSY": 3, "DONE": 1})
        self.assertEqual(sim.statistics.holds, {"IDLE": 1, "BUSY": 1, "DONE": 1})
        self.assertEqual(sim.statistics.transition_counts, {0: 1, 1: 1, 2: 1})
        self.assertEqual(sim.statistics.transition_matrix["BUSY", "BUSY"], 2)
        self.assertEqual(sim.uncovered_transitions, (3,))

    def test_parallel_edge_identity(self):
        sim = build_fsm().simulator().run([{"go": 1}, {"value": 3}])
        self.assertEqual(sim.trace[-1].transition_id, 3)
        first = Transition("IDLE", "BUSY", sig("go"))
        second = Transition("IDLE", "BUSY", sig("go") == 0)
        self.assertNotEqual(first, second)

    def test_sessions_are_independent(self):
        fsm = build_fsm()
        first, second = fsm.simulator(), fsm.simulator()
        first.step({"go": 1})
        self.assertEqual(second.current_state, "IDLE")
        self.assertEqual(fsm.current_state.name, "IDLE")
        self.assertEqual(second.statistics.cycles, 0)

    def test_snapshot_survives_definition_changes(self):
        fsm = build_fsm()
        sim = fsm.simulator()
        fsm.add_transition(Transition("DONE", "IDLE", const(1)))
        fsm.inputs["later"] = 1
        sim.run([{"go": 1}, {"value": 2}, {}])
        self.assertEqual(sim.current_state, "DONE")
        self.assertNotIn("later", sim.model.inputs)
        self.assertEqual(len(sim.model.transitions), 4)

    def test_trace_inputs_are_normalized_and_immutable(self):
        inputs = {"go": 1}
        step = build_fsm().simulator().step(inputs)
        inputs["go"] = 0
        self.assertEqual(dict(step.inputs), {"go": 1, "value": 0})
        with self.assertRaises(TypeError):
            step.inputs["go"] = 0
        with self.assertRaises(FrozenInstanceError):
            step.dst = "DONE"
        with self.assertRaises(FrozenInstanceError):
            build_fsm().simulator().model.transitions[0].dst = "DONE"

    def test_invalid_inputs_do_not_advance(self):
        sim = build_fsm().simulator()
        for inputs in [{"typo": 1}, {"go": 2}, {"value": -1}, {"value": 8}, {"go": 0.5}]:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                sim.step(inputs)
        self.assertEqual(sim.current_state, "IDLE")
        self.assertEqual(sim.statistics.cycles, 0)
        self.assertEqual(sim.trace, [])

    def test_statistics_without_recording(self):
        sim = build_fsm().simulator(record=False).run({"go": 1} for _ in range(100))
        self.assertEqual(sim.trace, [])
        self.assertEqual(sim.statistics.cycles, 100)
        self.assertEqual(sim.statistics.holds["BUSY"], 99)

    def test_reset_clears_run(self):
        sim = build_fsm().simulator().run([{"go": 1}])
        sim.reset()
        self.assertEqual(sim.current_state, "IDLE")
        self.assertEqual(sim.statistics.cycles, 0)
        self.assertEqual(sim.trace, [])
        self.assertEqual(sim.step({}).cycle, 1)

    def test_explicit_initial_state(self):
        sim = build_fsm().simulator(initial_state="BUSY")
        sim.step({"value": 2})
        sim.reset()
        self.assertEqual(sim.current_state, "BUSY")
        with self.assertRaises(ValueError):
            build_fsm().simulator(initial_state="UNKNOWN")

    def test_legacy_api_uses_same_execution(self):
        fsm = build_fsm()
        inputs = [{}, {"go": 1}, {"value": 1}, {"value": 2}, {}]
        sim = fsm.simulator().run(inputs)
        self.assertEqual(
            [state.name for state in fsm.multi_step(inputs)], [step.dst for step in sim.trace]
        )
        fsm.reset()
        self.assertEqual(fsm.step({}).name, "IDLE")
        fsm.set_state("BUSY")
        self.assertEqual(fsm.step({"value": 2}).name, "DONE")
        with self.assertRaises(ValueError):
            fsm.set_state("UNKNOWN")

    def test_legacy_session_recompiles_after_graph_changes(self):
        fsm = build_fsm()
        fsm.multi_step([{"go": 1}, {"value": 2}])
        fsm.add_transition(Transition("DONE", "IDLE", const(1)))
        self.assertEqual(fsm.step({}).name, "IDLE")

    def test_switching_cost_includes_holds_without_cost(self):
        stats = build_fsm().simulator().run([{}, {"go": 1}, {"value": 1}, {"value": 2}]).statistics
        self.assertEqual(stats.switching_cost({"IDLE": 0, "BUSY": 1, "DONE": 3}), 2)
        for encoding in [
            {"IDLE": 0},
            {"IDLE": 0, "BUSY": 0, "DONE": 1},
            {"IDLE": -1, "BUSY": 1, "DONE": 3},
        ]:
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                stats.switching_cost(encoding)

    def test_terminal_export_holds_and_preserves_priority(self):
        code = emit_fsm_oneprocess_enum(build_fsm())
        terminal = code.split("DONE: begin")[1].split("end")[0]
        self.assertIn("state_q <= DONE;", terminal)
        self.assertLess(code.index("if ((value == 2))"), code.index("else if ((value >= 2))"))
        self.assertIn("done_o  <= 1'b1;", terminal)

    def test_mermaid_compatibility(self):
        from finesse.visualization import to_mermaid

        fsm = build_fsm()
        self.assertIn("BUSY --> DONE : (value == 2)", fsm.to_mermaid())
        self.assertEqual(fsm.to_mermaid(False).count("BUSY --> DONE"), 2)
        self.assertEqual(to_mermaid(fsm), fsm.to_mermaid())

    def test_model_validation(self):
        with self.assertRaises(ValueError):
            FSM("empty", {}).compile()
        fsm = build_fsm()
        fsm.inputs["bad"] = 0
        with self.assertRaises(ValueError):
            fsm.compile()

    def test_missing_default(self):
        fsm = FSM("no_default", {})
        fsm.add_state(State("ONLY"))
        with self.assertRaises(RuntimeError):
            fsm.simulator()
        self.assertIn("state_q <= ONLY;", emit_fsm_oneprocess_enum(fsm))
        self.assertEqual(fsm.simulator(initial_state="ONLY").step({}).dst, "ONLY")


if __name__ == "__main__":
    unittest.main()
