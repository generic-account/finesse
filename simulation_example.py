from test1 import build_fsm


def build_simulation():
    return (
        build_fsm()
        .simulator()
        .run(
            [
                {"start": 0},
                {"start": 1},
                {"done": 0},
                {"done": 1},
                {},
            ]
            * 4
        )
    )


if __name__ == "__main__":
    simulation = build_simulation()
    print("Transition counts:", simulation.statistics.transition_counts)
    print("Uncovered transitions:", simulation.uncovered_transitions)
    simulation.view()
