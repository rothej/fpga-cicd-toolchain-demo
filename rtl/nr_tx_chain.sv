/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/nr_tx_chain.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211
 *
 * 5G NR physical-layer TX integration wrapper.
 *
 * Data flow:
 *   s_axis (bytes) -> scrambler -> qam_mapper -> cp_inserter -> m_axis (samples)
 *
 * Latency:
 *   scrambler    : 1 cycle (registered output)
 *   qam_mapper   : 1 cycle (registered output)
 *   cp_inserter  : N_FFT cycles (fill buffer) + combinational output
 *
 * Scrambler re-seed protocol (TX_CINIT / TX_IDLE state machine)
 * ---------------------------------------------------------------
 * The scrambler must reload once before byte 0 of every transport block, and
 * must not reload mid-block.  Two constraints make a passive idle-window
 * approach unworkable:
 *
 *   (a) AXI-S requires the initiator to hold tvalid high until tready is
 *       asserted; there is never a guaranteed tvalid=0 gap between blocks.
 *
 *   (b) Each 64-byte / QPSK transport block spans four OFDM symbols (256
 *       mapper outputs / N_FFT=64).  An EMIT->FILL edge trigger would fire
 *       four times per block, reloading the LFSR mid-stream.
 *
 * The state machine actively creates a one-cycle tready=0 window:
 *
 *   TX_CINIT  tready=0 (CINIT gating).  On the first tvalid=1 of each new
 *             block, tx_cinit_load fires combinationally (the LFSR reloads
 *             from scrambler_seed), and the state transitions to TX_IDLE.
 *             Byte 0 is held off this cycle; it is accepted on the next.
 *
 *   TX_IDLE   Normal operation.  tready=sym_ready (cp_inserter backpressure).
 *             Returns to TX_CINIT on the last accepted input byte (tlast).
 *
 * Backpressure propagation:
 *   s_axis_tready = sym_ready && (tx_state == TX_IDLE).
 *   The scrambler's tvalid input is gated with s_axis_tready so the LFSR
 *   only advances on cycles where data is actually consumed by the pipeline.
 *   Without this gate, the LFSR advances during cp_inserter EMIT stalls,
 *   desynchronising the TX Gold sequence from the RX descrambler.
 *
 * Note on CRC: CRC attachment is not performed in this wrapper; transport
 * block payload is scrambled, mapped, and CP-inserted directly. CRC
 * verification is exercised independently by the crc_engine / crc_checker
 * unit testbenches.
 */

