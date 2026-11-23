/*
 * Copyright (c) 2024 Michael Bell
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tinyQV_top #(
    parameter CLOCK_KHZ=48000,
    parameter NUM_GPIO=32
) (
    `ifdef USE_POWER_PINS_FOR_RAM
    inout  wire VDD,
    inout  wire VSS,
    `endif
    
    input  wire [NUM_GPIO-1:0] gpio_in,
    output wire [NUM_GPIO-1:0] gpio_out,
    output wire [NUM_GPIO-1:0] gpio_oe,
    output wire [NUM_GPIO-1:0] gpio_pu,
    output wire [NUM_GPIO-1:0] gpio_pd,
    input  wire [7:0] qspi_in,
    output wire [7:0] qspi_out,
    output wire [7:0] qspi_oe,
    output wire [7:0] qspi_pu,
    output wire [7:0] qspi_pd,
    input  wire       uart_rx,
    output wire       uart_tx,
    output wire       uart_rts,
    output wire       debug_uart_txd,
    input  wire       clk,
    input  wire       rst_n
);

    // Address to peripheral map
    localparam PERI_NONE = 4'h0;
    localparam PERI_ID = 4'h2;
    localparam PERI_DEBUG_UART = 4'h6;
    localparam PERI_DEBUG_UART_STATUS = 4'h7;    
    localparam PERI_TIME_LIMIT = 4'hB;
    localparam PERI_BIO_SEL = 4'hD;
    localparam PERI_BIO = 4'hE;
    localparam PERI_USER = 4'hF;

    // Bidirs are used for SPI interface
    wire [3:0] qspi_data_in = {qspi_in[5:4], qspi_in[2:1]};
    wire [3:0] qspi_data_out;
    wire [3:0] qspi_data_oe;
    wire       qspi_clk_out;
    wire       qspi_flash_select;
    wire       qspi_ram_a_select;
    wire       qspi_ram_b_select;
    assign qspi_out = {qspi_ram_b_select, qspi_ram_a_select, qspi_data_out[3:2], 
                       qspi_clk_out, qspi_data_out[1:0], qspi_flash_select};
    assign qspi_oe = rst_n ? {2'b11, qspi_data_oe[3:2], 1'b1, qspi_data_oe[1:0], 1'b1} : 8'h00;
    assign qspi_pu = 8'b11000011;
    assign qspi_pd = 8'b00110100;

    wire [3:0] qspi_data_in_ctrl;
    reg  [3:0] qspi_config;
    wire [3:0] qspi_data_out_ctrl;
    wire [3:0] qspi_data_oe_ctrl;
    wire       qspi_clk_out_ctrl;
    wire       qspi_flash_select_ctrl;
    wire       qspi_ram_a_select_ctrl;
    wire       qspi_ram_b_select_ctrl;
    wire [3:0] qspi_data_out_setup;
    wire [3:0] qspi_data_oe_setup;
    wire       qspi_clk_out_setup;
    wire       qspi_flash_select_setup;
    wire       qspi_ram_a_select_setup;
    wire       qspi_ram_b_select_setup;
    wire       setup_done;
    reg        setup_rst_n;

    wire [27:0] addr;
    wire  [1:0] write_n;
    wire  [1:0] read_n;
    wire        read_complete;
    wire [31:0] data_to_write;

    wire        data_ready;
    reg [31:0] data_from_read;

    reg [3:0] connect_peripheral;

    // Debug UART - runs fast to reduce the width of the count necessary for the divider!
    wire debug_uart_tx_busy;
    wire debug_uart_tx_start = write_n != 2'b11 && connect_peripheral == PERI_DEBUG_UART;    

    // Time
    reg [6:2] time_limit;
    wire time_pulse;

    // Peripherals interface
    wire [31:0] peri_data_out;
    wire        peri_data_ready;
    wire [7:2] peri_interrupts;
    wire [NUM_GPIO-1:0] peri_gpio_out;
    wire [NUM_GPIO-1:0] peri_gpio_oe;

    // BIO peripheral interface
    wire [31:0] bio_data_out;
    wire        bio_data_ready;
    wire [NUM_GPIO-1:0] bio_gpio_out;
    wire [NUM_GPIO-1:0] bio_gpio_oe;
    reg  [NUM_GPIO-1:0] bio_sel;
    reg bio_penable;

    // Peripherals get synchronized ui_in.
    reg [NUM_GPIO-1:0] gpio_in_sync0;
    reg [NUM_GPIO-1:0] gpio_in_sync;
    reg       uart_rx_sync0;
    reg       uart_rx_sync;
    always @(posedge clk) begin
        gpio_in_sync0 <= gpio_in;
        uart_rx_sync0 <= uart_rx;
        gpio_in_sync <= gpio_in_sync0;
        uart_rx_sync <= uart_rx_sync0;
    end

    // Interrupt requests
    wire [7:0] interrupt_req = {peri_interrupts, gpio_in_sync[1:0]};
    // Register the reset on the negative edge of clock for safety.
    // This also allows the option of async reset in the design, which might be preferable in some cases
    always @(negedge clk) setup_rst_n <= rst_n;

    /* verilator lint_off SYNCASYNCNET */
