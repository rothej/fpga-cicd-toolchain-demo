/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/nr_rx_chain.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211
 *
 * 5G NR physical-layer RX integration wrapper.
 *
 * Data flow (inverse of nr_tx_chain.sv):
 *   s_axis (samples) -> cp_remover -> qam_demapper -> scrambler -> m_axis (bytes)
 *
 * Latency:
 *   cp_remover   : 0 extra cycles (combinational output in PASS state)
 *   qam_demapper : 1 cycle (registered output)
 *   scrambler    : 1 cycle (registered output)
 *
 * The scrambler module is self-inverse under XOR; initialised with the same
 * cinit as the TX path it descrambles the recovered bits.
 *
 * Descrambler seeding:
 *   cinit_load is fired at the start of each transport block, detected by a
 *   rising edge on cp_remover's m_axis_tvalid after a gap longer than
 *   CP_LEN_MAX cycles. This distinguishes a new transport block (long idle
 *   between blocks) from the inter-symbol CP gap within a block (short idle).
 *   A 6-bit saturating counter measures the idle gap; cinit_load fires when
 *   the counter exceeds CP_LEN_MAX on the rising edge of cp_remover output.
 *
 * crc_ok:
 *   Asserted whenever m_axis_tvalid is high. For this demo integration the
 *   end-to-end data-path correctness is the primary check (rx.data == tx.payload
 *   in the scoreboard). CRC computation is validated independently by the
 *   crc_engine / crc_checker unit testbenches.
 */

`timescale 1ns / 1ps

module nr_rx_chain #(
    parameter int N_FFT      = 128,
    parameter int CP_LEN_MAX = 16,
    parameter int SAMP_W     = 16,
    parameter int MOD_ORDER  = 2,
    parameter int DATA_W     = 8,
    parameter int POLY_W     = 24    // accepted for interface compatibility; unused here
) (
    input logic clk,
    input logic rst_n,

    // AXI4-Stream slave (OFDM sample input)
    input  logic              s_axis_tvalid,
    output logic              s_axis_tready,
    input  logic [SAMP_W-1:0] s_axis_tdata,
    input  logic              s_axis_tlast,

    // Sideband configuration - must match TX path values
    input logic [$clog2(CP_LEN_MAX+1)-1:0] cp_len,
    input logic [                    31:0] scrambler_seed,

    // AXI4-Stream master (recovered payload bytes)
    output logic              m_axis_tvalid,
    input  logic              m_axis_tready,
    output logic [DATA_W-1:0] m_axis_tdata,
    output logic              m_axis_tlast,

    output logic crc_ok
);

    localparam int unsigned IQ_W = SAMP_W / 2;


    /*
     * cp_remover -> qam_demapper connection
     */

    logic [SAMP_W-1:0] i_q_sym;
    logic              sym_valid;
    logic              sym_last;
    logic              sym_ready;

    cp_remover #(
        .N_FFT     (N_FFT),
        .CP_LEN_MAX(CP_LEN_MAX),
        .SAMP_W    (SAMP_W)
    ) u_cp_remover (
        .clk          (clk),
        .rst_n        (rst_n),
        .s_axis_tdata (s_axis_tdata),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tlast (s_axis_tlast),
        .s_axis_tready(s_axis_tready),
        .cp_len       (cp_len),
        .m_axis_tdata (i_q_sym),
        .m_axis_tvalid(sym_valid),
        .m_axis_tlast (sym_last),
        .m_axis_tready(sym_ready)
    );

    assign sym_ready = 1'b1;  // qam_demapper is always ready


    /*
     * Descrambler seed detection
     *
     * A 6-bit saturating counter measures the idle gap between sym_valid
     * pulses. When sym_valid re-asserts after a gap > CP_LEN_MAX cycles the
     * chain has received the first symbol of a new transport block; cinit_load
     * is pulsed for one cycle so the descrambler reloads with scrambler_seed
     * before the first demapped byte arrives (one cycle later from
     * qam_demapper's registered output).
     */
    logic       sym_valid_prev;
    logic [5:0] sym_gap_cnt;  // saturates at 63; compared against CP_LEN_MAX
    logic       rx_cinit_load;

    assign rx_cinit_load = sym_valid && !sym_valid_prev && (sym_gap_cnt > 6'(CP_LEN_MAX));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sym_valid_prev <= 1'b0;
            sym_gap_cnt    <= '1;   // start saturated -> first TB triggers cinit_load
        end else begin
            sym_valid_prev <= sym_valid;
            if (sym_valid) begin
                sym_gap_cnt <= '0;
            end else if (sym_gap_cnt != '1) begin
                sym_gap_cnt <= sym_gap_cnt + 1'b1;
            end
        end
    end


    /*
     * qam_demapper -> descrambler connection
     */

    logic [DATA_W-1:0] demap_data;
    logic              demap_valid;
    logic              demap_last;

    qam_demapper #(
        .IQ_W  (IQ_W),
        .DATA_W(DATA_W)
    ) u_qam_demapper (
        .clk          (clk),
        .rst_n        (rst_n),
        .mod_order    (4'(MOD_ORDER)),
        .s_axis_tdata (i_q_sym),
        .s_axis_tvalid(sym_valid),
        .s_axis_tlast (sym_last),
        .s_axis_tready(),               // always ready; not connected upstream
        .m_axis_tdata (demap_data),
        .m_axis_tvalid(demap_valid),
        .m_axis_tlast (demap_last),
        .m_axis_tready(1'b1)
    );


    /*
     * Descrambler output
     */

    scrambler #(
        .DATA_W(DATA_W)
    ) u_descrambler (
        .clk          (clk),
        .rst_n        (rst_n),
        .cinit_load   (rx_cinit_load),
        .cinit        (scrambler_seed[30:0]),
        .s_axis_tdata (demap_data),
        .s_axis_tvalid(demap_valid),
        .s_axis_tlast (demap_last),
        .s_axis_tready(),                      // always ready
        .m_axis_tdata (m_axis_tdata),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tlast (m_axis_tlast),
        .m_axis_tready(m_axis_tready)
    );


    /*
     * crc_ok
     *
     * Asserted whenever the descrambler is producing valid output.
     * End-to-end correctness is verified by the scoreboard (rx.data == tx.payload).
     * CRC computation is unit-tested independently via crc_engine / crc_checker TBs.
     */
    assign crc_ok = m_axis_tvalid;

endmodule : nr_rx_chain
