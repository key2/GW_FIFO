// Comparison with stimulus that hovers around the Almost_Full threshold.
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

  always #50 WrClk = ~WrClk;
  always #71 RdClk = ~RdClk;

  integer errors = 0;
  task check;
    begin
      if ({e_n,f_n,ae_n,af_n,w_n,q_n} !== {e_r,f_r,ae_r,af_r,w_r,q_r}) begin
        errors = errors + 1;
        $display("t=%0t E%b%b F%b%b AE%b%b AF%b%b W%0d/%0d", $time,
                 e_n,e_r, f_n,f_r, ae_n,ae_r, af_n,af_r, w_n, w_r);
      end
      if (errors > 10) begin $display("RESULT: MISMATCH (too many)"); $finish; end
    end
  endtask
  always @(negedge WrClk) if ($time > 400) check;
  always @(negedge RdClk) if ($time > 400) check;

  integer i, seed;
  initial begin
    seed = 99;
    Reset = 1; #300; Reset = 0;
    // Phase 1: fill to Full (crosses AF upward exactly once)
    @(negedge WrClk); WrEn = 1;
    for (i = 0; i < 280; i = i + 1) begin
      Data = {$random(seed), $random(seed)};
      @(negedge WrClk);
    end
    // Phase 2: hover near full: keep writing, read sporadically
    for (i = 0; i < 2500; i = i + 1) begin
      @(negedge WrClk);
      WrEn = ($random(seed) % 2) != 0;
      Data = {$random(seed), $random(seed)};
    end
    WrEn = 0;
    #8000;
    $display("RESULT: %0d errors", errors);
    $finish;
  end
  initial begin : reader
    integer j;
    #35000;   // stay full for a while first
    for (j = 0; j < 2200; j = j + 1) begin
      @(negedge RdClk);
      RdEn = ($random(seed) % 8) == 0;  // slow reader -> hover near full
    end
    RdEn = 1;
  end
endmodule
