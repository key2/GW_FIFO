// Comparison hovering around the Almost_Empty threshold (rcnt ~ 24 read
// words = ~96 write words occupancy).
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
        $display("t=%0t E%b%b F%b%b AE%b%b AF%b%b W%0d/%0d Qok=%b", $time,
                 e_n,e_r, f_n,f_r, ae_n,ae_r, af_n,af_r, w_n, w_r, q_n===q_r);
      end
      if (errors > 10) begin $display("RESULT: MISMATCH (too many)"); $finish; end
    end
  endtask
  always @(negedge WrClk) if ($time > 400) check;
  always @(negedge RdClk) if ($time > 400) check;

  integer i, seed;
  initial begin
    seed = 5;
    Reset = 1; #300; Reset = 0;
    // fill to ~100 write words
    @(negedge WrClk); WrEn = 1;
    for (i = 0; i < 100; i = i + 1) begin
      Data = {$random(seed), $random(seed)};
      @(negedge WrClk);
    end
    // balanced hovering: writer ~ 4x reader word rate
    for (i = 0; i < 6000; i = i + 1) begin
      @(negedge WrClk);
      WrEn = ($random(seed) % 16) < 6;   // ~37.5% of 10ns -> 0.0375 w/ns
      Data = {$random(seed), $random(seed)};
    end
    WrEn = 0;
    #8000;
    $display("RESULT: %0d errors", errors);
    $finish;
  end
  initial begin : reader
    integer j;
    #12000;
    forever begin
      @(negedge RdClk);
      RdEn = ($random(seed) % 16) < 2;   // ~12.5% of 14.2ns -> 0.035 w/ns
    end
  end
endmodule
