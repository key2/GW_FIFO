"""Smoke simulation of the Amaranth Fifo in its Equal/Big/Small/ECC/FWFT
configurations, plus flags, counts, and synchronized reset."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from amaranth.sim import Simulator
from amaranth_fifo import Fifo

T = 1e-9


def run(dut, tb):
    sim = Simulator(dut)
    sim.add_testbench(tb)
    sim.run()


def make_step(ctx, dut):
    async def step():
        ctx.set(dut.WrClk, 1)
        ctx.set(dut.RdClk, 1)
        await ctx.delay(T)
        ctx.set(dut.WrClk, 0)
        ctx.set(dut.RdClk, 0)
        await ctx.delay(T)
    return step


def test_basic(name, dut, wr_vals, exp_rd, fwft=False, check_error=False):
    async def tb(ctx):
        step = make_step(ctx, dut)
        assert ctx.get(dut.Empty) == 1
        assert ctx.get(dut.Full) == 0
        # write burst
        ctx.set(dut.WrEn, 1)
        for v in wr_vals:
            ctx.set(dut.Data, v)
            await step()
        ctx.set(dut.WrEn, 0)
        for _ in range(4):     # pointer synchronization
            await step()
        assert ctx.get(dut.Empty) == 0, f"{name}: Empty must deassert"
        got = []
        ctx.set(dut.RdEn, 1)
        for _ in range(len(exp_rd) * 4 + 16):
            if fwft:
                if ctx.get(dut.Empty) == 0:
                    got.append(ctx.get(dut.Q))
                await step()
            else:
                empty_before = ctx.get(dut.Empty)
                await step()
                if not empty_before:
                    got.append(ctx.get(dut.Q))
            if check_error:
                assert ctx.get(dut.ERROR) == 0, f"{name}: ECC ERROR != 0"
            if len(got) >= len(exp_rd):
                break
        ctx.set(dut.RdEn, 0)
        assert got == list(exp_rd), f"{name}: got {got} exp {list(exp_rd)}"
        for _ in range(2):
            await step()
        assert ctx.get(dut.Empty) == 1, f"{name}: Empty must reassert"
    run(dut, tb)
    print(f"  {name}: OK")


# ---------------- Equal ----------------
test_basic("equal 16x8",
           Fifo(wdepth=16, wdsize=8, rdepth=16, rdsize=8),
           list(range(10, 20)), list(range(10, 20)))

# ---------------- Equal + output reg ----------------
# With En_Output_Reg + Ctrl_By_RdEn (non-FWFT) the Verilog read path has two
# stages, both gated by RdEn & ~Empty: Q lags by one qualified read cycle
# (first sample is the register's initial value).
test_basic("equal + en_output_reg + ctrl_by_rden",
           Fifo(wdepth=16, wdsize=8, rdepth=16, rdsize=8, en_output_reg=True,
                ctrl_by_rden=True),
           list(range(1, 9)), [0] + list(range(1, 8)))


# En_Output_Reg without Ctrl_By_RdEn: second stage is free running, so the
# last word still comes out one cycle after Empty asserts.
def test_output_reg_free():
    dut = Fifo(wdepth=16, wdsize=8, rdepth=16, rdsize=8, en_output_reg=True)

    async def tb(ctx):
        step = make_step(ctx, dut)
        vals = list(range(1, 9))
        ctx.set(dut.WrEn, 1)
        for v in vals:
            ctx.set(dut.Data, v)
            await step()
        ctx.set(dut.WrEn, 0)
        for _ in range(4):
            await step()
        got = []
        ctx.set(dut.RdEn, 1)
        for _ in range(len(vals)):
            await step()
            got.append(ctx.get(dut.Q))
        ctx.set(dut.RdEn, 0)
        await step()
        got.append(ctx.get(dut.Q))
        assert got == [0] + vals, f"output_reg_free: got {got}"
    run(dut, tb)
    print("  equal + en_output_reg (free running): OK")


test_output_reg_free()

# ---------------- Equal FWFT ----------------
test_basic("equal FWFT",
           Fifo(wdepth=16, wdsize=8, rdepth=16, rdsize=8, fwft=True),
           list(range(30, 38)), list(range(30, 38)), fwft=True)

# ---------------- Big: WDEPTH > RDEPTH ----------------
test_basic("big 8x4 -> 4x8",
           Fifo(wdepth=8, wdsize=4, rdepth=4, rdsize=8),
           [1, 2, 3, 4], [0x21, 0x43])

# ---------------- Small: WDEPTH < RDEPTH ----------------
test_basic("small 4x8 -> 8x4",
           Fifo(wdepth=4, wdsize=8, rdepth=8, rdsize=4),
           [0x21, 0x43], [1, 2, 3, 4])

# ---------------- ECC ----------------
test_basic("equal + ECC (36 bit)",
           Fifo(wdepth=16, wdsize=36, rdepth=16, rdsize=36, en_ecc=True),
           [0x123456789, 0xFEDCBA987, 0x5A5A5A5A5], 
           [0x123456789, 0xFEDCBA987, 0x5A5A5A5A5], check_error=True)

test_basic("equal + ECC + force_error tied off",
           Fifo(wdepth=8, wdsize=8, rdepth=8, rdsize=8, en_ecc=True,
                enable_force_error=True),
           [7, 8, 9], [7, 8, 9], check_error=True)


# ---------------- Full flag / counts / almost flags ----------------
def test_flags():
    dut = Fifo(wdepth=8, wdsize=8, rdepth=8, rdsize=8,
               almost_empty_flag=True, empty_th_mode="static_single", aempt=1,
               almost_full_flag=True, full_th_mode="static_single", afull=6,
               count_w=True, count_r=True)

    async def tb(ctx):
        step = make_step(ctx, dut)
        assert ctx.get(dut.Almost_Empty) == 1
        assert ctx.get(dut.Almost_Full) == 0
        ctx.set(dut.WrEn, 1)
        for v in range(8):
            ctx.set(dut.Data, v)
            await step()
        ctx.set(dut.WrEn, 0)
        for _ in range(4):
            await step()
        assert ctx.get(dut.Full) == 1, "Full must assert after 8 writes"
        assert ctx.get(dut.Wnum) == 8, f"Wnum {ctx.get(dut.Wnum)}"
        assert ctx.get(dut.Rnum) == 8, f"Rnum {ctx.get(dut.Rnum)}"
        assert ctx.get(dut.Almost_Full) == 1
        assert ctx.get(dut.Almost_Empty) == 0
        # drain
        ctx.set(dut.RdEn, 1)
        for _ in range(12):
            await step()
        ctx.set(dut.RdEn, 0)
        for _ in range(4):
            await step()
        assert ctx.get(dut.Empty) == 1
        assert ctx.get(dut.Full) == 0
        assert ctx.get(dut.Almost_Empty) == 1
        assert ctx.get(dut.Almost_Full) == 0
        assert ctx.get(dut.Wnum) == 0
        assert ctx.get(dut.Rnum) == 0
    run(dut, tb)
    print("  flags/counts: OK")


test_flags()


# ---------------- Synchronized reset ----------------
def test_reset_sync():
    dut = Fifo(wdepth=16, wdsize=8, rdepth=16, rdsize=8,
               en_reset=True, reset_synchronization=True)

    async def tb(ctx):
        step = make_step(ctx, dut)
        # release the power-on internal reset (two falling edges)
        for _ in range(3):
            await step()
        # write a few words
        ctx.set(dut.WrEn, 1)
        for v in (1, 2, 3):
            ctx.set(dut.Data, v)
            await step()
        ctx.set(dut.WrEn, 0)
        for _ in range(4):
            await step()
        assert ctx.get(dut.Empty) == 0
        # asynchronous reset pulse
        ctx.set(dut.Reset, 1)
        await ctx.delay(T)
        assert ctx.get(dut.Empty) == 1, "Empty must assert asynchronously"
        assert ctx.get(dut.Full) == 0
        ctx.set(dut.Reset, 0)
        for _ in range(3):
            await step()
        assert ctx.get(dut.Empty) == 1
        # FIFO must be functional again
        ctx.set(dut.WrEn, 1)
        ctx.set(dut.Data, 0x55)
        await step()
        ctx.set(dut.WrEn, 0)
        for _ in range(4):
            await step()
        assert ctx.get(dut.Empty) == 0
        ctx.set(dut.RdEn, 1)
        await step()
        ctx.set(dut.RdEn, 0)
        assert ctx.get(dut.Q) == 0x55
    run(dut, tb)
    print("  reset_synchronization: OK")


test_reset_sync()

print("FIFO simulation: all OK")
