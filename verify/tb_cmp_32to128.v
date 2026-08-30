// Cycle-exact comparison: Gowin netlist fifo_top_32to128 vs Amaranth RTL.
`timescale 100ps/100ps

module tb;
  reg WrClk = 0, RdClk = 0, Reset = 0, WrEn = 0, RdEn = 0;
  reg [35:0] Data = 0;

  wire e_n, f_n, ae_n, af_n;  wire [143:0] q_n;  wire [8:0] w_n;
  fifo_top_32to128 dut_net (
    .Data(Data), .Reset(Reset), .WrClk(WrClk), .RdClk(RdClk),
    .WrEn(WrEn), .RdEn(RdEn), .Wnum(w_n),
    .Almost_Empty(ae_n), .Almost_Full(af_n), .Q(q_n),
    .Empty(e_n), .Full(f_n));

  wire e_r, f_r, ae_r, af_r;  wire [143:0] q_r;  wire [8:0] w_r;
  fifo_top_32to128_rtl dut_rtl (
    .Data(Data), .Reset(Reset), .WrClk(WrClk), .RdClk(RdClk),
    .WrEn(WrEn), .RdEn(RdEn), .Wnum(w_r),
    .Almost_Empty(ae_r), .Almost_Full(af_r), .Q(q_r),
    .Empty(e_r), .Full(f_r));

  always #50 WrClk = ~WrClk;   // 10 ns
  always #71 RdClk = ~RdClk;   // 14.2 ns

  integer errors = 0;
  task check;
    begin
      if (e_n !== e_r)   begin errors = errors + 1; $display("t=%0t Empty %b/%b", $time, e_n, e_r); end
      if (f_n !== f_r)   begin errors = errors + 1; $display("t=%0t Full %b/%b", $time, f_n, f_r); end
      if (ae_n !== ae_r) begin errors = errors + 1; $display("t=%0t AEmpty %b/%b", $time, ae_n, ae_r); end
      if (af_n !== af_r) begin errors = errors + 1; $display("t=%0t AFull %b/%b", $time, af_n, af_r); end
      if (w_n !== w_r)   begin errors = errors + 1; $display("t=%0t Wnum %0d/%0d", $time, w_n, w_r); end
      if (q_n !== q_r)   begin errors = errors + 1; $display("t=%0t Q %h/%h", $time, q_n, q_r); end
      if (errors > 20) begin $display("RESULT: MISMATCH (too many)"); $finish; end
    end
  endtask
  always @(negedge WrClk) if ($time > 400) check;
  always @(negedge RdClk) if ($time > 400) check;

  integer i, seed;
  initial begin
    seed = 7;
    Reset = 1; #300; Reset = 0;
    for (i = 0; i < 4000; i = i + 1) begin
      @(negedge WrClk);
      WrEn = ($random(seed) % 4) != 0;
      Data = {$random(seed), $random(seed)};
    end
    WrEn = 0;
    #6000;
    $display("RESULT: %0d errors", errors);
    $finish;
  end
  initial begin : reader
    integer j;
    #400;
    for (j = 0; j < 4000; j = j + 1) begin
      @(negedge RdClk);
      RdEn = ($random(seed) % 3) != 0;
    end
    RdEn = 1;
  end
endmodule
