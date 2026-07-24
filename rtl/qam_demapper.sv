/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/qam_demapper.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211 S7.3.1.2
 *
 * Hard-decision QAM demapper. Inverts qam_mapper.sv by nearest-neighbour
 * threshold comparison on each signed I/Q axis independently.
 *
 * Input packing: s_axis_tdata = { I[IQ_W-1:0], Q[IQ_W-1:0] }
 * (mirrors qam_mapper.sv m_axis_tdata output packing)
 *
 * Decision boundaries are midpoints between adjacent constellation levels:
 *   QPSK   : threshold at 0
 *   16-QAM : thresholds at 0, +/-48
 *   64-QAM : thresholds at 0, +/-24, +/-48, +/-72
 *   256-QAM: thresholds at 0, +/-12, +/-24, +/-36, +/-48, +/-60, +/-72, +/-84
 *
 * Bit packing convention (mirrors qam_mapper.sv):
 *   mod_order=2 : m_axis_tdata[1]   = I bit,    m_axis_tdata[0]   = Q bit
 *   mod_order=4 : m_axis_tdata[3:2] = I 2-bit,  m_axis_tdata[1:0] = Q 2-bit
 *   mod_order=6 : m_axis_tdata[5:3] = I 3-bit,  m_axis_tdata[2:0] = Q 3-bit
 *   mod_order=8 : m_axis_tdata[7:4] = I 4-bit,  m_axis_tdata[3:0] = Q 4-bit
 * Upper bits beyond mod_order are driven to zero.
 *
 * Protocol:
 *   No backpressure. m_axis_tvalid is asserted one cycle after s_axis_tvalid.
 *   m_axis_tlast mirrors s_axis_tlast delayed one cycle.
 *   s_axis_tready is always asserted (unit-latency, no buffering required).
 */

`timescale 1ns / 1ps

module qam_demapper #(
    parameter int unsigned IQ_W   = 8,  // per-component input width; s_axis_tdata = 2*IQ_W
    parameter int unsigned DATA_W = 8   // m_axis_tdata width
) (
    input  logic              clk,
    input  logic              rst_n,
    input  logic [       3:0] mod_order,      // bits per symbol: 2 4 6 8
    input  logic [2*IQ_W-1:0] s_axis_tdata,
    input  logic              s_axis_tvalid,
    input  logic              s_axis_tlast,
    output logic              s_axis_tready,
    output logic [DATA_W-1:0] m_axis_tdata,
    output logic              m_axis_tvalid,
    output logic              m_axis_tlast,
    input  logic              m_axis_tready
);

    /*
     * Axis demapper functions
     *
     * Each function returns the Gray-coded bit pattern for the nearest
     * constellation point on one axis, using the same thresholds as the
     * midpoints between qam_mapper.sv output levels.
     */

    function automatic logic demap_qpsk(input logic signed [7:0] v);
        // Threshold at 0. Level +90 -> 0; level -90 -> 1.
        return (v >= 8'sd0) ? 1'b0 : 1'b1;
    endfunction : demap_qpsk

    function automatic logic [1:0] demap_qam16(input logic signed [7:0] v);
        // Thresholds at 0 and +/-48 (midpoints of +/-24, +/-72 levels).
        if (v > 8'sd48) return 2'b00;
        else if (v > 8'sd0) return 2'b01;
        else if (v > -8'sd48) return 2'b11;
        else return 2'b10;
    endfunction : demap_qam16

    function automatic logic [2:0] demap_qam64(input logic signed [7:0] v);
        // Thresholds at 0, +/-24, +/-48, +/-72 (midpoints of +/-12,+/-36,+/-60,+/-84 levels).
        if (v > 8'sd72) return 3'b000;
        else if (v > 8'sd48) return 3'b001;
        else if (v > 8'sd24) return 3'b011;
        else if (v > 8'sd0) return 3'b010;
        else if (v > -8'sd24) return 3'b110;
        else if (v > -8'sd48) return 3'b111;
        else if (v > -8'sd72) return 3'b101;
        else return 3'b100;
    endfunction : demap_qam64

    function automatic logic [3:0] demap_qam256(input logic signed [7:0] v);
        // Thresholds at 0, +/-12, +/-24, +/-36, +/-48, +/-60, +/-72, +/-84
        // (midpoints of +/-6, +/-18, ..., +/-90 levels).
        if (v > 8'sd84) return 4'b0000;
        else if (v > 8'sd72) return 4'b0001;
        else if (v > 8'sd60) return 4'b0011;
        else if (v > 8'sd48) return 4'b0010;
        else if (v > 8'sd36) return 4'b0110;
        else if (v > 8'sd24) return 4'b0111;
        else if (v > 8'sd12) return 4'b0101;
        else if (v > 8'sd0) return 4'b0100;
        else if (v > -8'sd12) return 4'b1100;
        else if (v > -8'sd24) return 4'b1101;
        else if (v > -8'sd36) return 4'b1111;
        else if (v > -8'sd48) return 4'b1110;
        else if (v > -8'sd60) return 4'b1010;
        else if (v > -8'sd72) return 4'b1011;
        else if (v > -8'sd84) return 4'b1001;
        else return 4'b1000;
    endfunction : demap_qam256


    // Unpack I and Q from the wide input word.
    logic signed [IQ_W-1:0] i_sym;
    logic signed [IQ_W-1:0] q_sym;

    assign i_sym = signed'(s_axis_tdata[2*IQ_W-1 : IQ_W]);
    assign q_sym = signed'(s_axis_tdata[IQ_W-1   :    0]);

    // Always ready: unit-latency, no input buffering required.
    assign s_axis_tready = 1'b1;


    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            m_axis_tdata  <= '0;
            m_axis_tvalid <= 1'b0;
            m_axis_tlast  <= 1'b0;
        end else begin
            m_axis_tvalid <= 1'b0;  // default: de-assert every cycle
            m_axis_tlast  <= 1'b0;

            if (s_axis_tvalid) begin
                m_axis_tvalid <= 1'b1;
                m_axis_tlast  <= s_axis_tlast;

                case (mod_order)
                    3'd2: m_axis_tdata <= DATA_W'({6'b0, demap_qpsk(i_sym), demap_qpsk(q_sym)});
                    3'd4: m_axis_tdata <= DATA_W'({4'b0, demap_qam16(i_sym), demap_qam16(q_sym)});
                    3'd6: m_axis_tdata <= DATA_W'({2'b0, demap_qam64(i_sym), demap_qam64(q_sym)});
                    4'd8: m_axis_tdata <= DATA_W'({demap_qam256(i_sym), demap_qam256(q_sym)});
                    default: m_axis_tdata <= '0;
                endcase  // mod_order
            end
        end
    end

endmodule : qam_demapper
