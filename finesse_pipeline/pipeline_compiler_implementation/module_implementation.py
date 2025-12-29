#!/usr/bin/env python3
"""
# [treesource] This is a module implementation to make a pipeline compiler
"""

from migen import *

from .module_interface import save_module
from .utils import sync_outputs, get_max_delay


class PipelineCompiler(Module):
    signal_name_counter = 0

    def __init__(self, module_name: str):
        # Keep track of the names to make sure there are no duplicates
        self.used_names = set()
        self.prefix = "compiled_signal_"

        self.__module__ = module_name

        # This is sync logic to make sure the module compiles with a sys_clk, it doesnt do anything
        stupid = Signal(name="stupid_only_needed_for_clk")
        self.sync += stupid.eq(stupid)

    def get_unique_name(self) -> str:
        """Generate a unique internal signal name

        Returns:
            A unique signal name as a string
        """

        name = f"{self.prefix}{self.signal_name_counter}"
        self.signal_name_counter += 1

        self.use_name(name)

        return name

    def get_good_to_save_in_register(self) -> Signal:
        """Returns a signal object with 1 being a stall so dont save in register and 0 being good to save in register

        Returns:
            A unique signal name as a string
        """

        return self.stall

    def is_name_available_and_valid(self, name: str) -> bool:
        """Check if a name is already used in the module and valid

        Args:
            name: Name to check
        """
        return name not in self.used_names

    def use_name(self, name: str):
        """Mark a name as used in the module

        Args:
            name: Name to mark as used
        """

        # Double check that the name is valid
        assert self.is_name_available_and_valid(name), (
            f"Name {name} is already used or invalid with the used names {self.used_names}"
        )

        self.used_names.add(name)

    def compile(
        self,
        inputs: list["Var"],
        outputs: list["Var"],
        input_signals: list[Signal] | None = [],
        output_signals: list[Signal] | None = [],
    ):
        """Compile the module into a verilog file"""

        # Sync the outputs so everything comes out the same clock cycle, this is messy. Fuck it
        outputs = sync_outputs(outputs)

        # Convert the Var objects to their underlying signals
        ios = inputs + outputs

        # Add in the signals
        ios_signals = {var._signal for var in ios}

        # Add in the signals that are passed in as arguments for more flexibility
        ios_signals.update(input_signals)
        ios_signals.update(output_signals)

        save_module(
            self,
            ios=ios_signals,
            output_dir="test_output",
            module_name=self.__module__,
        )

        # Return the output variables as they have changed, useful for debugging
        return outputs


class PipelineCompilerWithValidSignals(PipelineCompiler):
    def __init__(self, module_name: str):
        super().__init__(module_name)

        # Add valid_in and valid_out signals
        self.valid_in = Signal(name="valid_in")
        self.valid_out = Signal(name="valid_out")

        # Track valid signal through pipeline stages
        self.valid_pipeline = []

    def compile(self, inputs: list["Var"], outputs: list["Var"]):
        """Compile the module into a verilog file"""

        # Sync the outputs so everything comes out the same clock cycle
        outputs = sync_outputs(outputs)

        max_depth = get_max_delay(outputs)

        # Set up valid signal pipelining based on max depth
        if max_depth > 0:
            # Create pipeline registers for valid signal
            self.valid_pipeline = [
                Signal(name=f"valid_stage_{i}") for i in range(max_depth)
            ]

            # First stage gets valid_in
            self.sync += [self.valid_pipeline[0].eq(self.valid_in)]

            # Subsequent stages pipeline through with stall support
            for i in range(1, max_depth):
                self.sync += [
                    self.valid_pipeline[i].eq(self.valid_pipeline[i - 1]),
                ]

            # valid_out is the last stage
            self.comb += self.valid_out.eq(self.valid_pipeline[-1])
        else:
            # No pipeline stages, valid_out = valid_in, not worrying about stalling here
            self.comb += self.valid_out.eq(self.valid_in)

        return super().compile(
            inputs,
            outputs,
            input_signals=[self.valid_in],
            output_signals=[self.valid_out],
        )
