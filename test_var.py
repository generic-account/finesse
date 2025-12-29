#!/usr/bin/env python3
"""
This is the test for variables in the module
"""

from finesse_pipeline.pipeline_compiler_implementation.module_implementation import (
    PipelineCompiler,
)
from finesse_pipeline.pipeline_compiler_implementation.var import Var


def test_var_compile_with_operations():
    module = PipelineCompiler("test_module")
    a = Var(module, 32, True, "a")
    b = Var(module, 32, True, "b")
    c = a + b
    d = a - b
    e = a * b
    # f = a / b
    g = a == b
    h = a != b
    i = a < b
    j = a <= b
    k = a > b
    l = a >= b
    g.set_name("g_result")
    m = a.clip_size(16)
    m.set_name("m_result")
    module.compile(inputs=[a, b], outputs=[c, d, e, g, h, i, j, k, l, m])


def test_var_sync():
    module = PipelineCompiler("test_module_sync")
    a = Var(module, 8, True, "a")
    b = Var(module, 8, True, "b")

    # Increment the a delay and make sure it changed
    for _ in range(3):
        a = a.inc_delay()
    assert a._delay == 3, f"the delay is {a._delay}, expected 3"

    # Sync b to a and make sure it changed
    b, a = b.sync_delay(a)
    assert b._delay == a._delay, f"the delay is {b._delay}, expected {a._delay}"

    # Increment the b delay and make sure it changed
    for _ in range(2):
        b = b.inc_delay()
    assert b._delay == 5, f"the delay is {b._delay}, expected 5"


def test_var_slice():
    module = PipelineCompiler("test_module")
    a = Var(module, 16, True, "a")

    # Slice the variable
    b = a[0:8]
    b.set_name("b_result")
    c = a[8:16]
    c.set_name("c_result")

    # Make sure the bit widths are correct
    assert b._signal.nbits == 8, f"the bit width is {b._signal.nbits}, expected 8"
    assert c._signal.nbits == 8, f"the bit width is {c._signal.nbits}, expected 8"

    module.compile(inputs=[a], outputs=[b, c])


if __name__ == "__main__":
    test_var_compile_with_operations()
    test_var_sync()
    test_var_slice()
    print(f"var tests passed")
