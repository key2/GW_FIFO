"""Amaranth translation of ``FIFO/data/fifo_top.v``.

``FifoTop`` is a thin wrapper around :class:`Fifo`, exactly like fifo_top.v
wraps fifo.v.  It accepts the same parameters/options and exposes the same
ports (aliased 1:1 to the inner FIFO instance).

Running this file as a script generates Verilog, e.g. the equivalent of the
``exfifo1`` configuration in this repository:

    python -m amaranth_fifo.fifo_top --wdepth 128 --wdsize 36 \
        --rdepth 32 --rdsize 144 --memory-style ebr \
        --almost-empty static_single --aempt 1 \
        --almost-full  static_single --afull 1 \
        --en-reset --reset-synchronization -o fifo_top.v
"""

from amaranth.hdl import Elaboratable, Module

from .fifo import Fifo

__all__ = ["FifoTop"]


class FifoTop(Elaboratable):
    """Top level, equivalent to `module_name (fifo_top) in fifo_top.v."""

    def __init__(self, **kwargs):
        self.fifo_inst = Fifo(**kwargs)
        # Alias every port of the inner FIFO so that FifoTop presents the
        # exact same interface (fifo_top.v is a pure feed-through).
        for port in self.fifo_inst.ports():
            setattr(self, port.name, port)

    def ports(self):
        return self.fifo_inst.ports()

    def elaborate(self, platform):
        m = Module()
        m.submodules.fifo_inst = self.fifo_inst
        return m


def _main(argv=None):
    import argparse

    from amaranth.back import verilog

    parser = argparse.ArgumentParser(
        description="Generate Verilog for the Gowin-style dual-clock FIFO")
    parser.add_argument("--name", default="fifo_top", help="module name")
    parser.add_argument("--wdepth", type=int, required=True)
    parser.add_argument("--wdsize", type=int, required=True)
    parser.add_argument("--rdepth", type=int, required=True)
    parser.add_argument("--rdsize", type=int, required=True)
    parser.add_argument("--asize", type=int, default=None)
    parser.add_argument("--rasize", type=int, default=None)
    parser.add_argument("--memory-style", choices=("ebr", "dsr", "lut"),
                        default="ebr")
    parser.add_argument("--en-reset", action="store_true")
    parser.add_argument("--reset-synchronization", action="store_true")
    parser.add_argument("--almost-empty", dest="empty_th_mode", default=None,
                        choices=("static_single", "static_dual",
                                 "dynamic_single", "dynamic_dual"))
    parser.add_argument("--aempt", type=int, default=1)
    parser.add_argument("--assert-empty-th", type=int, default=None)
    parser.add_argument("--deassert-empty-th", type=int, default=None)
    parser.add_argument("--almost-full", dest="full_th_mode", default=None,
                        choices=("static_single", "static_dual",
                                 "dynamic_single", "dynamic_dual"))
    parser.add_argument("--afull", type=int, default=1)
    parser.add_argument("--assert-full-th", type=int, default=None)
    parser.add_argument("--deassert-full-th", type=int, default=None)
    parser.add_argument("--count-w", action="store_true")
    parser.add_argument("--count-r", action="store_true")
    parser.add_argument("--en-ecc", action="store_true")
    parser.add_argument("--enable-force-error", action="store_true")
    parser.add_argument("--en-output-reg", action="store_true")
    parser.add_argument("--ctrl-by-rden", action="store_true")
    parser.add_argument("--fwft", action="store_true")
    parser.add_argument("-o", "--output", default=None,
                        help="output file (default: stdout)")
    args = parser.parse_args(argv)

    top = FifoTop(
        wdepth=args.wdepth, wdsize=args.wdsize,
        rdepth=args.rdepth, rdsize=args.rdsize,
        asize=args.asize, rasize=args.rasize,
        memory_style=args.memory_style,
        en_reset=args.en_reset,
        reset_synchronization=args.reset_synchronization,
        almost_empty_flag=args.empty_th_mode is not None,
        empty_th_mode=args.empty_th_mode or "static_single",
        aempt=args.aempt,
        assert_empty_th=args.assert_empty_th,
        deassert_empty_th=args.deassert_empty_th,
        almost_full_flag=args.full_th_mode is not None,
        full_th_mode=args.full_th_mode or "static_single",
        afull=args.afull,
        assert_full_th=args.assert_full_th,
        deassert_full_th=args.deassert_full_th,
        count_w=args.count_w, count_r=args.count_r,
        en_ecc=args.en_ecc, enable_force_error=args.enable_force_error,
        en_output_reg=args.en_output_reg, ctrl_by_rden=args.ctrl_by_rden,
        fwft=args.fwft,
    )
    output = verilog.convert(top, name=args.name, ports=top.ports())
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    _main()
