#!/usr/bin/env python3
"""
# [treesource] Generate a Verilog file with parameter definitions using Migen
"""

from migen import *
from migen.fhdl import verilog


# NOTE: This class is meant to be extended and modified, but may not be worth using
class VerilogGenerator(Module):
    """
    This is python code to generate generic modules for verilog, this is meant to be extended and modified
    """

    def __init__(self, params: dict = None, inputs: dict = None, outputs: dict = None):
        """
        params: Dictionary of parameter names and values
                Example: {"WIDTH": 32, "DEPTH": 1024}

        inputs: Dictionary of input signal names and bit widths
                Example: {"clk": 1, "data_in": 8, "address": 16}

        outputs: Dictionary of output signal names and bit widths
                 Example: {"data_out": 8, "valid": 1}
        """

        # Store parameters as attributes
        self.params = params if params is not None else {}

        # Create input signals
        if inputs:
            for name, width in inputs.items():
                sig = Signal(width, name=name)
                setattr(self, name, sig)

        # Create output signals
        if outputs:
            for name, width in outputs.items():
                sig = Signal(width, name=name)
                setattr(self, name, sig)

        # Dummy signal to make sure module compiles
        self.dummy = Signal()


def save_module(
    module: VerilogGenerator | Module,
    ios: set[Signal] | None = None,
    output_dir: str = "hdl",
    module_name: str = "should_be_uniquely_named",
):
    """Save the module

    Args:
        module_name: Name of the module (without .v extension)
        ios: Set of input/output signals to include in the module interface
        output_dir: Directory to save the file
        module_name: Name of the module (without .v extension)
    """

    # Convert to Verilog
    verilog_code = verilog.convert(module, name=module_name, ios=ios)

    # Include a timescale
    verilog_code_str = f"`timescale 1ns / 1ps\n\n{verilog_code}"

    # Write to file
    filepath = f"{output_dir}/{module_name}.v"
    with open(filepath, "w") as f:
        f.write(verilog_code_str)
