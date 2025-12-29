#!/usr/bin/env python3
"""
# [treesource] This is the representation of a mux
"""

from migen import *

from .utils import sync_outputs


def unsafe_mux(sel: "Var", in0: "Var", in1: "Var") -> "Var":
    """This is a mux, it does not save anything sequentially
    IMPORTANT, Make sure the inputs are synced before calling this function

    Args:
        sel (Var): The select signal
        in0 (Var): The first input
        in1 (Var): The second input

    Returns:
        Var: The output of the mux
    """

    # Make sure the Vars have the same module
    assert sel.module == in0.module == in1.module, (
        "All inputs must belong to the same module"
    )

    # Make sure the Vars have the same bit width
    assert in0.bits == in1.bits, "Input variables must have the same bit width"

    # Make sure the Vars have the same signedness
    # NOTE: This is not essential, but I want to enforce this so the output is well defined
    assert in0.signed == in1.signed, "Input variables must have the same signedness"

    # Make sure everything is synced
    # sel, in0, in1 = sync_outputs([sel, in0, in1])

    # Create the output variable
    output = in0.make_new(sel.module, in0.bits, in0.signed)

    # Implement the mux logic
    sel_signal = sel._signal
    in0_signal = in0._signal
    in1_signal = in1._signal
    output_signal = output._signal

    output.module.comb += [
        If(sel_signal, output_signal.eq(in0_signal)).Else(output_signal.eq(in1_signal))
    ]

    # Make sure the delay for each input is the same and set the output delay accordingly
    assert in0._delay == in1._delay, (
        f"Input variables must have the same delay, but have {in0._delay} and {in1._delay}"
    )
    assert in0._delay == sel._delay, (
        f"Select variable must have the same delay as inputs, but has {sel._delay}"
    )
    output._delay = in0._delay

    return output


def unsafe_mux_with_signal_select(sel_signal: Signal, in0: "Var", in1: "Var") -> "Var":
    """This is a mux, it does not save anything sequentially, using a Signal as select
        IMPORTANT, Make sure the inputs are synced before calling this function

    Args:
        sel (Signal): The select signal
        in0 (Var): The first input
        in1 (Var): The second input

    Returns:
        Var: The output of the mux
    """

    # Make sure the Vars have the same module
    assert in0.module == in1.module, "All inputs must belong to the same module"

    # Make sure the Vars have the same bit width
    assert in0.bits == in1.bits, "Input variables must have the same bit width"

    # Make sure everything is synced
    # in0, in1 = sync_outputs([in0, in1])

    # Create the output variable
    output = in0.make_new(in0.module, in0.bits, in0.signed, delay=in0._delay)

    # Implement the mux logic
    in0_signal = in0._signal
    in1_signal = in1._signal
    output_signal = output._signal

    # Double check that all the signals are the correct types
    assert isinstance(sel_signal, Signal)
    assert isinstance(in0_signal, Signal)
    assert isinstance(in1_signal, Signal)
    assert isinstance(output_signal, Signal)

    output.module.comb += [
        If(sel_signal, output_signal.eq(in0_signal)).Else(output_signal.eq(in1_signal))
    ]

    # Make sure the delay for each input is the same and set the output delay accordingly
    assert in0._delay == in1._delay, (
        f"Input variables must have the same delay, but have {in0._delay} and {in1._delay}"
    )
    output._delay = in0._delay

    return output


def safe_mux(sel: "Var", in0: "Var", in1: "Var") -> "Var":
    """This is a mux that ensures the select signal is properly delayed to match the inputs
        IMPORTANT, Make sure the inputs are synced before calling this function

    Args:
        sel (Var): The select signal
        in0 (Var): The first input
        in1 (Var): The second input

    Returns:
        Var: The output of the mux
    """

    # Make all the variables delayed so there is no timing issues
    sel = sel.inc_delay()
    in0 = in0.inc_delay()
    in1 = in1.inc_delay()

    # NOTE: The check to make sure they are synced is done in the unsafe_mux function
    return unsafe_mux(sel, in0, in1)
