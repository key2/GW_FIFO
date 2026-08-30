// Minimal behavioral models of the Gowin primitives used by
// fifo_top_128to32.v / fifo_top_32to128.v (for iverilog simulation).
`timescale 100ps/100ps

module VCC (output V);
  assign V = 1'b1;
endmodule

module GND (output G);
  assign G = 1'b0;
endmodule

module GSR (input GSRI);
endmodule

module INV (output O, input I);
  assign O = ~I;
endmodule

module LUT2 (output F, input I0, I1);
  parameter INIT = 4'h0;
  assign F = INIT[{I1, I0}];
endmodule

module LUT3 (output F, input I0, I1, I2);
  parameter INIT = 8'h00;
  assign F = INIT[{I2, I1, I0}];
endmodule

module LUT4 (output F, input I0, I1, I2, I3);
  parameter INIT = 16'h0000;
  assign F = INIT[{I3, I2, I1, I0}];
endmodule

// Gowin carry-chain ALU (modes used here: 1 = SUB, 3 = NE)
module ALU (output SUM, COUT, input I0, I1, I3, CIN);
  parameter ALU_MODE = 0;
  reg S, C;
  assign SUM  = S ^ CIN;
  assign COUT = S ? CIN : C;
  always @(*) begin
    case (ALU_MODE)
      0: begin S = I0 ^ I1;              C = I0;   end // ADD
      1: begin S = I0 ^ ~I1;             C = I0;   end // SUB
      2: begin S = I3 ? (I0^I1):(I0^~I1);C = I0;   end // ADDSUB
      3: begin S = I0 ^ ~I1;             C = 1'b1; end // NE
      default: begin S = 1'b0; C = 1'b0; end
    endcase
  end
endmodule

module DFFCE (output reg Q, input D, CLK, CE, CLEAR);
  initial Q = 1'b0;
  always @(posedge CLK or posedge CLEAR)
    if (CLEAR) Q <= 1'b0;
    else if (CE) Q <= D;
endmodule

module DFFPE (output reg Q, input D, CLK, CE, PRESET);
  initial Q = 1'b1;
  always @(posedge CLK or posedge PRESET)
    if (PRESET) Q <= 1'b1;
    else if (CE) Q <= D;
endmodule

// 16Kb semi dual port BSRAM, as used: 32-bit write / 32-bit read, bypass
// read mode, async reset of the output register, byte enables on ADA[3:0].
module SDPB (
  output reg [31:0] DO,
  input CLKA, CEA, CLKB, CEB, OCE, RESET,
  input [13:0] ADA, ADB,
  input [31:0] DI,
  input [2:0] BLKSELA, BLKSELB
);
  parameter BIT_WIDTH_0 = 32;
  parameter BIT_WIDTH_1 = 32;
  parameter READ_MODE   = 1'b0;
  parameter RESET_MODE  = "SYNC";
  parameter BLK_SEL_0   = 3'b000;
  parameter BLK_SEL_1   = 3'b000;

  reg [31:0] mem [0:511];
  integer i;
  initial begin
    DO = 0;
    for (i = 0; i < 512; i = i + 1) mem[i] = 0;
  end

  always @(posedge CLKA)
    if (CEA && BLKSELA == BLK_SEL_0) begin
      if (ADA[0]) mem[ADA[13:5]][7:0]   <= DI[7:0];
      if (ADA[1]) mem[ADA[13:5]][15:8]  <= DI[15:8];
      if (ADA[2]) mem[ADA[13:5]][23:16] <= DI[23:16];
      if (ADA[3]) mem[ADA[13:5]][31:24] <= DI[31:24];
    end

  generate
    if (RESET_MODE == "ASYNC") begin : g_async
      always @(posedge CLKB or posedge RESET)
        if (RESET) DO <= 0;
        else if (CEB && BLKSELB == BLK_SEL_1) DO <= mem[ADB[13:5]];
    end else begin : g_sync
      always @(posedge CLKB)
        if (RESET) DO <= 0;
        else if (CEB && BLKSELB == BLK_SEL_1) DO <= mem[ADB[13:5]];
    end
  endgenerate
endmodule

// 18Kb x9 semi dual port BSRAM, as used: 9-bit write / 36-bit read.
module SDPX9B (
  output reg [35:0] DO,
  input CLKA, CEA, CLKB, CEB, OCE, RESET,
  input [13:0] ADA, ADB,
  input [35:0] DI,
  input [2:0] BLKSELA, BLKSELB
);
  parameter BIT_WIDTH_0 = 9;
  parameter BIT_WIDTH_1 = 36;
  parameter READ_MODE   = 1'b0;
  parameter RESET_MODE  = "SYNC";
  parameter BLK_SEL_0   = 3'b000;
  parameter BLK_SEL_1   = 3'b000;

  reg [8:0] mem [0:2047];
  integer i;
  initial begin
    DO = 0;
    for (i = 0; i < 2048; i = i + 1) mem[i] = 0;
  end

  always @(posedge CLKA)
    if (CEA && BLKSELA == BLK_SEL_0)
      mem[ADA[13:3]] <= DI[8:0];

  generate
    if (RESET_MODE == "ASYNC") begin : g_async
      always @(posedge CLKB or posedge RESET)
        if (RESET) DO <= 0;
        else if (CEB && BLKSELB == BLK_SEL_1)
          DO <= {mem[{ADB[13:5], 2'd3}], mem[{ADB[13:5], 2'd2}],
                 mem[{ADB[13:5], 2'd1}], mem[{ADB[13:5], 2'd0}]};
    end else begin : g_sync
      always @(posedge CLKB)
        if (RESET) DO <= 0;
        else if (CEB && BLKSELB == BLK_SEL_1)
          DO <= {mem[{ADB[13:5], 2'd3}], mem[{ADB[13:5], 2'd2}],
                 mem[{ADB[13:5], 2'd1}], mem[{ADB[13:5], 2'd0}]};
    end
  endgenerate
endmodule
