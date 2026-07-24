/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/cp_inserter.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211 S5.3.1
 *
 * Cyclic prefix (CP) inserter for OFDM symbols.
 *
 * Collects N_FFT complex samples (packed as SAMP_W-bit words) into an internal
 * buffer, then outputs the last cp_len samples (the cyclic prefix) followed by
 * all N_FFT samples, for a total of cp_len + N_FFT samples per output burst.
 *
 * cp_len is a runtime port (not a parameter); it must be stable from the first
 * s_axis_tvalid beat until the corresponding m_axis_tlast. It is latched when
 * FILL completes. CP_LEN_MAX sizes the port and internal counters.
 *
 * State machine:
 *   FILL     : receive N_FFT samples; write each to samp_buf[fill_ptr]
 *   EMIT_CP  : output samp_buf[cp_start .. N_FFT-1] (cp_len samples)
 *   EMIT_SYM : output samp_buf[0 .. N_FFT-1] (N_FFT samples); assert
 *              m_axis_tlast on the final sample then return to FILL
 *
 * Protocol:
 *   AXI4-Stream slave on input (s_axis_*); s_axis_tready is asserted only
 *   during FILL. AXI4-Stream master on output (m_axis_*); m_axis_tready
 *   gates emission in EMIT_CP and EMIT_SYM.
 *   s_axis_tlast exits FILL early; remaining buffer entries retain stale
 *   values. Callers should always present exactly N_FFT beats or assert
 *   s_axis_tlast on the N_FFT-th beat for deterministic output.
 */

`timescale 1ns / 1ps

module cp_inserter #(
    parameter int unsigned N_FFT      = 128,
    parameter int unsigned CP_LEN_MAX = 16,
    parameter int unsigned SAMP_W     = 16
) (
    input logic clk,
    input logic rst_n,

    // AXI4-Stream slave (input samples)
    input  logic [SAMP_W-1:0] s_axis_tdata,
    input  logic              s_axis_tvalid,
    input  logic              s_axis_tlast,
    output logic              s_axis_tready,

    // Runtime CP length - must be stable for the duration of one symbol.
    input logic [$clog2(CP_LEN_MAX+1)-1:0] cp_len,

    // AXI4-Stream master (CP-inserted output)
    output logic [SAMP_W-1:0] m_axis_tdata,
    output logic              m_axis_tvalid,
    output logic              m_axis_tlast,
    input  logic              m_axis_tready
);

    localparam int unsigned CP_W = $clog2(CP_LEN_MAX + 1);
    localparam int unsigned CNT_W = $clog2(N_FFT) + 1;

    typedef enum logic [1:0] {
        FILL,
        EMIT_CP,
        EMIT_SYM
    } state_t;

    state_t state;

    logic [CNT_W-1:0] fill_ptr;
    logic [CNT_W-1:0] emit_cnt;
    logic [CNT_W-1:0] cp_start;  // = N_FFT - cp_len_r, latched when FILL completes
    logic [CP_W-1:0] cp_len_r;  // latched cp_len

    // Sample buffer - one SAMP_W-bit word per symbol sample.
    logic [SAMP_W-1:0] samp_buf[N_FFT];


    /*
     * Combinational output
     */
    always_comb begin
        s_axis_tready = (state == FILL);

        m_axis_tdata  = '0;
        m_axis_tvalid = 1'b0;
        m_axis_tlast  = 1'b0;

        if (state == EMIT_CP) begin
            m_axis_tvalid = 1'b1;
            m_axis_tdata  = samp_buf[cp_start+emit_cnt];
        end else if (state == EMIT_SYM) begin
            m_axis_tvalid = 1'b1;
            m_axis_tlast  = (emit_cnt == CNT_W'(N_FFT - 1));
            m_axis_tdata  = samp_buf[emit_cnt];
        end
    end


    /*
     * State machine and buffer write
     */
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= FILL;
            fill_ptr <= '0;
            emit_cnt <= '0;
            cp_start <= '0;
            cp_len_r <= '0;
        end else begin
            case (state)
                FILL: begin
                    if (s_axis_tvalid) begin  // s_axis_tready = 1 in FILL
                        samp_buf[fill_ptr] <= s_axis_tdata;

                        if (fill_ptr == CNT_W'(N_FFT - 1) || s_axis_tlast) begin
                            // Latch cp_len and compute cp_start for the EMIT phases.
                            cp_len_r <= cp_len;
                            cp_start <= CNT_W'(N_FFT) - CNT_W'(cp_len);
                            fill_ptr <= '0;
                            emit_cnt <= '0;
                            // Skip EMIT_CP entirely when cp_len == 0.
                            if (cp_len == '0) begin
                                state <= EMIT_SYM;
                            end else begin
                                state <= EMIT_CP;
                            end
                        end else begin
                            fill_ptr <= fill_ptr + 1'b1;
                        end
                    end
                end

                EMIT_CP: begin
                    if (m_axis_tready) begin
                        if (emit_cnt == CNT_W'(cp_len_r) - 1'b1) begin
                            emit_cnt <= '0;
                            state    <= EMIT_SYM;
                        end else begin
                            emit_cnt <= emit_cnt + 1'b1;
                        end
                    end
                end

                EMIT_SYM: begin
                    if (m_axis_tready) begin
                        if (emit_cnt == CNT_W'(N_FFT - 1)) begin
                            emit_cnt <= '0;
                            state    <= FILL;
                        end else begin
                            emit_cnt <= emit_cnt + 1'b1;
                        end
                    end
                end

                default: state <= FILL;
            endcase  // state
        end
    end

endmodule : cp_inserter
