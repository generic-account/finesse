import importlib.util
import unittest
from types import SimpleNamespace

from test_simulation import build_fsm

from finesse import FSM, State, Transition
from finesse.core.expr import const


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Optional viewer not installed")
class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import matplotlib

        matplotlib.use("Agg")

    def tearDown(self):
        import matplotlib.pyplot as plt

        plt.close("all")

    def test_scrubbing_playback_and_inspection(self):
        sim = build_fsm().simulator().run([{}, {"go": 1}, {"value": 1}, {"value": 2}, {}])
        viewer = sim.view(show=False)
        viewer.slider.set_val(3)
        self.assertEqual(viewer.cycle, 3)
        self.assertIn("edge 1", viewer.status.get_text())
        viewer.inspect(SimpleNamespace(artist=viewer.edges[2]))
        self.assertIn("1 traversals", viewer.inspector.get_text())
        viewer.inspect(SimpleNamespace(artist=viewer.nodes["BUSY"]))
        self.assertIn("2 source cycles", viewer.inspector.get_text())
        viewer.toggle_weights()
        self.assertFalse(viewer.weighted)
        viewer.toggle_play()
        viewer.advance()
        viewer.advance()
        self.assertEqual(viewer.cycle, 5)
        self.assertFalse(viewer.playing)
        self.assertIn("hold", viewer.status.get_text())
        viewer.toggle_play()
        self.assertEqual(viewer.cycle, 0)
        viewer.figure.canvas.draw()

    def test_empty_trace_and_single_state(self):
        fsm = FSM("one", {})
        fsm.add_state(State("ONLY"), default=True)
        viewer = fsm.simulator().view(show=False)
        viewer.advance()
        self.assertEqual(viewer.cycle, 0)
        viewer.figure.canvas.draw()

    def test_self_loops_and_parallel_edges_render(self):
        fsm = build_fsm()
        fsm.add_transition(Transition("BUSY", "BUSY", const(1)))
        viewer = fsm.simulator().run([{"go": 1}, {}]).view(show=False)
        self.assertEqual(len(viewer.edges), len(fsm.transitions))
        viewer.figure.canvas.draw()

    def test_viewer_is_a_run_snapshot(self):
        sim = build_fsm().simulator().run([{"go": 1}])
        viewer = sim.view(show=False)
        sim.run([{"value": 2}])
        sim.reset()
        self.assertEqual(len(viewer.trace), 1)
        self.assertEqual(viewer.statistics.cycles, 1)

    def test_unrecorded_run_is_rejected(self):
        sim = build_fsm().simulator(record=False).run([{}])
        with self.assertRaises(ValueError):
            sim.view(show=False)
