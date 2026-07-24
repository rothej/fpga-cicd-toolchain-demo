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
 * Scrambler seeding:
 *   The scrambler is re-seeded (cinit_load) once before each transport block.
 *   A need_cinit flag is set at reset and after each m_axis_tlast. It fires
 *   cinit_load on the first idle cycle (s_axis_tvalid = 0) thereafter.
 *   The driver protocol guarantees at least one idle cycle between the
 *   sideband setup and the first s_axis_tvalid of each transport block.
 *
 * Note on CRC: CRC attachment is not performed in this wrapper; transport
 * block payload is scrambled, mapped, and CP-inserted directly. CRC
 * verification is exercised independently by the crc_engine / crc_checker
 * unit testbenches. Integration-level data-path correctness is validated
 * through the scoreboard's payload comparison (rx.data == tx.payload).
 *
 * All sub-module parameters and runtime configuration ports are derived from
 * the top-level parameters and sideband inputs. mod_order is a compile-time
 * parameter; cp_len and scrambler_seed are runtime sidebands.
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
     * Scrambler re-seed logic
     *
     * need_cinit is set at reset and after each completed transport block
     * (m_axis_tlast). cinit_load fires on the first idle input cycle thereafter.
     */
    logic need_cinit;
    logic tx_cinit_load;

    assign tx_cinit_load = need_cinit && !s_axis_tvalid;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            need_cinit <= 1'b1;
        end else begin
            if (m_axis_tvalid && m_axis_tlast && m_axis_tready) begin
                need_cinit <= 1'b1;
            end else if (tx_cinit_load) begin
                need_cinit <= 1'b0;
            end
        end
    end


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
        .s_axis_tdata (s_axis_tdata),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tlast (s_axis_tlast),
        .s_axis_tready(s_axis_tready),
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
    logic              sym_ready;

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
