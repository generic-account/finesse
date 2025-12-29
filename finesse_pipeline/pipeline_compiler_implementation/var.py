#!/usr/bin/env python3
"""
# [treesource] This is the representation of a variable for the pipeline compiler
"""

# IMPORTANT NOTE: Currently each operation saves their input sequentially to prevent running too long, there are ways to monitor the length of path then only save when needed to reduce latency

from typing import Self
from migen import *

from .module_implementation import (
    PipelineCompiler,
)
from .mux import (
    unsafe_mux,
    unsafe_mux_with_signal_select,
)


class Unsafe_Var:
    def __init__(
        self,
        module: PipelineCompiler,
        bits: int,
        signed: bool,
        name: str | None = None,
        constant_value: int | None = None,
        delay: int = 0,  # DONT ADD THIS PARAMETER UNLESS YOU KNOW WHAT YOU ARE DOING!!!
    ):
        self.module: PipelineCompiler = module

        # Only allow str characters in the name for user declared variables, numbers are saved for the internal representation
        # Also make sure there are no duplicates
        assert name is None or name.replace("_", "").isalpha(), (
            f"Users can only use alphabetic characters and underscores in variable names, got {name}"
        )
        if name is None:
            name = self.module.get_unique_name()
        else:
            self.module.use_name(name)
        self.name = name

        # Save the bits and the signedness for the operations below
        self.bits = bits
        self.signed = signed

        # This is the actual signal representing the variable in hardware
        self._signal = Signal(bits_sign=(bits, signed), name=name)

        # The constant value is set if this variable is a constant
        if constant_value is not None:
            self.module.comb += self._signal.eq(constant_value)

        # This is the cycle after input the variable is valid, this is to prevent any syncing issues
        self._delay = delay

    def make_new(
        self,
        module: PipelineCompiler,
        bits: int,
        signed: bool,
        constant_value: int | None = None,
        delay: int = 0,
    ) -> Self:
        """Create a new variable. This makes sure that the new variable has the same class as the one called before and gets around circular imports

        Args:
            module: The module to create the variable in
            bits: The bit width of the variable
            signed: Whether the variable is signed
            constant_value: The constant value to set (if any)
            delay: The delay to set (default is 0)

        Returns:
            A new variable in the same module
        """

        return type(self)(
            module, bits, signed, constant_value=constant_value, delay=delay
        )

    def set_name(self, new_name: str) -> None:
        """Set a new name for the variable

        Args:
            new_name: The new name to set
        """

        # NOTE: This isnt really good practice. Had to look at source code below
        # https://github.com/m-labs/migen/blob/master/migen/fhdl/structure.py#L305-L428
        self._signal.name_override = new_name

    def sync_delay(self, other: Self) -> (Self, Self):
        """This function syncs two variables to the same delay, returning the new synced variables in the same order

        Args:
            self (_type_): _description_
        """

        max_delay = max(self._delay, other._delay)

        var1 = self
        var2 = other

        while var1._delay < max_delay:
            var1 = var1.inc_delay()

        while var2._delay < max_delay:
            var2 = var2.inc_delay()

        return var1, var2

    def register_control(self) -> Self:
        # This makes sure that we dont have any combinational loops by registering the variable
        # TODO: Implement this less lazily later and actuall check the logic to see if there are combinational issues

        return self.inc_delay()

    def get_delay(self) -> int:
        return self._delay

    def inc_delay(self) -> Self:
        # Increments the delay and retuns the new variable
        result = type(self)(self.module, self.bits, self.signed, delay=self._delay + 1)
        # NOTE: This does not take into account stalling, use the below function if stalling is needed
        self.module.sync += result._signal.eq(self._signal)
        return result

    def inc_delay_with_stalling(self) -> Self:
        # Increments the delay and retuns the new variable
        result = type(self)(self.module, self.bits, self.signed, delay=self._delay + 1)

        # Make sure the delay for self and result are the same, then inc the smaller one
        while self._delay < result._delay:
            self = self.inc_delay()
        while result._delay < self._delay:
            result = result.inc_delay()

        select = self.module.get_good_to_save_in_register()
        self.module.sync += result._signal.eq(
            unsafe_mux_with_signal_select(select, self, result)._signal
        )
        return result

    def set_delay(self, new_delay: int) -> Self:
        """Set the delay of the variable to a new value

        Args:
            new_delay: The new delay to set

        Returns:
            A new variable with the specified delay
        """

        # MAKE SURE THE NEW DELAY IS GREATER THAN THE CURRENT DELAY
        assert new_delay >= self._delay, (
            f"New delay {new_delay} must be greater than or equal to current delay {self._delay}"
        )

        result = self
        while result._delay < new_delay:
            result = result.inc_delay()
        return result

    def __getitem__(self, key):
        """Get a slice or bit of the variable
        Args:
            key: The slice or bit to get
        Returns:
            A new variable representing the slice
        """

        if isinstance(key, slice):
            # Get the slice
            start = key.start if key.start is not None else 0
            stop = key.stop if key.stop is not None else self.bits
            step = key.step if key.step is not None else 1

            # Calculate the new bits
            new_bits = (stop - start + (step - 1)) // step

            result = type(self)(self.module, new_bits, self.signed, delay=self._delay)

            # Create the combinational logic for the slice
            self.module.comb += result._signal.eq(
                Cat(*[self._signal[i] for i in range(start, stop, step)])
            )

            return result
        else:
            # Get a single bit
            assert isinstance(key, int), "Key must be an integer or slice"

            result = type(self)(self.module, 1, False, delay=self._delay)

            # Create the combinational logic for the bit
            self.module.comb += result._signal.eq(self._signal[key])

            return result

    def __setitem__(self, key, value: Self) -> None:
        """Set a slice or bit of the variable
        Args:
            key: The slice or bit to set
            value: The value to set the slice or bit to
        """

        # Add in logic to make sure the signals have the same delay
        value = value.set_delay(self._delay)

        if isinstance(key, slice):
            # Get the slice
            start = key.start if key.start is not None else 0
            stop = key.stop if key.stop is not None else self.bits
            step = key.step if key.step is not None else 1

            # Create the combinational logic for the slice
            self.module.comb += Cat(
                *[self._signal[i] for i in range(start, stop, step)]
            ).eq(value._signal)
        else:
            # Get a single bit
            assert isinstance(key, int), "Key must be an integer or slice"

            # Create the combinational logic for the bit
            self.module.comb += self._signal[key].eq(value._signal)

    def __setitem__(self, key, value: Self) -> None:
        """Set a slice or bit of the variable
        Args:
            key: The slice or bit to set
            value: The value to set the slice or bit to
        """

        # Add in logic to make sure the signals have the same delay
        value = value.set_delay(self._delay)

        if isinstance(key, slice):
            # Get the slice
            start = key.start if key.start is not None else 0
            stop = key.stop if key.stop is not None else self.bits
            step = key.step if key.step is not None else 1

            # Create the combinational logic for the slice
            self.module.comb += Cat(
                *[self._signal[i] for i in range(start, stop, step)]
            ).eq(value._signal)
        else:
            # Get a single bit
            assert isinstance(key, int), "Key must be an integer or slice"

            # Create the combinational logic for the bit
            self.module.comb += self._signal[key].eq(value._signal)

    def clip_size(self, new_bits: int) -> Self:
        """Clip the variable to a new bit size, overflow sets to max value, underflow to 0

        Args:
            new_bits: The new bit size to clip to

        Returns:
            A new variable representing the clipped value
        """

        if self.signed:
            # The case it is signed calculate the new max and min values
            max_value = (1 << (new_bits - 1)) - 1
            min_value = -(1 << (new_bits - 1))

        else:
            # Same but unsigned
            max_value = (1 << new_bits) - 1
            min_value = 0

        result = type(self)(self.module, new_bits, self.signed)
        self.module.comb += (
            If(
                self._signal > max_value,
                result._signal.eq(max_value),
            )
            .Elif(
                self._signal < min_value,
                result._signal.eq(min_value),
            )
            .Else(
                result._signal.eq(self._signal),
            )
        )

        return result

    # These are the math operations that are going to be overloaded
    def __add__(self, other: Self) -> Self:
        """Overload the addition operator for variables

        Args:
            other: The other variable to add

        Returns:
            A new variable representing the sum
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = max(self.bits, other.bits) + 1  # +1 for potential overflow
        signed = self.signed or other.signed

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal + other._signal)

        return result

    def __sub__(self, other: Self) -> Self:
        """Overload the subtraction operator for variables

        Args:
            other: The other variable to subtract

        Returns:
            A new variable representing the difference
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = (
            max(self.bits, other.bits) + 1
        )  # +1 for potential overflow (I think, not sure about subtraction)
        signed = self.signed or other.signed

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal - other._signal)

        return result

    def __mul__(self, other: Self) -> Self:
        """Overload the multiplication operator for variables

        Args:
            other: The other variable to multiply

        Returns:
            A new variable representing the product
        """

        assert not isinstance(other, int), (
            f"Multiplication by integer is not supported yet, using value {other}"
        )

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = self.bits + other.bits  # Multiplication increases bit width alot
        signed = self.signed or other.signed

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal * other._signal)

        return result

    def __truediv__(self, other: "Var") -> "Var":
        """Overload the division operator for variables

        Args:
            other: The other variable to divide

        Returns:
            A new variable representing the quotient
        """

        # NOTE: I dont really plan on implementing this right now, division in hardware cane be pipelined and isnt needed at the moment
        # If we do decide to implement it we should do a for loop by the bits for repeat logic then use the operations already defined
        raise NotImplementedError("Division operator is not implemented yet")

    def __eq__(self, other: Self) -> Self:
        """Overload the equality operator for variables

        Args:
            other: The other variable to compare to
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = 1
        signed = False

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal == other._signal)

        return result

    def __ne__(self, other: Self) -> Self:
        """Overload the inequality operator for variables

        Args:
            other: The other variable to compare to
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = 1
        signed = False

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal != other._signal)

        return result

    def __lt__(self, other: Self) -> Self:
        """Overload the less than operator for variables

        Args:
            other: The other variable to compare to
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = 1
        signed = False

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal < other._signal)

        return result

    def __le__(self, other: Self) -> Self:
        """Overload the less than or equal to operator for variables

        Args:
            other: The other variable to compare to
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = 1
        signed = False

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal <= other._signal)

        return result

    def __gt__(self, other: Self) -> Self:
        """Overload the greater than operator for variables

        Args:
            other: The other variable to compare to
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = 1
        signed = False

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal > other._signal)

        return result

    def __ge__(self, other: Self) -> Self:
        """Overload the greater than or equal to operator for variables

        Args:
            other: The other variable to compare to
        """

        # Add in logic to make sure the signals have the same delay
        self, other = self.sync_delay(other)

        max_bits = 1
        signed = False

        result = type(self)(self.module, max_bits, signed)
        self.module.comb += result._signal.eq(self._signal >= other._signal)

        return result


class Var(Unsafe_Var):
    def clip_size(self, new_bits: int) -> "Var":
        """Clip the variable to a new bit size, overflow sets to max value, underflow to 0

        Args:
            new_bits: The new bit size to clip to

        Returns:
            A new variable representing the clipped value
        """

        result = super().clip_size(new_bits)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    # These are the math operations that are going to be overloaded
    def __add__(self, other: "Var") -> "Var":
        """Overload the addition operator for variables

        Args:
            other: The other variable to add

        Returns:
            A new variable representing the sum
        """

        result = super().__add__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __sub__(self, other: "Var") -> "Var":
        """Overload the subtraction operator for variables

        Args:
            other: The other variable to subtract

        Returns:
            A new variable representing the difference
        """

        result = super().__sub__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __mul__(self, other: "Var") -> "Var":
        """Overload the multiplication operator for variables

        Args:
            other: The other variable to multiply

        Returns:
            A new variable representing the product
        """

        result = super().__mul__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __truediv__(self, other: "Var") -> "Var":
        """Overload the division operator for variables

        Args:
            other: The other variable to divide

        Returns:
            A new variable representing the quotient
        """

        result = super().__mul__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __eq__(self, other: "Var") -> "Var":
        """Overload the equality operator for variables

        Args:
            other: The other variable to compare to
        """

        result = super().__eq__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __ne__(self, other: "Var") -> "Var":
        """Overload the inequality operator for variables

        Args:
            other: The other variable to compare to
        """

        result = super().__ne__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __lt__(self, other: "Var") -> "Var":
        """Overload the less than operator for variables

        Args:
            other: The other variable to compare to
        """

        result = super().__lt__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __le__(self, other: "Var") -> "Var":
        """Overload the less than or equal to operator for variables

        Args:
            other: The other variable to compare to
        """

        result = super().__le__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __gt__(self, other: "Var") -> "Var":
        """Overload the greater than operator for variables

        Args:
            other: The other variable to compare to
        """

        result = super().__gt__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result

    def __ge__(self, other: "Var") -> "Var":
        """Overload the greater than or equal to operator for variables

        Args:
            other: The other variable to compare to
        """

        result = super().__ge__(other)

        # Make sure the combinational length isnt too long
        result = result.register_control()

        return result