`timescale 1ns / 1ps

module nr_tx_chain #(
    parameter int N_FFT      = 128,
    parameter int CP_LEN_MAX = 16,
    parameter int SAMP_W     = 16,   // total I+Q width at output (2 × IQ_W)
    parameter int MOD_ORDER  = 2,    // bits per QAM symbol (compile-time)
    parameter int DATA_W     = 8,
    parameter int POLY_W     = 24    // accepted for interface compatibility; unused here
) (
    input logic clk,
    input logic rst_n,

    // AXI4-Stream slave (payload input)
    input  logic              s_axis_tvalid,
    output logic              s_axis_tready,
    input  logic [DATA_W-1:0] s_axis_tdata,
    input  logic              s_axis_tlast,

    // Sideband configuration - stable for the duration of one transport block
    input logic [$clog2(CP_LEN_MAX+1)-1:0] cp_len,
    input logic [                    31:0] scrambler_seed,

    // AXI4-Stream master (OFDM sample output)
    output logic              m_axis_tvalid,
    input  logic              m_axis_tready,
    output logic [SAMP_W-1:0] m_axis_tdata,
    output logic              m_axis_tlast
);

    localparam int unsigned IQ_W = SAMP_W / 2;  // per-component width

    /*
     * sym_ready: cp_inserter.s_axis_tready.
     * Declared early; driven by the cp_inserter port connection at the bottom.
     * 1 during FILL (accepting symbols), 0 during EMIT (outputting OFDM symbol).
     */
    logic sym_ready;


    /*
     * TX cinit state machine
     *
     * TX_CINIT : holds s_axis_tready=0; fires tx_cinit_load on the first
     *            tvalid=1 of the new block; transitions to TX_IDLE immediately
     *            so tready releases on the following cycle.
     *
     * TX_IDLE  : normal operation; re-arms (-> TX_CINIT) on s_axis_tlast.
     *
     * Reset enters TX_CINIT so the very first block is seeded before byte 0.
     */
    localparam logic TX_IDLE = 1'b0;
    localparam logic TX_CINIT = 1'b1;

    logic tx_state;
    logic tx_cinit_load;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_state <= TX_CINIT;
        end else if (tx_state == TX_CINIT) begin
            // Fire cinit this cycle (combinational below), release tready next.
            if (s_axis_tvalid) tx_state <= TX_IDLE;
        end else begin  // TX_IDLE
            // Re-arm at the end of the transport block.
            if (s_axis_tvalid && s_axis_tready && s_axis_tlast) tx_state <= TX_CINIT;
        end
    end

    // tx_cinit_load: combinational, fires exactly once per block.
    // tready=0 this cycle (CINIT gating) -> byte 0 is NOT accepted yet.
    // On the next cycle tx_state=IDLE, tready=sym_ready, byte 0 is accepted
    // with the freshly loaded LFSR.
    assign tx_cinit_load = (tx_state == TX_CINIT) && s_axis_tvalid;

    // s_axis_tready: propagate cp_inserter backpressure AND hold low in CINIT.
    assign s_axis_tready = sym_ready && (tx_state == TX_IDLE);


    /*
     * scrambler -> qam_mapper connection
     */

    logic [DATA_W-1:0] scr_data;
    logic              scr_valid;
    logic              scr_last;
    logic              scr_ready;

    scrambler #(
        .DATA_W(DATA_W)
    ) u_scrambler (
        .clk          (clk),
        .rst_n        (rst_n),
        .cinit_load   (tx_cinit_load),
        .cinit        (scrambler_seed[30:0]),
        // Gate tvalid with s_axis_tready: LFSR advances only when data is
        // consumed by the pipeline. Without this gate the LFSR runs ahead
        // during cp_inserter EMIT stalls, desynchronising TX and RX.
        .s_axis_tdata (s_axis_tdata),
        .s_axis_tvalid(s_axis_tvalid && s_axis_tready),
        .s_axis_tlast (s_axis_tlast),
        .s_axis_tready(),                                // always 1 internally; not routed up
        .m_axis_tdata (scr_data),
        .m_axis_tvalid(scr_valid),
        .m_axis_tlast (scr_last),
        .m_axis_tready(scr_ready)
    );


    /*
     * qam_mapper -> cp_inserter connection
     */

    logic [SAMP_W-1:0] sym_data;
    logic              sym_valid;
    logic              sym_last;

    qam_mapper #(
        .DATA_W(DATA_W),
        .IQ_W  (IQ_W)
    ) u_qam_mapper (
        .clk          (clk),
        .rst_n        (rst_n),
        .mod_order    (4'(MOD_ORDER)),
        .s_axis_tdata (scr_data),
        .s_axis_tvalid(scr_valid),
        .s_axis_tlast (scr_last),
        .s_axis_tready(scr_ready),
        .m_axis_tdata (sym_data),
        .m_axis_tvalid(sym_valid),
        .m_axis_tlast (sym_last),
        .m_axis_tready(sym_ready)
    );


    /*
     * cp_inserter output
     *
     * sym_ready is driven here (cp_inserter.s_axis_tready) and read above
     * by the cinit state machine and the s_axis_tready assignment.
     */

    cp_inserter #(
        .N_FFT     (N_FFT),
        .CP_LEN_MAX(CP_LEN_MAX),
        .SAMP_W    (SAMP_W)
    ) u_cp_inserter (
        .clk          (clk),
        .rst_n        (rst_n),
        .s_axis_tdata (sym_data),
        .s_axis_tvalid(sym_valid),
        .s_axis_tlast (sym_last),
        .s_axis_tready(sym_ready),
        .cp_len       (cp_len),
        .m_axis_tdata (m_axis_tdata),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tlast (m_axis_tlast),
        .m_axis_tready(m_axis_tready)
    );

endmodule : nr_tx_chain
