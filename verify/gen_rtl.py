"""Generate Amaranth RTL Verilog for the two SOC FIFO configurations."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from amaranth.back import verilog
from amaranth_fifo import FifoTop


def gen_128to32(afull, path):
    top = FifoTop(wdepth=64, wdsize=128, rdepth=256, rdsize=32,
                  memory_style="ebr",
                  en_reset=True, reset_synchronization=True,
                  almost_full_flag=True, full_th_mode="static_single",
                  afull=afull)
    with open(path, "w") as f:
        f.write(verilog.convert(top, name="fifo_top_128to32_rtl",
                                ports=top.ports()))


def gen_32to128(aempt, afull, path):
    top = FifoTop(wdepth=256, wdsize=36, rdepth=64, rdsize=144,
                  memory_style="ebr",
                  en_reset=True, reset_synchronization=True,
                  almost_empty_flag=True, empty_th_mode="static_single",
                  aempt=aempt,
                  almost_full_flag=True, full_th_mode="static_single",
                  afull=afull,
                  count_w=True, fwft=True)
    with open(path, "w") as f:
        f.write(verilog.convert(top, name="fifo_top_32to128_rtl",
                                ports=top.ports()))


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "128to32":
        gen_128to32(int(sys.argv[2]), sys.argv[3])
    else:
        gen_32to128(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
