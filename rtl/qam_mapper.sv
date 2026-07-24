/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/qam_mapper.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211 S7.3.1.2
 *
 * Byte-serial to QAM symbol mapper supporting QPSK through 256-QAM.
 *
 * Each input byte produces one output symbol. The lower mod_order bits of
 * s_axis_tdata are interpreted as the Gray-coded constellation index; upper
 * bits are ignored. I and Q are signed IQ_W-bit integers scaled so that peak
 * amplitude is +/-90 (of +/-127), leaving headroom for downstream processing.
 *
 * Bit packing convention (matches qam_demapper.sv):
 *   mod_order=2 : s_axis_tdata[1]   = I-axis bit,    s_axis_tdata[0]   = Q-axis bit
 *   mod_order=4 : s_axis_tdata[3:2] = I-axis 2-bit,  s_axis_tdata[1:0] = Q-axis 2-bit
 *   mod_order=6 : s_axis_tdata[5:3] = I-axis 3-bit,  s_axis_tdata[2:0] = Q-axis 3-bit
 *   mod_order=8 : s_axis_tdata[7:4] = I-axis 4-bit,  s_axis_tdata[3:0] = Q-axis 4-bit
 *
 * Output packing: m_axis_tdata = { I[IQ_W-1:0], Q[IQ_W-1:0] }
 *
 * Protocol:
 *   No backpressure. m_axis_tvalid is asserted one cycle after s_axis_tvalid.
 *   m_axis_tlast mirrors s_axis_tlast delayed one cycle.
 *   s_axis_tready is always asserted (unit-latency, no buffering required).
 */

`timescale 1ns / 1ps

module qam_mapper #(
    parameter int unsigned DATA_W = 8,  // s_axis_tdata width (>= mod_order)
    parameter int unsigned IQ_W   = 8   // per-component output width; m_axis_tdata = 2*IQ_W
) (
    input  logic              clk,
    input  logic              rst_n,
    input  logic [       3:0] mod_order,      // bits per symbol: 2 4 6 8
    input  logic [DATA_W-1:0] s_axis_tdata,
    input  logic              s_axis_tvalid,
    input  logic              s_axis_tlast,
    output logic              s_axis_tready,
    output logic [2*IQ_W-1:0] m_axis_tdata,
    output logic              m_axis_tvalid,
    output logic              m_axis_tlast,
    input  logic              m_axis_tready
);

    /*
     * Gray-coded constellation axis functions
     *
     * Each function maps the axis bit-pattern to a signed amplitude.
     * Constellation levels per TS 38.211 Table 7.3.1.2-{1..4}; amplitudes
     * are integers proportional to the normalised values (1/sqrt M scaling):
     *
     *   QPSK   : +/-90  (~ 1/sqrt 2  x 128)
     *   16-QAM : +/-24, +/-72 (~ 1/sqrt 10 x 128 x {1,3})
     *   64-QAM : +/-12, +/-36, +/-60, +/-84 (~ 1/sqrt 42 x 128 x {1,3,5,7})
     *   256-QAM: +/-6, +/-18, ..., +/-90  (~ 1/sqrt 170 x 128 x {1,3,...,15})
     */

    function automatic logic signed [7:0] qpsk_val(input logic b);
        return b ? -8'sd90 : 8'sd90;
    endfunction : qpsk_val

    function automatic logic signed [7:0] qam16_val(input logic [1:0] b);
        unique case (b)
            2'b00:   return 8'sd72;
            2'b01:   return 8'sd24;
            2'b11:   return -8'sd24;
            2'b10:   return -8'sd72;
            default: return 8'sd0;
        endcase
    endfunction : qam16_val

    function automatic logic signed [7:0] qam64_val(input logic [2:0] b);
        unique case (b)
            3'b000:  return 8'sd84;
            3'b001:  return 8'sd60;
            3'b011:  return 8'sd36;
            3'b010:  return 8'sd12;
            3'b110:  return -8'sd12;
            3'b111:  return -8'sd36;
            3'b101:  return -8'sd60;
            3'b100:  return -8'sd84;
            default: return 8'sd0;
        endcase
    endfunction : qam64_val

    function automatic logic signed [7:0] qam256_val(input logic [3:0] b);
        unique case (b)
            4'b0000: return 8'sd90;
            4'b0001: return 8'sd78;
            4'b0011: return 8'sd66;
            4'b0010: return 8'sd54;
            4'b0110: return 8'sd42;
            4'b0111: return 8'sd30;
            4'b0101: return 8'sd18;
            4'b0100: return 8'sd6;
            4'b1100: return -8'sd6;
            4'b1101: return -8'sd18;
            4'b1111: return -8'sd30;
            4'b1110: return -8'sd42;
            4'b1010: return -8'sd54;
            4'b1011: return -8'sd66;
            4'b1001: return -8'sd78;
            4'b1000: return -8'sd90;
            default: return 8'sd0;
        endcase
    endfunction : qam256_val


    // Always ready: unit-latency, no input buffering required.
    assign s_axis_tready = 1'b1;

    // Internal symbol registers (fixed 8-bit; constellation values fit in 8 bits).
    logic signed [7:0] i_sym_r;
    logic signed [7:0] q_sym_r;

    // Pack I and Q into the wide output word: upper half = I, lower half = Q.
    assign m_axis_tdata = {IQ_W'(unsigned'(i_sym_r)), IQ_W'(unsigned'(q_sym_r))};


    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            i_sym_r       <= '0;
            q_sym_r       <= '0;
            m_axis_tvalid <= 1'b0;
            m_axis_tlast  <= 1'b0;
        end else begin
            m_axis_tvalid <= 1'b0;  // default: de-assert every cycle
            m_axis_tlast  <= 1'b0;

            if (s_axis_tvalid) begin
                m_axis_tvalid <= 1'b1;
                m_axis_tlast  <= s_axis_tlast;

                case (mod_order)
                    3'd2: begin
                        i_sym_r <= qpsk_val(s_axis_tdata[1]);
                        q_sym_r <= qpsk_val(s_axis_tdata[0]);
                    end
                    3'd4: begin
                        i_sym_r <= qam16_val(s_axis_tdata[3:2]);
                        q_sym_r <= qam16_val(s_axis_tdata[1:0]);
                    end
                    3'd6: begin
                        i_sym_r <= qam64_val(s_axis_tdata[5:3]);
                        q_sym_r <= qam64_val(s_axis_tdata[2:0]);
                    end
                    4'd8: begin
                        i_sym_r <= qam256_val(s_axis_tdata[7:4]);
                        q_sym_r <= qam256_val(s_axis_tdata[3:0]);
                    end
                    default: begin
                        i_sym_r <= 8'sd0;
                        q_sym_r <= 8'sd0;
                    end
                endcase  // mod_order
            end
        end
    end

endmodule : qam_mapper