`ifdef SIM
    reg rst_reg_n;
    always @(negedge clk) rst_reg_n <= rst_n & setup_done;
`elsif SYNTH_FPGA
    reg rst_reg_n;
    always @(negedge clk) rst_reg_n <= rst_n & setup_done;
`else
    wire rst_reg_n;
    (* keep *)
    gf180mcu_as_sc_mcu7t3v3__dfxtn_2 i_rst_reg_n (
        .CLK(clk),
        .D(rst_n & setup_done),
        .Q(rst_reg_n)
    );
`endif
    /* verilator lint_on SYNCASYNCNET */

    always @(posedge clk) begin
        if (!setup_rst_n) begin
            qspi_config <= qspi_data_in;
        end
    end

    assign qspi_data_in_ctrl = rst_reg_n ? qspi_data_in : qspi_config;
    assign qspi_data_out     = rst_reg_n ? qspi_data_out_ctrl : qspi_data_out_setup;
    assign qspi_data_oe      = rst_reg_n ? qspi_data_oe_ctrl  : qspi_data_oe_setup;
    assign qspi_clk_out      = rst_reg_n ? qspi_clk_out_ctrl  : qspi_clk_out_setup;
    assign qspi_flash_select = rst_reg_n ? qspi_flash_select_ctrl : qspi_flash_select_setup;
    assign qspi_ram_a_select = rst_reg_n ? qspi_ram_a_select_ctrl : qspi_ram_a_select_setup;
    assign qspi_ram_b_select = rst_reg_n ? qspi_ram_b_select_ctrl : qspi_ram_b_select_setup;

    genvar i;
    generate
    for (i = 0; i < NUM_GPIO; i = i + 1) begin
        assign gpio_out[i] = bio_sel[i] ? bio_gpio_out[i] : peri_gpio_out[i];
        assign gpio_oe[i]  = bio_sel[i] ? bio_gpio_oe[i]  : peri_gpio_oe[i];
    end
    endgenerate

    qspi_setup i_setup(
        .clk(clk),
        .rstn(setup_rst_n),

        .spi_data_out(qspi_data_out_setup),
        .spi_data_oe(qspi_data_oe_setup),
        .spi_clk_out(qspi_clk_out_setup),
        .spi_flash_select(qspi_flash_select_setup),
        .spi_ram_a_select(qspi_ram_a_select_setup),
        .spi_ram_b_select(qspi_ram_b_select_setup),

        .done(setup_done)
    );

    tinyQV i_tinyqv(
        .clk(clk),
        .rstn(rst_reg_n),

        .data_addr(addr),
        .data_write_n(write_n),
        .data_read_n(read_n),
        .data_read_complete(read_complete),
        .data_out(data_to_write),

        .data_ready(data_ready),
        .data_in(data_from_read),

        .interrupt_req(interrupt_req),
        .time_pulse(time_pulse),

        .spi_data_in(qspi_data_in_ctrl),
        .spi_data_out(qspi_data_out_ctrl),
        .spi_data_oe(qspi_data_oe_ctrl),
        .spi_clk_out(qspi_clk_out_ctrl),
        .spi_flash_select(qspi_flash_select_ctrl),
        .spi_ram_a_select(qspi_ram_a_select_ctrl),
        .spi_ram_b_select(qspi_ram_b_select_ctrl)
    );

    tinyQV_peripherals #(.CLOCK_KHZ(CLOCK_KHZ), .NUM_GPIO(NUM_GPIO)) i_peripherals (
        .clk(clk),
        .rst_n(rst_reg_n),

        .gpio_in(gpio_in_sync),
        .gpio_in_raw(gpio_in),
        .gpio_out(peri_gpio_out),
        .gpio_oe(peri_gpio_oe),
        .gpio_pu(gpio_pu),
        .gpio_pd(gpio_pd),

        .uart_rx(uart_rx_sync),
        .uart_tx(uart_tx),
        .uart_rts(uart_rts),

        .addr_in(addr[10:0]),
        .data_in(data_to_write),

        .data_write_n(write_n | {2{connect_peripheral != PERI_USER}}),
        .data_read_n(read_n),

        .data_out(peri_data_out),
        .data_ready(peri_data_ready),

        .data_read_complete(read_complete),

        .user_interrupts(peri_interrupts)
    );

    femto_bio #(.NUM_CORES(`NUM_BIO_CORES)) i_bio (
        `ifdef USE_POWER_PINS_FOR_RAM
        .VDD  (VDD),
        .VSS  (VSS),
        `endif

        .clk(clk),
        .rst_n(rst_reg_n),

        .gpio_out(bio_gpio_out),
        .gpio_oe(bio_gpio_oe),
        .gpio_in(gpio_in_sync),
        
        .paddr(addr[15:0]),
        .psel(connect_peripheral == PERI_BIO),
        .penable(bio_penable),
        .pwrite(bio_penable && write_n == 2'b10),  // Only 32-bit transactions supported
        .pwdata(data_to_write),
        .prdata(bio_data_out),
        .pready(bio_data_ready)
    );

    always @(*) begin
        if ({addr[27:6], addr[1:0]} == 24'h800000) 
            connect_peripheral = addr[5:2];
        else if (addr[27:11] == 17'h10000)
            connect_peripheral = PERI_USER;
        else if (addr[27:16] == 12'h900)
            connect_peripheral = PERI_BIO;
        else
            connect_peripheral = PERI_NONE;
    end

    // Read data
    always @(*) begin
        case (connect_peripheral)
            PERI_ID:          data_from_read = "WS_3";
            PERI_DEBUG_UART_STATUS: data_from_read = {31'h0, debug_uart_tx_busy};
            PERI_TIME_LIMIT:  data_from_read = {25'h0, time_limit, 2'b11};
            PERI_BIO_SEL:     data_from_read = bio_sel;
            PERI_BIO:         data_from_read = bio_data_out;
            PERI_USER:        data_from_read = peri_data_out;
            default:          data_from_read = 32'hFFFF_FFFF;
        endcase
    end

    assign data_ready = (connect_peripheral == PERI_USER) ? peri_data_ready : 
                        (connect_peripheral == PERI_BIO) ? bio_data_ready : 1'b1;

    uart_tx #(.CLK_HZ(CLOCK_KHZ * 1_000), .BIT_RATE(1_000_000)) i_debug_uart_tx(
        .clk(clk),
        .resetn(rst_reg_n),
        .uart_txd(debug_uart_txd),
        .uart_tx_en(debug_uart_tx_start),
        .uart_tx_data(data_to_write[7:0]),
        .uart_tx_busy(debug_uart_tx_busy) 
    );

    always @(posedge clk) begin
        if (!rst_reg_n) begin
            time_limit <= (CLOCK_KHZ / 4000 - 1);
        end else if (write_n != 2'b11) begin
            if (connect_peripheral == PERI_TIME_LIMIT) time_limit <= data_to_write[6:2];
        end
    end

    reg [6:0] time_count;

    always @(posedge clk) begin
        if (!rst_reg_n) begin
            time_count <= 0;
        end else begin
            if (time_pulse) time_count <= 0;
            else time_count <= time_count + 1;
        end
    end
    assign time_pulse = time_count == {time_limit, 2'b11};

    always @(posedge clk) begin
        if (!rst_reg_n) begin
            bio_sel <= 0;
        end else if (write_n != 2'b11) begin
            if (connect_peripheral == PERI_BIO_SEL) bio_sel <= data_to_write[NUM_GPIO-1:0];
        end
    end

    always @(posedge clk) begin
        if (!rst_reg_n) begin
            bio_penable <= 0;
        end else begin
            bio_penable <= (connect_peripheral == PERI_BIO && (write_n == 2'b10 || read_n == 2'b10)) && !bio_data_ready;
        end
    end

    // List all unused inputs to prevent warnings
    wire _unused = &{qspi_in[6], qspi_in[3], qspi_in[0], read_complete, 1'b0};

endmodule
