// SPDX-FileCopyrightText: © 2025 XXX Authors
// SPDX-License-Identifier: Apache-2.0

`default_nettype none

module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
    inout  wire VDD,
    inout  wire VSS,
    
    input  wire clk,       // clock
    input  wire rst_n,     // reset (active low)
    
    input  wire [NUM_INPUT_PADS-1:0] input_in,   // Input value
    output wire [NUM_INPUT_PADS-1:0] input_pu,   // Pull-up
    output wire [NUM_INPUT_PADS-1:0] input_pd,   // Pull-down

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,   // Input value
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,  // Output value
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,   // Output enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,   // Input type (0=CMOS Buffer, 1=Schmitt Trigger)
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,   // Slew rate (0=fast, 1=slow)
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,   // Input enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,   // Pull-up
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,   // Pull-down

    inout  wire [NUM_ANALOG_PADS-1:0] analog  // Analog
);

    // See here for usage: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html
    
    // Disable pull-up and pull-down for input
    assign input_pu = '0;
    assign input_pd = '0;

    // Set the bidir as output
    assign bidir_cs = '0;
    assign bidir_sl = '0;
    assign bidir_ie = '1;
    
    tinyQV_top tt(
        `ifdef USE_POWER_PINS_FOR_RAM
        .VDD  (VDD),
        .VSS  (VSS),
        `endif

        .gpio_in(bidir_in[39:8]),
        .gpio_out(bidir_out[39:8]),
        .gpio_oe(bidir_oe[39:8]),
        .gpio_pu(bidir_pu[39:8]),
        .gpio_pd(bidir_pd[39:8]),
        .qspi_in(bidir_in[7:0]),
        .qspi_out(bidir_out[7:0]),
        .qspi_oe(bidir_oe[7:0]),
        .qspi_pu(bidir_pu[7:0]),
        .qspi_pd(bidir_pd[7:0]),
        .uart_rx(input_in[0]),
        .uart_tx(bidir_out[40]),
        .uart_rts(bidir_out[41]),
        .clk(clk),
        .rst_n(rst_n)
    );

    // TODO
    assign bidir_out[42] = 1'b0;
    assign bidir_out[43] = 1'b0;
    assign bidir_oe[43:40] = '1;
    assign bidir_pu[43:40] = '0;
    assign bidir_pd[43:40] = '0;

endmodule

`default_nettype wire
