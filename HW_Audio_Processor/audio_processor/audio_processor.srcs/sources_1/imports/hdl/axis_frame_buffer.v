`timescale 1ns / 1ps
`default_nettype none
//////////////////////////////////////////////////////////////////////////////////
// Company: Digilent
// Engineer: Arthur Brown
//
// Create Date: 03/23/2018 01:23:15 PM
// Module Name: axis_volume_controller
// Description: AXI-Stream volume controller intended for use with AXI Stream Pmod I2S2 controller.
//              Whenever a 2-word packet is received on the slave interface, it is multiplied by
//              the value of the switches, taken to represent the range 0.0:1.0, then sent over the
//              master interface. Reception of data on the slave interface is halted while processing and
//              transfer is taking place.
//
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
//
//////////////////////////////////////////////////////////////////////////////////

module axis_frame_buffer #(
    parameter DATA_WIDTH = 24,
    parameter BUFFER_DEPTH = 1024
) (
    input wire      axis_clk,
    input  wire     axis_resetn,

    //AXIS SLAVE INTERFACE
    input  wire [DATA_WIDTH-1:0] s_axis_data,
    input  wire s_axis_valid,
    output wire s_axis_ready,
    input  wire s_axis_last,

    // AXIS MASTER INTERFACE
    output wire [DATA_WIDTH-1:0] m_axis_data,
    output wire m_axis_valid,
    input  wire m_axis_ready,
    output wire m_axis_last,

    //AXIS UART-RX INTERFACE
    input  wire [15:0] s_rx_data,
    input  wire s_rx_valid,
    output wire s_rx_ready,
    //input  wire s_rx_last,

    // AXIS UART-TX INTERFACE
    output wire [15:0] m_tx_data,
    output wire m_tx_valid,
    input  wire m_tx_ready,
    //output wire m_tx_last

    output wire [15:0] led
);
    localparam PTR_WIDTH = $clog2(BUFFER_DEPTH) + 1; // +1 added for security, when depth is not a power of 2

    (* ram_style = "block" *) reg [DATA_WIDTH-1:0] buffer  [0:BUFFER_DEPTH];
    (* ram_style = "block" *) reg [DATA_WIDTH-1:0] display [0:BUFFER_DEPTH];
    reg [PTR_WIDTH-1:0] buffer_ptr;
    reg LR_flag;

    wire [DATA_WIDTH-1:0] axis_sm_data;
    wire axis_sm_valid;
    wire axis_sm_ready;
    wire axis_sm_last;

    // Pass-through of the Audio Stream
    assign axis_sm_data = s_axis_data;
    assign axis_sm_valid = s_axis_valid;
    assign axis_sm_ready = m_axis_ready;
    assign axis_sm_last = s_axis_last;

    assign m_axis_data = axis_sm_data;
    assign m_axis_valid = axis_sm_valid;
    assign s_axis_ready = axis_sm_ready;
    assign m_axis_last = axis_sm_last;

    // Store the Audio Data into the internal buffer
    always @(posedge axis_clk)
    begin
        if (axis_resetn == 1'b0) begin
            buffer_ptr <= {PTR_WIDTH{1'b0}};
            LR_flag <= 1'b0;
        end
        else begin
            if (axis_sm_valid) begin
                LR_flag <= ~LR_flag;
                if (LR_flag) begin
                    buffer_ptr <= (buffer_ptr == BUFFER_DEPTH-1) ? {PTR_WIDTH{1'b0}} : buffer_ptr + 1;
                end
            end
        end
    end

    integer i;

    always @(posedge axis_clk)
    begin
        if (axis_resetn == 1'b0) begin
            for (i = 0; i < BUFFER_DEPTH; i=i+1) begin
                buffer[i] <= {DATA_WIDTH{1'b0}};
            end
        end
        else begin
            if (axis_sm_valid && LR_flag) begin
                buffer[buffer_ptr] <= axis_sm_data;
            end
        end
    end

    // Indication of the UART command
    reg [15:0] uart_data_reg;
    assign led = uart_data_reg;

    always @(posedge axis_clk) begin
        if (!axis_resetn) begin
            uart_data_reg <= 16'b0;
        end
        else begin
            if (s_rx_valid) begin
                uart_data_reg <= s_rx_data;
            end
        end
    end

    // UART response state-machine
    localparam STATE_IDLE         = 4'h0;
    localparam STATE_WAIT_BUFFER  = 4'h1;
    localparam STATE_COPY_BUFFER  = 4'h2;
    localparam STATE_TAKE_SAMPLE  = 4'h3;
    localparam STATE_TAKE_BYTE    = 4'h4;
    localparam STATE_WAIT_SENDER  = 4'h5;
    localparam STATE_SEND_BYTE    = 4'h6;
    localparam STATE_END_SAMPLE   = 4'h7;
    localparam STATE_END_TRANSFER = 4'h8;

    localparam cmd_get_wave = 8'h57;    // 'W' - get waveform
    localparam cmd_get_spec = 8'h53;    // 'S' - get spectrum

    assign m_tx_data  = r_send_byte;  // Data to send to uart
    assign m_tx_valid = m_tx_ready & (r_fsm == STATE_SEND_BYTE);
    //assign s_rx_ready = m_tx_ready;
    assign s_rx_ready = (r_fsm == STATE_IDLE);

    reg [3:0] r_fsm;
    reg [PTR_WIDTH-1:0] r_send_ptr;
    reg [DATA_WIDTH-1:0] r_send_sample;
    reg [1:0] r_byte_counter;
    reg [7:0] r_send_byte;

    always @(posedge axis_clk) begin
        if (!axis_resetn) begin
            r_fsm          <= STATE_IDLE;
            r_send_ptr     <= {PTR_WIDTH{1'b0}};
            r_byte_counter <= 2'b0;
            r_send_sample  <= {DATA_WIDTH{1'b0}};
            r_send_byte    <= 8'b0;
        end
        else begin
            case (r_fsm)
                STATE_IDLE: begin
                    if (s_rx_valid && (s_rx_data == cmd_get_wave)) begin
                        r_fsm <= ((buffer_ptr == BUFFER_DEPTH-1) && LR_flag) ? STATE_COPY_BUFFER : STATE_WAIT_BUFFER;
                    end
                    else if (s_rx_valid) begin
                        r_send_byte <= s_rx_data[7:0];
                        r_byte_counter <= 2'b10;
                        r_send_ptr <= BUFFER_DEPTH-1;
                        r_fsm <= STATE_WAIT_SENDER;
                    end
                end
                STATE_WAIT_BUFFER: begin
                    r_fsm <= ((buffer_ptr == BUFFER_DEPTH-1) && LR_flag) ? STATE_COPY_BUFFER : STATE_WAIT_BUFFER;
                end
                STATE_COPY_BUFFER: begin
                    r_fsm <= STATE_TAKE_SAMPLE;
                    r_send_ptr <= {PTR_WIDTH{1'b0}};
                end
                STATE_TAKE_SAMPLE: begin
                    r_send_sample <= display[r_send_ptr];
                    r_byte_counter <= 2'b0;
                    r_fsm <= STATE_TAKE_BYTE;
                end
                STATE_TAKE_BYTE: begin
                    r_send_byte <= r_byte_counter[1:1] ? r_send_sample[23:16] : r_byte_counter[0:0] ? r_send_sample[15:8] : r_send_sample[7:0];
                    r_fsm <= m_tx_ready ? STATE_SEND_BYTE : STATE_WAIT_SENDER;
                end
                STATE_WAIT_SENDER: begin
                    r_fsm <= m_tx_ready ? STATE_SEND_BYTE : STATE_WAIT_SENDER;
                end
                STATE_SEND_BYTE: begin
                    if (r_byte_counter == 2'b10) begin
                        r_byte_counter <= 2'b0;
                        r_fsm <= STATE_END_SAMPLE;
                    end
                    else begin
                        r_byte_counter <= r_byte_counter + 2'b01;
                        r_fsm <= STATE_TAKE_BYTE;
                    end
                end
                STATE_END_SAMPLE: begin
                    if (r_send_ptr == BUFFER_DEPTH-1) begin
                        r_send_ptr <= {PTR_WIDTH{1'b0}};
                        r_fsm <= STATE_END_TRANSFER;
                        //r_fsm <= STATE_IDLE;
                    end
                    else begin
                        r_send_ptr <= r_send_ptr + 1;
                        r_fsm <= STATE_TAKE_SAMPLE;
                    end
                end
                STATE_END_TRANSFER: begin
                    r_fsm <= STATE_IDLE;
                end
                default: begin
                    r_fsm <= STATE_IDLE;
                end
            endcase
        end
    end

    // Copy Buffer to DisplayBuffer once ready (ptr points to the end)
    always @(posedge axis_clk) begin
        if (!axis_resetn) begin
            for (i = 0; i < BUFFER_DEPTH; i=i+1) begin
                display[i] <= {DATA_WIDTH{1'b0}};
            end
        end
        else begin
            if (r_fsm == STATE_COPY_BUFFER) begin
                for (i = 0; i < BUFFER_DEPTH; i=i+1) begin
                    display[i] <= buffer[i];
                end
            end
        end
    end

endmodule
