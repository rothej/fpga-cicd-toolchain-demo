/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/cp_remover.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211 S5.3.1
 *
 * Cyclic prefix (CP) remover for received OFDM symbols.
 * Discards the first cp_len samples of each cp_len + N_FFT input burst
 * and forwards the remaining N_FFT samples to the output.
 *
 * cp_len is a runtime port (not a parameter); it must be stable from the
 * first beat of each burst until the burst completes. CP_LEN_MAX sizes the
 * port and gap-detection counter. The module tracks cp_len during idle
 * cycles (s_axis_tvalid = 0) so it is correctly captured before the first
 * beat of each burst (driver protocol: assert cp_len one cycle before tvalid).
 *
 * State machine:
 *   SKIP_CP : count and discard cp_len_r samples; when cp_len_r == 0 the
 *             state transitions immediately without consuming any input beat.
 *   PASS    : forward N_FFT samples; assert m_axis_tlast on the final sample.
 *
 * Protocol:
 *   AXI4-Stream slave on input; s_axis_tready is asserted only when beats
 *   will actually be consumed (1 in SKIP_CP when cp_len_r != 0, and
 *   m_axis_tready in PASS). AXI4-Stream master on output.
 *   s_axis_tlast is accepted on the port for protocol compliance; the module
 *   counts samples internally rather than relying on s_axis_tlast framing.
 */

`timescale 1ns / 1ps

module cp_remover #(
    parameter int unsigned N_FFT      = 128,
    parameter int unsigned CP_LEN_MAX = 16,
    parameter int unsigned SAMP_W     = 16
) (
    input logic clk,
    input logic rst_n,

    // AXI4-Stream slave (received CP+symbol)
    input  logic [SAMP_W-1:0] s_axis_tdata,
    input  logic              s_axis_tvalid,
    input  logic              s_axis_tlast,   // informational; counted internally
    output logic              s_axis_tready,

    // Runtime CP length - must be stable for the duration of one burst.
    input logic [$clog2(CP_LEN_MAX+1)-1:0] cp_len,

    // AXI4-Stream master (CP-stripped payload)
    output logic [SAMP_W-1:0] m_axis_tdata,
    output logic              m_axis_tvalid,
    output logic              m_axis_tlast,
    input  logic              m_axis_tready
);

    localparam int unsigned CP_W = $clog2(CP_LEN_MAX + 1);
    localparam int unsigned CNT_W = $clog2(N_FFT) + 1;

    typedef enum logic {
        SKIP_CP,
        PASS
    } state_t;

    state_t             state;
    logic   [CNT_W-1:0] cnt;
    logic   [ CP_W-1:0] cp_len_r;  // cp_len sampled while idle in SKIP_CP


    /*
     * Combinational output
     *
     * s_axis_tready: accept input only when it will be consumed.
     *   SKIP_CP + cp_len_r != 0  -> 1 (discard beats)
     *   SKIP_CP + cp_len_r == 0  -> 0 (transitioning without consuming)
     *   PASS                     -> m_axis_tready (matched throughput)
     */
    always_comb begin
        case (state)
            SKIP_CP: s_axis_tready = (cp_len_r != '0);
            PASS:    s_axis_tready = m_axis_tready;
            default: s_axis_tready = 1'b0;
        endcase

        m_axis_tdata  = '0;
        m_axis_tvalid = 1'b0;
        m_axis_tlast  = 1'b0;

        if (state == PASS && s_axis_tvalid) begin
            m_axis_tdata  = s_axis_tdata;
            m_axis_tvalid = 1'b1;
            m_axis_tlast  = (cnt == CNT_W'(N_FFT - 1));
        end
    end


    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= SKIP_CP;
            cnt      <= '0;
            cp_len_r <= '0;
        end else begin
            case (state)
                SKIP_CP: begin
                    if (!s_axis_tvalid) begin
                        cp_len_r <= cp_len;  // latch cp_len while idle
                    end else begin  // s_axis_tvalid asserted
                        if (cp_len_r == '0) begin
                            // No CP: transition without consuming a beat.
                            state <= PASS;
                            cnt   <= '0;
                        end else begin
                            // s_axis_tready=1: beat is consumed and discarded.
                            if (cnt == CNT_W'(cp_len_r) - 1'b1) begin
                                cnt   <= '0;
                                state <= PASS;
                            end else begin
                                cnt <= cnt + 1'b1;
                            end
                        end
                    end
                end  // SKIP_CP

                PASS: begin
                    if (s_axis_tvalid && m_axis_tready) begin
                        if (cnt == CNT_W'(N_FFT - 1)) begin
                            cnt   <= '0;
                            state <= SKIP_CP;
                            // cp_len_r will be re-latched during SKIP_CP idle cycles.
                        end else begin
                            cnt <= cnt + 1'b1;
                        end
                    end
                end  // PASS

                default: state <= SKIP_CP;
            endcase  // state
        end
    end

endmodule : cp_remover
