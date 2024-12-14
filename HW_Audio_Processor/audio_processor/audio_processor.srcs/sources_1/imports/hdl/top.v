`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: Digilent Inc
// Engineer: Arthur Brown
//
// Create Date: 03/23/2018 11:53:54 AM
// Design Name: Arty-A7-100-Pmod-I2S2
// Module Name: top
// Project Name:
// Target Devices: Arty A7 100
// Tool Versions: Vivado 2017.4
// Description: Implements a volume control stream from Line In to Line Out of a Pmod I2S2 on port JA
//
// Revision:
// Revision 0.01 - File Created
//
//////////////////////////////////////////////////////////////////////////////////


module top #(
	parameter NUMBER_OF_SWITCHES = 4,
	parameter RESET_POLARITY = 0
) (
    input wire       clk,
    input wire [NUMBER_OF_SWITCHES-1:0] sw,
    input wire       bypass,
    input wire       reset,

    output wire tx_mclk,
    output wire tx_lrck,
    output wire tx_sclk,
    output wire tx_data,
    output wire rx_mclk,
    output wire rx_lrck,
    output wire rx_sclk,
    input  wire rx_data,

    input wire  uart_rx,
    output wire uart_tx,

    output wire [15:0] LED//,

    //output wire probe_sys_clk,
    //output wire probe_baud
);
    wire axis_clk;
    wire clk_ok;

    wire [23:0] axis_tx_data;
    wire axis_tx_valid;
    wire axis_tx_ready;
    wire axis_tx_last;

    wire [23:0] axis_sm_data;
    wire axis_sm_valid;
    wire axis_sm_ready;
    wire axis_sm_last;

    wire [23:0] axis_rx_data;
    wire axis_rx_valid;
    wire axis_rx_ready;
    wire axis_rx_last;

	wire resetn = ((reset == RESET_POLARITY) ? 1'b0 : 1'b1) & clk_ok;

	wire volume_bypass = bypass;
	wire [32:0] axis_bypass_data;
	wire axis_bypass_valid;
	wire axis_bypass_last;
	wire axis_bypass_ready;

	assign axis_bypass_data = volume_bypass ? axis_rx_data : axis_tx_data;
	assign axis_bypass_valid = volume_bypass ? axis_rx_valid : axis_tx_valid;
	assign axis_bypass_last = volume_bypass ? axis_rx_last : axis_tx_last;

	assign axis_bypass_ready = volume_bypass ? axis_tx_ready : axis_rx_ready;

    clk_wiz_0 m_clk (
        .clk_in1(clk),
        .locked(clk_ok),
        .axis_clk(axis_clk)
    );

    //assign probe_sys_clk = axis_clk;

    axis_i2s2 m_i2s2 (
        .axis_clk(axis_clk),
        .axis_resetn(resetn),

        .tx_axis_s_data(axis_bypass_data),
        .tx_axis_s_valid(axis_bypass_valid),
        .tx_axis_s_ready(axis_tx_ready),
        .tx_axis_s_last(axis_bypass_last),

        .rx_axis_m_data(axis_rx_data),
        .rx_axis_m_valid(axis_rx_valid),
        .rx_axis_m_ready(axis_bypass_ready),
        .rx_axis_m_last(axis_rx_last),

        .tx_mclk(tx_mclk),
        .tx_lrck(tx_lrck),
        .tx_sclk(tx_sclk),
        .tx_sdout(tx_data),
        .rx_mclk(rx_mclk),
        .rx_lrck(rx_lrck),
        .rx_sclk(rx_sclk),
        .rx_sdin(rx_data)
    );

    axis_volume_controller #(
		.SWITCH_WIDTH(NUMBER_OF_SWITCHES),
		.DATA_WIDTH(24)
	) m_vc (
        .clk(axis_clk),
        .sw(sw),

        .s_axis_data(axis_rx_data),
        .s_axis_valid(axis_rx_valid),
        .s_axis_ready(axis_rx_ready),
        .s_axis_last(axis_rx_last),

        .m_axis_data(axis_sm_data),
        .m_axis_valid(axis_sm_valid),
        .m_axis_ready(axis_sm_ready),
        .m_axis_last(axis_sm_last)
    );

    wire [15:0] uart_rx_data;
    wire uart_rx_valid;
    wire uart_rx_ready;

    wire [15:0] uart_tx_data;
    wire uart_tx_valid;
    wire uart_tx_ready;

    axis_frame_buffer #(
		.DATA_WIDTH(24)
	) m_fb (
        .axis_clk(axis_clk),
        .axis_resetn(resetn),

        .s_axis_data(axis_sm_data),
        .s_axis_valid(axis_sm_valid),
        .s_axis_ready(axis_sm_ready),
        .s_axis_last(axis_sm_last),

        .m_axis_data(axis_tx_data),
        .m_axis_valid(axis_tx_valid),
        .m_axis_ready(axis_tx_ready),
        .m_axis_last(axis_tx_last),

        //AXIS UART-RX INTERFACE
        .s_rx_data(uart_rx_data),
        .s_rx_valid(uart_rx_valid),
        .s_rx_ready(uart_rx_ready),

        // AXIS UART-TX INTERFACE
        .m_tx_data(uart_tx_data),
        .m_tx_valid(uart_tx_valid),
        .m_tx_ready(uart_tx_ready),

        // Indicator
        .led(LED)
    );

    axis_uart_v1_0 uart_inst
    (
        .aclk(axis_clk),
        .aresetn(resetn),
        /* AXI-Stream Interface (Slave) */
        .s_axis_tdata(uart_tx_data),
        .s_axis_tvalid(uart_tx_valid),
        .s_axis_tready(uart_tx_ready),
        /* AXI-Stream Interface (Master) */
        .m_axis_tdata(uart_rx_data),
        .m_axis_tuser(),				/* Parity Error */
        .m_axis_tvalid(uart_rx_valid),
        .m_axis_tready(uart_rx_ready),
        // UART Port
        .tx(uart_tx),
        .rx(uart_rx),
        .rts(),						/* Active when FLOW_CONTROL == 1 */
        .cts()							/* Active when FLOW_CONTROL == 1 */
        //.probe_baud(probe_baud)
    );

endmodule
