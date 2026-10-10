from __future__ import annotations

from collections import Counter
from math import cos, log1p, pi, sin
from textwrap import fill

from ..simulation import Simulator, Statistics


class SimulationViewer:
    def __init__(self, simulation: Simulator):
        if simulation.statistics.cycles != len(simulation.trace):
            raise ValueError("Viewer requires a complete recorded trace")
        try:
            import matplotlib.pyplot as plt
            from matplotlib.patches import FancyArrowPatch
            from matplotlib.path import Path
            from matplotlib.widgets import Button, CheckButtons, Slider
        except ImportError as error:
            raise ImportError('Install the viewer with: pip install -e ".[viewer]"') from error

        self.model = simulation.model
        self.trace = tuple(simulation.trace)
        self.initial_state = simulation.initial_state
        self.statistics = Statistics()
        for step in self.trace:
            self.statistics.observe(step)
        self.cycle = 0
        self.weighted = True
        self.playing = False
        self.figure, self.axes = plt.subplots(figsize=(12, 8))
        self.figure.subplots_adjust(bottom=0.30, top=0.9)
        self.axes.set(xlim=(-1.6, 1.6), ylim=(-1.4, 1.4), aspect="equal")
        self.axes.axis("off")
        self.figure.suptitle(self.model.name)
        self.positions = {
            state: (
                cos(pi / 2 - 2 * pi * index / len(self.model.states)),
                sin(pi / 2 - 2 * pi * index / len(self.model.states)),
            )
            for index, state in enumerate(self.model.states)
        }
        self.edges = []
        parallel = Counter()
        for index, transition in enumerate(self.model.transitions):
            start, end = self.positions[transition.src], self.positions[transition.dst]
            ordinal = parallel[transition.src, transition.dst]
            parallel[transition.src, transition.dst] += 1
            if transition.src == transition.dst:
                x, y = start
                radius = 0.25 + ordinal * 0.15
                path = Path(
                    [
                        (x - 0.04, y + 0.04),
                        (x - radius, y + radius),
                        (x + radius, y + radius),
                        (x + 0.04, y + 0.04),
                    ],
                    [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4],
                )
                edge = FancyArrowPatch(path=path, arrowstyle="-|>", mutation_scale=14)
            else:
                edge = FancyArrowPatch(
                    start,
                    end,
                    arrowstyle="-|>",
                    mutation_scale=14,
                    shrinkA=16,
                    shrinkB=16,
                    connectionstyle=f"arc3,rad={0.18 + ordinal * 0.18}",
                )
            edge.set_picker(5)
            self.axes.add_patch(edge)
            self.edges.append(edge)
        self.nodes = {}
        for state, (x, y) in self.positions.items():
            self.nodes[state] = self.axes.scatter([x], [y], s=460, zorder=3, picker=True)
            alignment = "left" if x > 0.1 else "right" if x < -0.1 else "center"
            label = fill(state.replace("_", " "), width=18)
            self.axes.text(x * 1.18, y * 1.18, label, ha=alignment, va="center", fontsize=8)
        self.status = self.figure.text(0.08, 0.235, "", fontsize=9, va="top")
        self.inspector = self.figure.text(
            0.08,
            0.14,
            "Click a state or edge to inspect full-run statistics.",
            fontsize=8,
            va="top",
        )
        self.slider = Slider(
            self.figure.add_axes((0.12, 0.09, 0.55, 0.025)),
            "Cycle",
            0,
            max(1, len(self.trace)),
            valinit=0,
            valstep=1,
        )
        self.slider.on_changed(self.set_cycle)
        self.previous = Button(self.figure.add_axes((0.12, 0.025, 0.10, 0.04)), "Previous")
        self.play = Button(self.figure.add_axes((0.24, 0.025, 0.10, 0.04)), "Play")
        self.next = Button(self.figure.add_axes((0.36, 0.025, 0.10, 0.04)), "Next")
        self.weights = CheckButtons(
            self.figure.add_axes((0.73, 0.025, 0.20, 0.09)), ["Full-run weights"], [True]
        )
        self.previous.on_clicked(lambda event: self.slider.set_val(max(0, self.cycle - 1)))
        self.next.on_clicked(
            lambda event: self.slider.set_val(min(len(self.trace), self.cycle + 1))
        )
        self.play.on_clicked(self.toggle_play)
        self.weights.on_clicked(self.toggle_weights)
        self.timer = self.figure.canvas.new_timer(interval=400)
        self.timer.add_callback(self.advance)
        self.figure.canvas.mpl_connect("pick_event", self.inspect)
        self.figure.canvas.mpl_connect("close_event", lambda event: self.timer.stop())
        self.set_cycle(0)

    def set_cycle(self, cycle: float) -> None:
        self.cycle = min(len(self.trace), max(0, int(cycle)))
        step = self.trace[self.cycle - 1] if self.cycle else None
        active = step.dst if step else self.initial_state
        for state, node in self.nodes.items():
            count = self.statistics.state_cycles[state]
            node.set_sizes([460 + 100 * log1p(count) if self.weighted else 460])
            node.set_color("#06b6d4" if state == active else "#cbd5e1")
        for index, edge in enumerate(self.edges):
            count = self.statistics.transition_counts[index]
            selected = step is not None and step.transition_id == index
            edge.set_color("#f97316" if selected else "#64748b")
            edge.set_linewidth(1.5 + log1p(count) if self.weighted else 1.5)
            edge.set_alpha(1 if selected or count else 0.3)
            edge.set_linestyle("-" if count else "--")
        detail = f"Initial state: {active}"
        if step:
            action = "hold" if step.transition_id is None else f"edge {step.transition_id}"
            values = ", ".join(f"{name}={value}" for name, value in step.inputs.items())
            detail = f"{step.src} → {step.dst} ({action})\n{fill(values, width=110)}"
        self.status.set_text(f"Cycle {self.cycle}/{len(self.trace)}   {detail}")
        self.figure.canvas.draw_idle()

    def toggle_weights(self, event=None) -> None:
        self.weighted = not self.weighted
        self.set_cycle(self.cycle)

    def toggle_play(self, event=None) -> None:
        self.playing = not self.playing
        self.play.label.set_text("Pause" if self.playing else "Play")
        if self.playing:
            if self.cycle == len(self.trace):
                self.slider.set_val(0)
            self.timer.start()
        else:
            self.timer.stop()

    def advance(self) -> None:
        if self.cycle < len(self.trace):
            self.slider.set_val(self.cycle + 1)
        if self.cycle == len(self.trace) and self.playing:
            self.toggle_play()

    def inspect(self, event) -> None:
        for state, node in self.nodes.items():
            if event.artist is node:
                self.inspector.set_text(
                    f"{state}: {self.statistics.state_cycles[state]} source cycles, "
                    f"{self.statistics.holds[state]} implicit holds"
                )
                break
        for index, edge in enumerate(self.edges):
            if event.artist is edge:
                transition = self.model.transitions[index]
                detail = (
                    f"Edge {index}: {transition.src} → {transition.dst}   "
                    f"{transition.cond.to_verilog()}"
                )
                self.inspector.set_text(
                    f"{fill(detail, width=120)}\n"
                    f"{self.statistics.transition_counts[index]} traversals (full run)"
                )
                break
        self.figure.canvas.draw_idle()

    def show(self) -> None:
        import matplotlib.pyplot as plt

        plt.show()
