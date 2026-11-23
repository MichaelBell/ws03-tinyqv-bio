`default_nettype none

`include "slot_defines.svh"

module tb_top #(
    // Signal pads
    parameter NUM_INPUT_PADS = `NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS = `NUM_BIDIR_PADS
)(
    inout [3:0] qspi_data
);

    reg uart_rx;
    reg prog_n;
    reg prog_cs;
    reg prog_mosi;
    wire [3:0] input_PAD;
    assign input_PAD = {prog_cs, prog_mosi, prog_n, uart_rx};
    wire uart_tx;
    wire uart_rts;
    wire debug_uart_tx;

    wire prog_miso;

    reg [31:0] gpio_in;
    wire [7:0] uio;
    wire [31:0] gpio_out;

    wire [NUM_BIDIR_PADS-1:0] bidir_PAD;

    assign bidir_PAD[39:8] = gpio_in;
    assign uio[5:4] = qspi_data[3:2];
    assign uio[2:1] = qspi_data[1:0];
    assign bidir_PAD[7:0] = uio;
    assign gpio_out = bidir_PAD[39:8];
    assign uart_tx = bidir_PAD[40];
    assign uart_rts = bidir_PAD[41];
    assign debug_uart_tx = bidir_PAD[42];
    assign prog_miso = bidir_PAD[43];

    wire clk_PAD;
    wire rst_n_PAD;
    //wire prog_clk_PAD;

`ifdef USE_POWER_PINS
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

    chip_top uut (
`ifdef USE_POWER_PINS
        .VDD(VPWR),
        .VSS(VGND),
`endif

        .clk_PAD(clk_PAD),
        .rst_n_PAD(rst_n_PAD),
        //.prog_clk_PAD(prog_clk_PAD),
        
        .input_PAD(input_PAD),
        .bidir_PAD(bidir_PAD)
    );

endmodule

