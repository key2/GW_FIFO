// Cycle-exact comparison: Gowin netlist fifo_top_128to32 vs Amaranth RTL.
`timescale 100ps/100ps

module tb;
  reg WrClk = 0, RdClk = 0, Reset = 0, WrEn = 0, RdEn = 0;
  reg [127:0] Data = 0;

  wire e_n, f_n, af_n;  wire [31:0] q_n;
  fifo_top_128to32 dut_net (
    .Data(Data), .Reset(Reset), .WrClk(WrClk), .RdClk(RdClk),
    .WrEn(WrEn), .RdEn(RdEn),
    .Almost_Full(af_n), .Q(q_n), .Empty(e_n), .Full(f_n));

  wire e_r, f_r, af_r;  wire [31:0] q_r;
  fifo_top_128to32_rtl dut_rtl (
    .Data(Data), .Reset(Reset), .WrClk(WrClk), .RdClk(RdClk),
    .WrEn(WrEn), .RdEn(RdEn),
    .Almost_Full(af_r), .Q(q_r), .Empty(e_r), .Full(f_r));

  always #50 WrClk = ~WrClk;   // 10 ns
  always #71 RdClk = ~RdClk;   // 14.2 ns (asynchronous)

  integer errors = 0;
  task check;
    begin
      if (e_n !== e_r)   begin errors = errors + 1; $display("t=%0t Empty %b/%b", $time, e_n, e_r); end
      if (f_n !== f_r)   begin errors = errors + 1; $display("t=%0t Full %b/%b", $time, f_n, f_r); end
      if (af_n !== af_r) begin errors = errors + 1; $display("t=%0t AFull %b/%b", $time, af_n, af_r); end
      if (q_n !== q_r)   begin errors = errors + 1; $display("t=%0t Q %h/%h", $time, q_n, q_r); end
      if (errors > 20) begin $display("RESULT: MISMATCH (too many)"); $finish; end
    end
  endtask
  always @(negedge WrClk) if ($time > 400) check;
  always @(negedge RdClk) if ($time > 400) check;

  integer i, seed;
  initial begin
    seed = 42;
    Reset = 1; #300; Reset = 0;
    // random phase
    for (i = 0; i < 3000; i = i + 1) begin
      @(negedge WrClk);
      WrEn = ($random(seed) % 4) != 0;
      Data = {$random(seed), $random(seed), $random(seed), $random(seed)};
    end
    WrEn = 0;
    #5000;
    $display("RESULT: %0d errors", errors);
    $finish;
  end
  initial begin : reader
    integer j;
    #400;
    for (j = 0; j < 3000; j = j + 1) begin
      @(negedge RdClk);
      RdEn = ($random(seed) % 3) != 0;
    end
    RdEn = 1; // drain
  end
  // fill-to-full phase interleaved via long random run above; also do a
  // deterministic fill and drain at the end:
  initial begin : phases
    #350000;
    WrEn = 0; RdEn = 1; #30000;   // drain all
    RdEn = 0;
    repeat (80) begin @(negedge WrClk); WrEn = 1; Data = {4{$random(seed)}}; end
    WrEn = 0; #3000;              // now Full
    repeat (300) @(negedge RdClk); // hold
  end
endmodule
