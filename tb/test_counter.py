# tb/test_counter.py
"""
Cocotb testbench for rtl/counter.sv.

Simulation parameters
---------------------
WIDTH : int
    Counter bit width. Set to 4 in the runner for fast overflow cycling.

Run via::

    make sim # SIM=verilator (default)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cocotb
import cocotb_tools.runner
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

#  Helpers


async def _start_clock(dut: Any) -> None:
    """Start a 10 ns clock on dut.clk."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())


async def _tick(dut: Any) -> None:
    """Advance one rising edge, then settle one delta step.

    Verilator resumes the cocotb coroutine inside the VPI clock-change
    callback,before the posedge has propagated through DFF evaluation.
    Timer(1, unit="step") forces a zero-simtime delta so Verilator
    completes eval() before any signal is read.
    """
    await RisingEdge(dut.clk)
    await Timer(1, unit="step")


async def _reset(dut: Any, cycles: int = 2) -> None:
    """Assert active-low synchronous reset for `cycles` clock edges."""
    dut.rst_n.value = 0
    dut.en.value = 0
    for _ in range(cycles):
        await _tick(dut)
    dut.rst_n.value = 1


# Tests


@cocotb.test()
async def test_reset_clears_outputs(dut: Any) -> None:
    """Active-low synchronous reset drives count and overflow to zero, even with en asserted."""
    await _start_clock(dut)
    dut.en.value = 1  # en high, reset must override
    dut.rst_n.value = 0
    for _ in range(2):
        await _tick(dut)
    assert dut.count.value == 0, f"Expected count=0,    got {int(dut.count.value)}"
    assert dut.overflow.value == 0, f"Expected overflow=0, got {int(dut.overflow.value)}"


@cocotb.test()
async def test_count_increments_when_enabled(dut: Any) -> None:
    """Counter increments by 1 each rising edge when en is asserted."""
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1
    for expected in range(1, 8):
        await _tick(dut)
        assert (
            dut.count.value == expected
        ), f"Cycle {expected}: expected count={expected}, got {int(dut.count.value)}"


@cocotb.test()
async def test_count_holds_when_disabled(dut: Any) -> None:
    """Counter holds its value across multiple cycles when en is deasserted."""
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1
    for _ in range(3):
        await _tick(dut)  # count -> 3
    held = int(dut.count.value)
    dut.en.value = 0
    for _ in range(4):
        await _tick(dut)
        assert dut.count.value == held, f"Expected count={held} (held), got {int(dut.count.value)}"
        assert dut.overflow.value == 0, "overflow should be cleared when en=0"


@cocotb.test()
async def test_overflow_timing(dut: Any) -> None:
    """
    Verify overflow register update timing.

    overflow is computed via the non-blocking assignment ``overflow <= &count``
    inside the always_ff block. The registered output therefore appears one
    cycle *after* count reaches MAX; i.e. simultaneously with the wrap to 0::

        count:    ... -> MAX ->  0  ->  1  -> ...
        overflow: ... ->  0  ->  1  ->  0  -> ...
    """
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1

    width = len(dut.count.value)
    max_val = (1 << width) - 1

    # Advance until count reaches MAX
    while int(dut.count.value) != max_val:
        await _tick(dut)

    # At MAX: overflow not yet high; still reflects &(MAX-1) from prior edge
    assert dut.count.value == max_val, f"Expected count={max_val}"
    assert dut.overflow.value == 0, "overflow should be 0 while count=MAX"

    # Next edge: count wraps to 0, overflow register captures &MAX = 1
    await _tick(dut)
    assert dut.count.value == 0, f"Expected count=0 after wrap, got {int(dut.count.value)}"
    assert dut.overflow.value == 1, f"Expected overflow=1 at wrap,  got {int(dut.overflow.value)}"

    # Edge after: count=1, overflow clears
    await _tick(dut)
    assert dut.count.value == 1, f"Expected count=1,            got {int(dut.count.value)}"
    assert dut.overflow.value == 0, f"Expected overflow=0 post-wrap, got {int(dut.overflow.value)}"


