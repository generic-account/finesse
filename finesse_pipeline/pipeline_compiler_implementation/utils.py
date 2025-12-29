#!/usr/bin/env python3
"""
# [treesource] These are utils for the pipeline compiler that may be useful
"""


def sync_outputs(outputs: list["Var"]) -> list["Var"]:
    # Dumb stupid code to make sure all the outputs are synced, make sure to set when call
    max_delay = max((output._delay for output in outputs))
    new_output = []
    for output in outputs:
        while output._delay < max_delay:
            output = output.inc_delay()
        new_output.append(output)
    return new_output


def get_max_delay(outputs: list["Var"]) -> int:
    """Get the maximum delay from a list of Vars

    Args:
        outputs (list[Var]): List of Vars to check"""

    return max(output._delay for output in outputs)
