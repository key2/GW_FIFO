"""Amaranth equivalents of the two FIFO netlists used by the RiscV AE350 SOC
(``RiscV_AE350_SOC/data/fifo_top_128to32.v`` / ``fifo_top_32to128.v``).

Those files are GowinSynthesis V1.9.11 *post-synthesis netlists* (LUT/DFF/
SDPB/SDPX9B primitives), so they cannot be reproduced byte-for-byte; instead
the factories below build the same FIFO configuration from the parametric
:class:`~amaranth_fifo.fifo_top.FifoTop`.  The configurations were recovered
from the netlists and verified by cycle-exact co-simulation (iverilog,
netlist vs. generated RTL, asynchronous WrClk/RdClk, near-empty / mid /
near-full stimulus, 0 mismatches on Empty/Full/Almost_*/Wnum/Q):

fifo_top_128to32 (DDR3 read FIFO, 128 -> 32 bits):
    WDEPTH=64  WDSIZE=128  RDEPTH=256 RDSIZE=32  (ASIZE=6, RASIZE=8)
    EBR based, En_Reset + Reset_Synchronization,
    Al_Full_Flag static single threshold AFULL=48,
    standard FIFO (no FWFT), no output register, no counts, no ECC.

fifo_top_32to128 (DDR3 write FIFO, 36 -> 144 bits):
    WDEPTH=256 WDSIZE=36   RDEPTH=64  RDSIZE=144 (ASIZE=8, RASIZE=6)
    EBR based, En_Reset + Reset_Synchronization, FWFT,
    Count_W (Wnum[8:0]),
    Al_Empty_Flag static single threshold AEMPT=24,
    Al_Full_Flag  static single threshold AFULL=200,
    no output register, no ECC.

Generate drop-in RTL replacements (same module names and ports) with:

    python -m amaranth_fifo.soc_fifos [output_directory]
"""

from .fifo_top import FifoTop

__all__ = ["fifo_top_128to32", "fifo_top_32to128"]


def fifo_top_128to32():
    """128-bit x 64 write side -> 32-bit x 256 read side ("Small" branch)."""
    return FifoTop(
        wdepth=64, wdsize=128, rdepth=256, rdsize=32,
        memory_style="ebr",
        en_reset=True, reset_synchronization=True,
        almost_full_flag=True, full_th_mode="static_single", afull=48,
    )


def fifo_top_32to128():
    """36-bit x 256 write side -> 144-bit x 64 read side ("Big" branch)."""
    return FifoTop(
        wdepth=256, wdsize=36, rdepth=64, rdsize=144,
        memory_style="ebr",
        en_reset=True, reset_synchronization=True,
        fwft=True,
        count_w=True,
        almost_empty_flag=True, empty_th_mode="static_single", aempt=24,
        almost_full_flag=True, full_th_mode="static_single", afull=200,
    )


def _main(argv=None):
    import os
    import sys

    from amaranth.back import verilog

    out_dir = (argv or sys.argv[1:] or ["."])[0]
    for name, factory in (("fifo_top_128to32", fifo_top_128to32),
                          ("fifo_top_32to128", fifo_top_32to128)):
        top = factory()
        path = os.path.join(out_dir, name + ".v")
        with open(path, "w") as f:
            f.write(verilog.convert(top, name=name, ports=top.ports()))
        print(f"wrote {path}")


if __name__ == "__main__":
    _main()