@cocotb.test()
async def test_overflow_clears_when_disabled(dut: Any) -> None:
    """Deasserting en while overflow is high immediately clears it (else branch sets overflow=0)."""
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1

    width = len(dut.count.value)
    max_val = (1 << width) - 1

    # Run through one full wrap to reach overflow=1
    while int(dut.count.value) != max_val:
        await _tick(dut)
    await _tick(dut)  # count=0, overflow=1

    assert dut.overflow.value == 1, "Precondition: overflow should be 1 at wrap"

    # Deassert en; else branch fires on the next edge
    dut.en.value = 0
    await _tick(dut)
    assert (
        dut.overflow.value == 0
    ), f"Expected overflow=0 when disabled, got {int(dut.overflow.value)}"
    assert (
        dut.count.value == 0
    ), f"Expected count=0 (held), got {int(dut.count.value)}"  # count held at 0


@cocotb.test()
async def test_reset_mid_count(dut: Any) -> None:
    """Reset asserted mid-count clears count and overflow regardless of current value."""
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1
    for _ in range(5):
        await _tick(dut)  # count -> 5
    assert int(dut.count.value) == 5, f"Precondition: expected count=5, got {int(dut.count.value)}"

    # Assert reset mid-count; en stays high to confirm reset overrides
    dut.rst_n.value = 0
    for _ in range(2):
        await _tick(dut)
    assert (
        dut.count.value == 0
    ), f"Expected count=0 after mid-count reset, got {int(dut.count.value)}"
    assert (
        dut.overflow.value == 0
    ), f"Expected overflow=0 after mid-count reset, got {int(dut.overflow.value)}"


@cocotb.test()
async def test_multiple_overflow_cycles(dut: Any) -> None:
    """Overflow pulses correctly and consistently across 3 consecutive wrap cycles."""
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1

    width = len(dut.count.value)
    max_val = (1 << width) - 1

    for cycle in range(3):
        # Advance until count reaches MAX
        while int(dut.count.value) != max_val:
            await _tick(dut)

        assert dut.overflow.value == 0, f"Wrap {cycle}: overflow should be 0 while count=MAX"

        # Wrap edge: count -> 0, overflow -> 1
        await _tick(dut)
        assert (
            dut.count.value == 0
        ), f"Wrap {cycle}: expected count=0 after wrap, got {int(dut.count.value)}"
        assert (
            dut.overflow.value == 1
        ), f"Wrap {cycle}: expected overflow=1 at wrap, got {int(dut.overflow.value)}"

        # Edge after wrap: count -> 1, overflow clears
        await _tick(dut)
        assert (
            dut.overflow.value == 0
        ), f"Wrap {cycle}: expected overflow=0 post-wrap, got {int(dut.overflow.value)}"


@cocotb.test()
async def test_reenable_resumes_from_held_value(dut: Any) -> None:
    """Re-asserting en after a hold period resumes counting from the held value, not from zero."""
    await _start_clock(dut)
    await _reset(dut)
    dut.en.value = 1
    for _ in range(5):
        await _tick(dut)  # count -> 5
    held = int(dut.count.value)
    assert held == 5, f"Precondition: expected count=5, got {held}"

    # Hold for 3 cycles; count must not drift
    dut.en.value = 0
    for _ in range(3):
        await _tick(dut)
        assert dut.count.value == held, f"Expected count={held} (held), got {int(dut.count.value)}"

    # Re-enable; must resume from held value, not restart from 0
    dut.en.value = 1
    for expected in range(held + 1, held + 4):
        await _tick(dut)
        assert (
            dut.count.value == expected
        ), f"Expected count={expected} after re-enable, got {int(dut.count.value)}"


#  Pytest / Cocotb runner


def test_counter_runner() -> None:
    """Compile the DUT and execute all @cocotb.test() cases via Verilator."""
    from cocotb_tools.runner import get_runner

    sim = os.getenv("SIM", "verilator")
    proj_path = Path(__file__).resolve().parent.parent

    runner = get_runner(sim)
    runner.build(
        sources=[proj_path / "rtl" / "counter.sv"],
        hdl_toplevel="counter",
        always=True,
        parameters={"WIDTH": 4},
        build_args=["--sv", "--trace", "--trace-fst", "--Wno-WIDTHEXPAND"],
        waves=True,
    )
    runner.test(
        hdl_toplevel="counter",
        test_module="test_counter",
        waves=True,  # Supports wave outputs
    )
