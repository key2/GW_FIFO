"""Amaranth translation of ``FIFO/data/fifo.v`` (Gowin dual-clock FIFO core).

Every Verilog `define / parameter is mapped to a constructor parameter:

    parameters (fifo_parameter.v)         constructor argument
    -----------------------------         --------------------
    WDEPTH / WDSIZE                       wdepth / wdsize
    RDEPTH / RDSIZE                       rdepth / rdsize
    ASIZE / RASIZE                        asize / rasize (default: log2 of depth)
    AEMPT / AFULL                         aempt / afull
    AssertEmptyTh / DeassertEmptyTh       assert_empty_th / deassert_empty_th
    AssertFullTh / DeassertFullTh         assert_full_th / deassert_full_th

    `defines (fifo_define.v)              constructor argument
    ------------------------              --------------------
    `EBR_BASED/`DSR_BASED/`LUT_BASED      memory_style = "ebr"|"dsr"|"lut"
    `En_Reset                             en_reset
    `Reset_Synchronization                reset_synchronization
    `Al_Empty_Flag                        almost_empty_flag
    `Empty_S_Single_Th                    empty_th_mode = "static_single"
    `Empty_S_Dual_Th                      empty_th_mode = "static_dual"
    `Empty_D_Single_Th                    empty_th_mode = "dynamic_single"
    `Empty_D_Dual_Th                      empty_th_mode = "dynamic_dual"
    `Al_Full_Flag                         almost_full_flag
    `Full_S_Single_Th / `Full_S_Dual_Th   full_th_mode = "static_single"/"static_dual"
    `Full_D_Single_Th / `Full_D_Dual_Th   full_th_mode = "dynamic_single"/"dynamic_dual"
    `Count_W / `Count_R                   count_w / count_r
    `En_ECC                               en_ecc
    `Enable_force_error                   enable_force_error
    `En_Output_Reg                        en_output_reg
    `Ctrl_By_RdEn                         ctrl_by_rden
    `FWFT                                 fwft (first-word fall-through)

Ports keep the Verilog names.  Clocks and resets are ordinary input ports
(WrClk, RdClk, and Reset or WrReset/RdReset depending on the options); the
module builds its own local clock domains from them, including the negative
edge two-FF reset synchronizers of the `Reset_Synchronization option.

Note: ``memory_style`` selects between block RAM ("ebr"), distributed RAM
("dsr") and registers ("lut") in the original flow through Synplify
``syn_ramstyle`` attributes; in Amaranth the memory is emitted as a plain
memory and the mapping is left to the synthesis tool.  ECC (as in fifo.v) is
only available when WDEPTH == RDEPTH and requires "ebr".
"""

from amaranth.hdl import (
    C,
    Cat,
    ClockDomain,
    ClockSignal,
    Elaboratable,
    Module,
    Mux,
    ResetSignal,
    Signal,
    unsigned,
)
from amaranth.lib.memory import Memory

from .edc import Edc, edc_pwidth

__all__ = ["Fifo"]

_EMPTY_TH_MODES = ("static_single", "static_dual", "dynamic_single", "dynamic_dual")
_FULL_TH_MODES = _EMPTY_TH_MODES
_MEMORY_STYLES = ("ebr", "dsr", "lut")


def _log2_int(n, what):
    if n < 1 or n & (n - 1):
        raise ValueError(f"{what} must be a power of two, not {n}")
    return n.bit_length() - 1


