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
 * Output masking:
 *   qam_demapper outputs {(DATA_W-MOD_ORDER)'b0, recovered_bits}.  When the
 *   descrambler XORs its full DATA_W-bit Gold byte against this, the upper
 *   (DATA_W-MOD_ORDER) bits of the output equal gold[DATA_W-1:MOD_ORDER]
 *   instead of the original payload bits (which were discarded by the mapper).
 *   m_axis_tdata is therefore masked to MOD_ORDER bits before leaving the
 *   module.  Sequences must generate payloads limited to MOD_ORDER bits so
 *   that the scoreboard comparison (rx.data == tx.payload) is well-defined.
 *
 * Sideband timing:
 *   cp_remover latches cp_len only while s_axis_tvalid is low, so cp_len must be
 *   presented at least one cycle before the first beat of a block. cp_len and
 *   scrambler_seed must match the TX values and stay stable until the block's
 *   m_axis_tlast. Only scrambler_seed[30:0] is used (bit 31 is ignored).
 *
 * Descrambler seeding:
 *   cinit_load fires on the cp_remover output beat carrying the TX block-start
 *   tag (sym_tuser). nr_tx_chain tags byte 0 of each transport block; the tag
 *   rides through scrambler -> qam_mapper -> cp_inserter -> cp_remover and is
 *   never asserted in the CP region. Intra-block symbol boundaries carry no tag,
 *   so the descrambler LFSR runs on across them.
 */

`timescale 1ns / 1ps

module nr_rx_chain #(
    parameter int N_FFT      = 128,
    parameter int CP_LEN_MAX = 16,
    parameter int SAMP_W     = 16,
    parameter int MOD_ORDER  = 2,
    parameter int DATA_W     = 8
) (
    input logic clk,
    input logic rst_n,

    // AXI4-Stream slave (OFDM sample input)
    input  logic              s_axis_tvalid,
    output logic              s_axis_tready,
    input  logic [SAMP_W-1:0] s_axis_tdata,
    input  logic              s_axis_tlast,
    input  logic              s_axis_tuser,

    // Sideband configuration - must match TX path values
    input logic [$clog2(CP_LEN_MAX+1)-1:0] cp_len,
    input logic [                    31:0] scrambler_seed,

    // AXI4-Stream master (recovered payload bytes)
    output logic              m_axis_tvalid,
    input  logic              m_axis_tready,
    output logic [DATA_W-1:0] m_axis_tdata,
    output logic              m_axis_tlast
);

    localparam int unsigned IQ_W = SAMP_W / 2;

    // Mask for the active payload bits.  The upper (DATA_W - MOD_ORDER) bits
    // of the descrambler output are Gold-sequence artefacts and are zeroed here.
    localparam logic [DATA_W-1:0] MOD_MASK = DATA_W'((1 << MOD_ORDER) - 1);


    /*
     * cp_remover -> qam_demapper connection
     */

    logic [SAMP_W-1:0] i_q_sym;
    logic              sym_valid;
    logic              sym_last;
    logic              sym_ready;
    logic              sym_tuser;

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
        .s_axis_tuser (s_axis_tuser),
        .s_axis_tready(s_axis_tready),
        .cp_len       (cp_len),
        .m_axis_tdata (i_q_sym),
        .m_axis_tvalid(sym_valid),
        .m_axis_tlast (sym_last),
        .m_axis_tuser (sym_tuser),
        .m_axis_tready(sym_ready)
    );

    assign sym_ready = 1'b1;  // qam_demapper is always ready


    /*
     * Descrambler seed detection
     *
     * sym_tuser is the block-start tag from nr_tx_chain, carried through cp_remover.
     * rx_cinit_load fires the same cycle cp_remover emits the tagged sample - one
     * cycle before qam_demapper's registered output (the descrambler input) presents
     * it, matching the cinit-before-data convention of nr_tx_chain's tx_cinit_load.
     */
    logic rx_cinit_load;
    assign rx_cinit_load = sym_valid && sym_tuser;


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
        .s_axis_tuser (sym_tuser),
        .s_axis_tready(),
        .m_axis_tdata (demap_data),
        .m_axis_tvalid(demap_valid),
        .m_axis_tlast (demap_last),
        .m_axis_tuser (),
        .m_axis_tready(1'b1)
    );


    /*
     * Descrambler output
     *
     * descr_tdata carries the raw XOR output, which has Gold-sequence bits in
     * positions [DATA_W-1:MOD_ORDER].  Those bits are masked before m_axis_tdata.
     */
    logic [DATA_W-1:0] descr_tdata;

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
        .m_axis_tdata (descr_tdata),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tlast (m_axis_tlast),
        .m_axis_tready(m_axis_tready)
    );

    // Discard Gold-sequence artefacts in the upper (DATA_W - MOD_ORDER) bits.
    // The qam_demapper zero-pads those bits; after XOR they equal gold[DATA_W-1:MOD_ORDER].
    assign m_axis_tdata = descr_tdata & MOD_MASK;

endmodule : nr_rx_chain
