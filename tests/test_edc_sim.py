"""Behavioral test of the Amaranth Edc: encode, decode, error injection."""
import random
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from amaranth.sim import Simulator
from amaranth_fifo.edc import Edc, edc_pwidth, hamming_positions, single_error_threshold

random.seed(1234)


def run(dsize):
    dut = Edc(dsize=dsize)
    pw = edc_pwidth(dsize)

    async def tb(ctx):
        async def rd_tick():
            ctx.set(dut.RdClk, 0)
            await ctx.delay(1e-9)
            ctx.set(dut.RdClk, 1)
            await ctx.delay(1e-9)

        for _ in range(50):
            data = random.getrandbits(dsize)
            ctx.set(dut.Ein, data)
            await ctx.delay(1e-9)
            enc = ctx.get(dut.Eout)
            chk = ctx.get(dut.P_out)
            assert enc == data, (dsize, "Eout passthrough")

            # no error
            ctx.set(dut.Din, enc)
            ctx.set(dut.P_in, chk)
            await ctx.delay(1e-9)
            assert ctx.get(dut.Dout) == data, (dsize, "no-error Dout")
            await rd_tick()
            assert ctx.get(dut.error) == 0b00, (dsize, "no-error status")

            # single data bit error -> corrected
            bit = random.randrange(dsize)
            ctx.set(dut.Din, enc ^ (1 << bit))
            await ctx.delay(1e-9)
            assert ctx.get(dut.Dout) == data, (dsize, "single-error correction")
            await rd_tick()
            assert ctx.get(dut.error) == 0b01, (dsize, "single-error status")

            # single check bit error (not the overall parity bit)
            cbit = random.randrange(pw - 1)
            ctx.set(dut.Din, enc)
            ctx.set(dut.P_in, chk ^ (1 << cbit))
            await ctx.delay(1e-9)
            assert ctx.get(dut.Dout) == data, (dsize, "chk-bit error Dout")
            await rd_tick()
            assert ctx.get(dut.error) == 0b01, (dsize, "chk-bit error status")

            # double data bit error -> detected
            if dsize >= 2:
                b1, b2 = random.sample(range(dsize), 2)
                ctx.set(dut.Din, enc ^ (1 << b1) ^ (1 << b2))
                ctx.set(dut.P_in, chk)
                await ctx.delay(1e-9)
                await rd_tick()
                assert ctx.get(dut.error) == 0b10, (dsize, "double-error status")

    sim = Simulator(dut)
    sim.add_testbench(tb)
    sim.run()
    print(f"  DSIZE={dsize:2d} pw={pw} thr={single_error_threshold(dsize)} OK")


for d in (1, 2, 3, 4, 5, 8, 11, 12, 26, 27, 32, 36, 57, 58, 64):
    run(d)
print("EDC simulation: all OK")