class Fifo(Elaboratable):
    """Dual-clock FIFO, equivalent to module ``fifo`` in fifo.v."""

    def __init__(self, *, wdepth, wdsize, rdepth, rdsize,
                 asize=None, rasize=None,
                 memory_style="ebr",
                 en_reset=False, reset_synchronization=False,
                 almost_empty_flag=False, empty_th_mode="static_single",
                 aempt=1, assert_empty_th=None, deassert_empty_th=None,
                 almost_full_flag=False, full_th_mode="static_single",
                 afull=1, assert_full_th=None, deassert_full_th=None,
                 count_w=False, count_r=False,
                 en_ecc=False, enable_force_error=False,
                 en_output_reg=False, ctrl_by_rden=False,
                 fwft=False):
        # ---------------- parameter checks ----------------
        _log2_int(wdepth, "wdepth")
        _log2_int(rdepth, "rdepth")
        if wdepth * wdsize != rdepth * rdsize:
            raise ValueError("wdepth*wdsize must equal rdepth*rdsize")
        if memory_style not in _MEMORY_STYLES:
            raise ValueError(f"memory_style must be one of {_MEMORY_STYLES}")
        if almost_empty_flag and empty_th_mode not in _EMPTY_TH_MODES:
            raise ValueError(f"empty_th_mode must be one of {_EMPTY_TH_MODES}")
        if almost_full_flag and full_th_mode not in _FULL_TH_MODES:
            raise ValueError(f"full_th_mode must be one of {_FULL_TH_MODES}")
        if almost_empty_flag and empty_th_mode == "static_dual" and (
                assert_empty_th is None or deassert_empty_th is None):
            raise ValueError("static_dual empty mode needs assert_empty_th "
                             "and deassert_empty_th")
        if almost_full_flag and full_th_mode == "static_dual" and (
                assert_full_th is None or deassert_full_th is None):
            raise ValueError("static_dual full mode needs assert_full_th "
                             "and deassert_full_th")
        if en_ecc:
            if wdepth != rdepth:
                raise ValueError("ECC (en_ecc) requires WDEPTH == RDEPTH")
            if memory_style != "ebr":
                raise ValueError("ECC (en_ecc) requires memory_style='ebr'")
            edc_pwidth(wdsize)  # validates 1 <= wdsize <= 64
        if reset_synchronization and not en_reset:
            raise ValueError("reset_synchronization requires en_reset")

        self.wdepth, self.wdsize = wdepth, wdsize
        self.rdepth, self.rdsize = rdepth, rdsize
        self.asize = _log2_int(wdepth, "wdepth") if asize is None else asize
        self.rasize = _log2_int(rdepth, "rdepth") if rasize is None else rasize
        self.memory_style = memory_style
        self.en_reset = bool(en_reset)
        self.reset_synchronization = bool(reset_synchronization)
        self.almost_empty_flag = bool(almost_empty_flag)
        self.empty_th_mode = empty_th_mode
        self.aempt = aempt
        self.assert_empty_th = assert_empty_th
        self.deassert_empty_th = deassert_empty_th
        self.almost_full_flag = bool(almost_full_flag)
        self.full_th_mode = full_th_mode
        self.afull = afull
        self.assert_full_th = assert_full_th
        self.deassert_full_th = deassert_full_th
        self.count_w = bool(count_w)
        self.count_r = bool(count_r)
        self.en_ecc = bool(en_ecc)
        self.enable_force_error = bool(enable_force_error)
        self.en_output_reg = bool(en_output_reg)
        self.ctrl_by_rden = bool(ctrl_by_rden)
        self.fwft = bool(fwft)

        asize, rasize = self.asize, self.rasize

        # ---------------- ports (Verilog names) ----------------
        self.Data = Signal(wdsize)
        if self.en_reset:
            if self.reset_synchronization:
                self.Reset = Signal()
            else:
                self.WrReset = Signal()
                self.RdReset = Signal()
        self.WrClk = Signal()
        self.RdClk = Signal()
        self.WrEn = Signal()
        self.RdEn = Signal()
        if self.almost_empty_flag:
            if empty_th_mode == "dynamic_dual":
                self.AlmostEmptySetTh = Signal(rasize)
                self.AlmostEmptyClrTh = Signal(rasize)
            elif empty_th_mode == "dynamic_single":
                self.AlmostEmptyTh = Signal(rasize)
        if self.almost_full_flag:
            if full_th_mode == "dynamic_dual":
                self.AlmostFullSetTh = Signal(asize)
                self.AlmostFullClrTh = Signal(asize)
            elif full_th_mode == "dynamic_single":
                self.AlmostFullTh = Signal(asize)
        if self.count_w:
            self.Wnum = Signal(asize + 1)
        if self.count_r:
            self.Rnum = Signal(rasize + 1)
        if self.almost_empty_flag:
            self.Almost_Empty = Signal(init=1)
        if self.almost_full_flag:
            self.Almost_Full = Signal()
        if self.en_ecc:
            self.ERROR = Signal(2)
        self.Q = Signal(rdsize)
        self.Empty = Signal(init=1)
        self.Full = Signal()

    # ------------------------------------------------------------------
    def ports(self):
        ports = [self.Data]
        if self.en_reset:
            if self.reset_synchronization:
                ports.append(self.Reset)
            else:
                ports += [self.WrReset, self.RdReset]
        ports += [self.WrClk, self.RdClk, self.WrEn, self.RdEn]
        if self.almost_empty_flag:
            if self.empty_th_mode == "dynamic_dual":
                ports += [self.AlmostEmptySetTh, self.AlmostEmptyClrTh]
            elif self.empty_th_mode == "dynamic_single":
                ports.append(self.AlmostEmptyTh)
        if self.almost_full_flag:
            if self.full_th_mode == "dynamic_dual":
                ports += [self.AlmostFullSetTh, self.AlmostFullClrTh]
            elif self.full_th_mode == "dynamic_single":
                ports.append(self.AlmostFullTh)
        if self.count_w:
            ports.append(self.Wnum)
        if self.count_r:
            ports.append(self.Rnum)
        if self.almost_empty_flag:
            ports.append(self.Almost_Empty)
        if self.almost_full_flag:
            ports.append(self.Almost_Full)
        if self.en_ecc:
            ports.append(self.ERROR)
        ports += [self.Q, self.Empty, self.Full]
        return ports

    # ------------------------------------------------------------------
    @staticmethod
    def _gray2bin(m, gray, name):
        """gry2bin function of fifo.v (MSB-first XOR chain)."""
        n = len(gray)
        binary = Signal(n, name=name)
        m.d.comb += binary[n - 1].eq(gray[n - 1])
        for i in reversed(range(n - 1)):
            m.d.comb += binary[i].eq(binary[i + 1] ^ gray[i])
        return binary

    @staticmethod
    def _full_compare(wgraynext, wq2_rptr, msb):
        """wfull_val: next write gray pointer equals the synchronized read
        pointer with its two top bits inverted."""
        return wgraynext == Cat(wq2_rptr[:msb - 1], ~wq2_rptr[msb - 1:msb + 1])

    # ------------------------------------------------------------------
    def elaborate(self, platform):
        m = Module()
        wdepth, wdsize = self.wdepth, self.wdsize
        rdepth, rdsize = self.rdepth, self.rdsize
        asize, rasize = self.asize, self.rasize
        fwft = self.fwft

        # ------------------------------------------------------------------
        # Resets (WRst / RRst) and clock domains
        # ------------------------------------------------------------------
        if self.en_reset and self.reset_synchronization:
            # 2-FF synchronizers clocked on the FALLING clock edges, with
            # asynchronous assertion on Reset (as in fifo.v).
            m.domains += ClockDomain("rdn", clk_edge="neg", async_reset=True,
                                     local=True)
            m.d.comb += [
                ClockSignal("rdn").eq(self.RdClk),
                ResetSignal("rdn").eq(self.Reset),
            ]
            reset_r = Signal(2, init=0b11)
            m.d.rdn += reset_r.eq(Cat(C(0, 1), reset_r[0]))
            rrst = reset_r[1]

            m.domains += ClockDomain("wrn", clk_edge="neg", async_reset=True,
                                     local=True)
            m.d.comb += [
                ClockSignal("wrn").eq(self.WrClk),
                ResetSignal("wrn").eq(self.Reset),
            ]
            reset_w = Signal(2, init=0b11)
            m.d.wrn += reset_w.eq(Cat(C(0, 1), reset_w[0]))
            wrst = reset_w[1]
        elif self.en_reset:
            rrst = self.RdReset
            wrst = self.WrReset
        else:
            rrst = C(0)
            wrst = C(0)

        # "wr"/"rd": posedge domains with asynchronous reset WRst/RRst.
        m.domains += ClockDomain("wr", async_reset=True, local=True)
        m.domains += ClockDomain("rd", async_reset=True, local=True)
        m.d.comb += [
            ClockSignal("wr").eq(self.WrClk),
            ResetSignal("wr").eq(wrst),
            ClockSignal("rd").eq(self.RdClk),
            ResetSignal("rd").eq(rrst),
        ]

        # ------------------------------------------------------------------
        # Common read/write bookkeeping signals
        # ------------------------------------------------------------------
        rbin_num = Signal(rasize + 1)        # read pointer (binary)
        rbin_num_next = Signal(rasize + 1)
        rcnt_sub = Signal(rasize + 1)        # read data count
        raddr_num = Signal(rasize)           # read address
        waddr = Signal(asize)                # write address
        rempty_val = Signal()
        wfull_val = Signal()
        wcnt_sub = Signal(asize + 1)         # write data count

        m.d.rd += rbin_num.eq(rbin_num_next)
        m.d.comb += rbin_num_next.eq(rbin_num + (self.RdEn & ~self.Empty))

        # ------------------------------------------------------------------
        # Memory (+ optional ECC datapath, WDEPTH == RDEPTH only)
        # ------------------------------------------------------------------
        pwidth = edc_pwidth(wdsize) if self.en_ecc else 0
        mem_width = wdsize + pwidth
        mem = Memory(shape=unsigned(mem_width), depth=wdepth, init=[])
        m.submodules.mem = mem
        wport = mem.write_port(domain="wr")
        m.d.comb += [
            wport.addr.eq(waddr),
            wport.en.eq(self.WrEn & ~self.Full),
        ]

        if self.en_ecc:
            edc = Edc(dsize=wdsize,
                      en_reset=self.en_reset,
                      reset_synchronization=self.reset_synchronization,
                      enable_force_error=self.enable_force_error)
            m.submodules.u_edc = edc
            ecc_wdata = Signal(mem_width, name="data")    # {P_out, Data_p}
            ecc_qreg = Signal(mem_width, name="Qreg")
            m.d.comb += [
                edc.WrClk.eq(self.WrClk),
                edc.RdClk.eq(self.RdClk),
                edc.Ein.eq(self.Data),
                ecc_wdata.eq(Cat(edc.Eout, edc.P_out)),
                edc.Din.eq(ecc_qreg[:wdsize]),
                edc.P_in.eq(ecc_qreg[wdsize:]),
                self.Q.eq(edc.Dout),
                self.ERROR.eq(edc.error),
            ]
            if self.en_reset:
                if self.reset_synchronization:
                    m.d.comb += edc.RST.eq(self.Reset)
                else:
                    m.d.comb += [edc.Reset.eq(wrst), edc.RPReset.eq(rrst)]
            if self.enable_force_error:
                m.d.comb += edc.force_error.eq(0b00)
            m.d.comb += wport.data.eq(ecc_wdata)
        else:
            m.d.comb += wport.data.eq(self.Data)

        # Condition under which the read-side data register is loaded.
        if fwft:
            rd_load = Mux(self.RdEn, ~rempty_val, self.Empty & ~rempty_val)
        else:
            rd_load = self.RdEn & ~self.Empty

        # ==================================================================
        if wdepth < rdepth:
            # ---------------- Small: WDEPTH < RDEPTH ----------------
            a = rdepth // wdepth
            la = _log2_int(a, "RDEPTH/WDEPTH")

            wdata = Signal(wdsize)                 # registered memory word
            wptr = Signal(asize + 1)
            rptr = Signal(asize + 1)
            wq2_rptr = Signal(asize + 1)
            rq2_wptr = Signal(asize + 1)
            wq1_rptr = Signal(asize + 1)
            rq1_wptr = Signal(asize + 1)
            wbin = Signal(asize + 1)
            wcount_r_1 = Signal(rasize + 1)
            rgraynext = Signal(asize + 1)
            rbinnext = Signal(asize + 1)
            rbinnext_1 = Signal(asize + 1)
            wgraynext = Signal(asize + 1)
            wcount_r = Signal(asize + 1)
            rcount_w = Signal(asize + 1)
            wbinnext = Signal(asize + 1)
            wdata_q = Signal(rdsize)

            rport = mem.read_port(domain="comb")
            m.d.comb += rport.addr.eq(raddr_num[la:])       # raddr_num / a
            with m.If(rd_load):
                m.d.rd += wdata.eq(rport.data)

            # Slice selection within the wide memory word.
            if fwft:
                sel = Signal(la, name="rd_word_sel")
                m.d.comb += sel.eq(Mux(self.RdEn,
                                       (raddr_num - 1)[:la],
                                       raddr_num[:la]))
            else:
                sel = Signal(la, name="rd_word_sel")
                m.d.comb += sel.eq((raddr_num - 1)[:la])
            m.d.comb += wdata_q.eq(wdata.word_select(sel, rdsize))

            if self.en_output_reg:
                wdata_q_r = Signal(rdsize)
                if self.ctrl_by_rden:
                    cond = self.RdEn if fwft else (self.RdEn & ~self.Empty)
                    with m.If(cond):
                        m.d.rd += wdata_q_r.eq(wdata_q)
                else:
                    m.d.rd += wdata_q_r.eq(wdata_q)
                m.d.comb += self.Q.eq(wdata_q_r)
            else:
                m.d.comb += self.Q.eq(wdata_q)

            if fwft:
                m.d.comb += raddr_num.eq(rbin_num_next[:rasize])
            else:
                m.d.comb += raddr_num.eq(rbin_num[:rasize])
            m.d.comb += [
                rbinnext.eq(rbin_num_next[la:]),            # / a
                rbinnext_1.eq(rbin_num[la:]),               # / a
                rgraynext.eq((rbinnext >> 1) ^ rbinnext),
                rempty_val.eq(rgraynext == rq2_wptr),
            ]
            gb_w = self._gray2bin(m, rq2_wptr, "wcount_r")
            m.d.comb += [
                wcount_r.eq(gb_w),
                wcount_r_1.eq(wcount_r << la),              # * a
                rcnt_sub.eq(Cat(wcount_r_1[:rasize],
                                wcount_r[asize] ^ rbinnext_1[asize])
                            - rbin_num[:rasize]),
                waddr.eq(wbin[:asize]),
                wbinnext.eq(wbin + (self.WrEn & ~self.Full)),
                wgraynext.eq((wbinnext >> 1) ^ wbinnext),
                wfull_val.eq(self._full_compare(wgraynext, wq2_rptr, asize)),
            ]
            gb_r = self._gray2bin(m, wq2_rptr, "rcount_w")
            m.d.comb += [
                rcount_w.eq(gb_r),
                wcnt_sub.eq(Cat(wbin[:asize], rcount_w[asize] ^ wbin[asize])
                            - rcount_w[:asize]),
            ]

            # Pointer synchronization and pointer registers.
            m.d.wr += [wq1_rptr.eq(rptr), wq2_rptr.eq(wq1_rptr)]
            m.d.rd += [rq1_wptr.eq(wptr), rq2_wptr.eq(rq1_wptr)]
            m.d.rd += rptr.eq(rgraynext)
            m.d.wr += [wbin.eq(wbinnext), wptr.eq(wgraynext)]

        # ==================================================================
        elif wdepth > rdepth:
            # ---------------- Big: WDEPTH > RDEPTH ----------------
            b = wdepth // rdepth
            lb = _log2_int(b, "WDEPTH/RDEPTH")

            wptr = Signal(rasize + 1)
            rptr = Signal(rasize + 1)
            wq2_rptr = Signal(rasize + 1)
            rq2_wptr = Signal(rasize + 1)
            wq1_rptr = Signal(rasize + 1)
            rq1_wptr = Signal(rasize + 1)
            wbin = Signal(asize + 1)
            rgraynext = Signal(rasize + 1)
            wgraynext = Signal(rasize + 1)
            wcount_r = Signal(rasize + 1)
            rcount_w = Signal(rasize + 1)
            rcount_w_1 = Signal(asize + 1)
            wbin_num_next = Signal(asize + 1)
            wbinnext = Signal(rasize + 1)
            wbinnext_1 = Signal(rasize + 1)
            wdata_q = Signal(rdsize)

            # b memory words are read side by side to form one read word.
            rports = []
            for j in range(b):
                rp = mem.read_port(domain="comb")
                m.d.comb += rp.addr.eq(Cat(C(j, lb), raddr_num))  # raddr*b+j
                rports.append(rp)
            rdata_cat = Cat(*[rp.data for rp in rports])

            if self.en_output_reg:
                wdata_q_r = Signal(rdsize)
                if self.ctrl_by_rden:
                    if fwft:
                        with m.If(rd_load):
                            m.d.rd += wdata_q_r.eq(rdata_cat)
                        with m.If(self.RdEn):
                            m.d.rd += wdata_q.eq(wdata_q_r)
                    else:
                        with m.If(rd_load):
                            m.d.rd += [wdata_q_r.eq(rdata_cat),
                                       wdata_q.eq(wdata_q_r)]
                else:
                    with m.If(rd_load):
                        m.d.rd += wdata_q_r.eq(rdata_cat)
                    m.d.rd += wdata_q.eq(wdata_q_r)
            else:
                with m.If(rd_load):
                    m.d.rd += wdata_q.eq(rdata_cat)

            m.d.comb += self.Q.eq(wdata_q)

            if fwft:
                m.d.comb += raddr_num.eq(rbin_num_next[:rasize])
            else:
                m.d.comb += raddr_num.eq(rbin_num[:rasize])
            m.d.comb += [
                rgraynext.eq((rbin_num_next >> 1) ^ rbin_num_next),
                rempty_val.eq(rgraynext == rq2_wptr),
            ]
            gb_w = self._gray2bin(m, rq2_wptr, "wcount_r")
            m.d.comb += [
                wcount_r.eq(gb_w),
                rcnt_sub.eq(Cat(wcount_r[:rasize],
                                wcount_r[rasize] ^ rbin_num[rasize])
                            - rbin_num[:rasize]),
                waddr.eq(wbin[:asize]),
                wbin_num_next.eq(wbin + (self.WrEn & ~self.Full)),
                wbinnext.eq(wbin_num_next[lb:]),            # / b
                wbinnext_1.eq(wbin[lb:]),                   # / b
                wgraynext.eq((wbinnext >> 1) ^ wbinnext),
                wfull_val.eq(self._full_compare(wgraynext, wq2_rptr, rasize)),
            ]
            gb_r = self._gray2bin(m, wq2_rptr, "rcount_w")
            m.d.comb += [
                rcount_w.eq(gb_r),
                rcount_w_1.eq(rcount_w << lb),              # * b
                wcnt_sub.eq(Cat(wbin[:asize],
                                rcount_w[rasize] ^ wbinnext_1[rasize])
                            - rcount_w_1[:asize]),
            ]

            m.d.wr += [wq1_rptr.eq(rptr), wq2_rptr.eq(wq1_rptr)]
            m.d.rd += [rq1_wptr.eq(wptr), rq2_wptr.eq(rq1_wptr)]
            m.d.rd += rptr.eq(rgraynext)
            m.d.wr += [wbin.eq(wbin_num_next), wptr.eq(wgraynext)]

        # ==================================================================
        else:
            # ---------------- Equal: WDEPTH == RDEPTH ----------------
            wptr = Signal(asize + 1)
            rptr = Signal(asize + 1)
            wq2_rptr = Signal(asize + 1)
            rq2_wptr = Signal(asize + 1)
            wq1_rptr = Signal(asize + 1)
            rq1_wptr = Signal(asize + 1)
            wbin = Signal(asize + 1)
            rgraynext = Signal(asize + 1)
            wgraynext = Signal(asize + 1)
            wcount_r = Signal(asize + 1)
            rcount_w = Signal(asize + 1)
            wbinnext = Signal(asize + 1)
            wdata_q = Signal(mem_width)

            rport = mem.read_port(domain="comb")
            m.d.comb += rport.addr.eq(raddr_num)

            if self.en_output_reg:
                wdata_q_r = Signal(mem_width)
                if self.ctrl_by_rden:
                    if fwft:
                        with m.If(rd_load):
                            m.d.rd += wdata_q_r.eq(rport.data)
                        with m.If(self.RdEn):
                            m.d.rd += wdata_q.eq(wdata_q_r)
                    else:
                        with m.If(rd_load):
                            m.d.rd += [wdata_q_r.eq(rport.data),
                                       wdata_q.eq(wdata_q_r)]
                else:
                    with m.If(rd_load):
                        m.d.rd += wdata_q_r.eq(rport.data)
                    m.d.rd += wdata_q.eq(wdata_q_r)
            else:
                with m.If(rd_load):
                    m.d.rd += wdata_q.eq(rport.data)

            if self.en_ecc:
                m.d.comb += ecc_qreg.eq(wdata_q)   # Q is driven by the EDC
            else:
                m.d.comb += self.Q.eq(wdata_q)

            if fwft:
                m.d.comb += raddr_num.eq(rbin_num_next[:asize])
            else:
                m.d.comb += raddr_num.eq(rbin_num[:asize])
            m.d.comb += [
                rgraynext.eq((rbin_num_next >> 1) ^ rbin_num_next),
                rempty_val.eq(rgraynext == rq2_wptr),
            ]
            gb_w = self._gray2bin(m, rq2_wptr, "wcount_r")
            m.d.comb += [
                wcount_r.eq(gb_w),
                rcnt_sub.eq(Cat(wcount_r[:asize],
                                wcount_r[asize] ^ rbin_num[rasize])
                            - rbin_num[:rasize]),
                waddr.eq(wbin[:asize]),
                wbinnext.eq(wbin + (self.WrEn & ~self.Full)),
                wgraynext.eq((wbinnext >> 1) ^ wbinnext),
                wfull_val.eq(self._full_compare(wgraynext, wq2_rptr, asize)),
            ]
            gb_r = self._gray2bin(m, wq2_rptr, "rcount_w")
            m.d.comb += [
                rcount_w.eq(gb_r),
                wcnt_sub.eq(Cat(wbin[:asize], rcount_w[asize] ^ wbin[asize])
                            - rcount_w[:asize]),
            ]

            m.d.wr += [wq1_rptr.eq(rptr), wq2_rptr.eq(wq1_rptr)]
            m.d.rd += [rq1_wptr.eq(wptr), rq2_wptr.eq(rq1_wptr)]
            m.d.rd += rptr.eq(rgraynext)
            m.d.wr += [wbin.eq(wbinnext), wptr.eq(wgraynext)]

        # ==================================================================
        # Status flags (common to all depth ratios)
        # ==================================================================
        m.d.rd += self.Empty.eq(rempty_val)     # resets to 1
        m.d.wr += self.Full.eq(wfull_val)       # resets to 0

        r1 = rasize + 1
        a1 = asize + 1

        if self.almost_empty_flag:
            arempty_val = Signal()
            if self.empty_th_mode == "static_dual":
                clr_th = self.deassert_empty_th
                clr_p1 = (self.deassert_empty_th + 1) % (1 << r1)
                set_th = self.assert_empty_th
                set_p1 = (self.assert_empty_th + 1) % (1 << r1)
            elif self.empty_th_mode == "static_single":
                clr_th = self.aempt
                clr_p1 = (self.aempt + 1) % (1 << r1)
            elif self.empty_th_mode == "dynamic_dual":
                clr_th = self.AlmostEmptyClrTh
                clr_p1 = Signal(r1, name="aempty_clr_p1")
                m.d.comb += clr_p1.eq(self.AlmostEmptyClrTh + 1)
                set_th = self.AlmostEmptySetTh
                set_p1 = Signal(r1, name="aempty_set_p1")
                m.d.comb += set_p1.eq(self.AlmostEmptySetTh + 1)
            else:  # dynamic_single
                clr_th = self.AlmostEmptyTh
                clr_p1 = Signal(r1, name="aempty_p1")
                m.d.comb += clr_p1.eq(self.AlmostEmptyTh + 1)

            m.d.comb += arempty_val.eq(
                (rcnt_sub <= clr_th)
                | ((rcnt_sub == clr_p1) & self.RdEn))

            if self.empty_th_mode in ("static_dual", "dynamic_dual"):
                with m.If(arempty_val
                          & ((rcnt_sub <= set_th)
                             | ((rcnt_sub == set_p1) & self.RdEn))):
                    m.d.rd += self.Almost_Empty.eq(1)
                with m.Elif(~arempty_val):
                    m.d.rd += self.Almost_Empty.eq(0)
            else:
                m.d.rd += self.Almost_Empty.eq(arempty_val)

        if self.almost_full_flag:
            awfull_val = Signal()
            if self.full_th_mode == "static_dual":
                da_th = self.deassert_full_th
                da_m1 = (self.deassert_full_th - 1) % (1 << a1)
                as_th = self.assert_full_th
                as_m1 = (self.assert_full_th - 1) % (1 << a1)
            elif self.full_th_mode == "static_single":
                da_th = self.afull
                da_m1 = (self.afull - 1) % (1 << a1)
            elif self.full_th_mode == "dynamic_dual":
                da_th = self.AlmostFullClrTh
                da_m1 = Signal(a1, name="afull_clr_m1")
                m.d.comb += da_m1.eq(self.AlmostFullClrTh - 1)
                as_th = self.AlmostFullSetTh
                as_m1 = Signal(a1, name="afull_set_m1")
                m.d.comb += as_m1.eq(self.AlmostFullSetTh - 1)
            else:  # dynamic_single
                da_th = self.AlmostFullTh
                da_m1 = Signal(a1, name="afull_m1")
                m.d.comb += da_m1.eq(self.AlmostFullTh - 1)

            m.d.comb += awfull_val.eq(
                (wcnt_sub >= da_th)
                | ((wcnt_sub == da_m1) & self.WrEn))

            if self.full_th_mode in ("static_dual", "dynamic_dual"):
                with m.If(awfull_val
                          & ((wcnt_sub >= as_th)
                             | ((wcnt_sub == as_m1) & self.WrEn))):
                    m.d.wr += self.Almost_Full.eq(1)
                with m.Elif(~awfull_val):
                    m.d.wr += self.Almost_Full.eq(0)
            else:
                m.d.wr += self.Almost_Full.eq(awfull_val)

        if self.count_w:
            m.d.wr += self.Wnum.eq(wcnt_sub)
        if self.count_r:
            m.d.rd += self.Rnum.eq(rcnt_sub)

        return m
