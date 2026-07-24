/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : sim/nr_chain/nr_chain_top.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : -
 *
 * Loopback simulation wrapper: nr_tx_chain -> nr_rx_chain.
 * Not synthesisable; used exclusively as the Verilator/cocotb simulation top.
 *
 * The lb_* ports expose the TX->RX boundary wires as top-level ports so the
 * cocotb loopback monitor can observe them without hierarchy traversal.
 * lb_tready is driven by u_rx (AXI4-S slave); lb_tvalid, lb_tdata, and
 * lb_tlast are driven by u_tx (AXI4-S master).
 */

`timescale 1ns / 1ps

module nr_chain_top #(
    parameter int N_FFT      = 64,
    parameter int CP_LEN_MAX = 16,
    parameter int SAMP_W     = 16,
    parameter int MOD_ORDER  = 2,   // bits per QAM symbol: 2=QPSK 4=16QAM 6=64QAM
    parameter int DATA_W     = 8,
    parameter int POLY_W     = 24   // CRC polynomial width in bits (e.g. 24 = CRC-24A)
) (
    input logic clk,
    input logic rst_n,

    // TX chain input
    input  logic              s_axis_tvalid,
    output logic              s_axis_tready,
    input  logic [DATA_W-1:0] s_axis_tdata,
    input  logic              s_axis_tlast,

    // Sideband configuration - stable for the duration of one transport block
    input logic [$clog2(CP_LEN_MAX+1)-1:0] cp_len,
    input logic [                    31:0] scrambler_seed,

    // TX->RX loopback observation
    output logic              lb_tvalid,
    output logic              lb_tready,
    output logic [SAMP_W-1:0] lb_tdata,
    output logic              lb_tlast,

    // RX chain output
    output logic              m_axis_tvalid,
    input  logic              m_axis_tready,
    output logic [DATA_W-1:0] m_axis_tdata,
    output logic              m_axis_tlast,
    output logic              crc_ok
);

    /*
     * Internal loopback wires at the TX->RX boundary.
     *
     * The _w suffix distinguishes the internal wire nets from the output ports of
     * the same name. The four assign statements route each wire to its corresponding
     * output port so the cocotb monitor sees them as top-level signals without
     * hierarchy traversal.
     *
     * Drive ownership:
     *   lb_tvalid_w / lb_tdata_w / lb_tlast_w - u_tx (AXI4-S master)
     *   lb_tready_w                           - u_rx (AXI4-S slave)
     */
    wire              lb_tvalid_w;
    wire              lb_tready_w;
    wire [SAMP_W-1:0] lb_tdata_w;
    wire              lb_tlast_w;

    assign lb_tvalid = lb_tvalid_w;
    assign lb_tready = lb_tready_w;
    assign lb_tdata  = lb_tdata_w;
    assign lb_tlast  = lb_tlast_w;


    nr_tx_chain #(
        .N_FFT     (N_FFT),
        .CP_LEN_MAX(CP_LEN_MAX),
        .SAMP_W    (SAMP_W),
        .MOD_ORDER (MOD_ORDER),
        .DATA_W    (DATA_W),
        .POLY_W    (POLY_W)
    ) u_tx (
        .clk           (clk),
        .rst_n         (rst_n),
        .s_axis_tvalid (s_axis_tvalid),
        .s_axis_tready (s_axis_tready),
        .s_axis_tdata  (s_axis_tdata),
        .s_axis_tlast  (s_axis_tlast),
        .cp_len        (cp_len),
        .scrambler_seed(scrambler_seed),
        .m_axis_tvalid (lb_tvalid_w),
        .m_axis_tready (lb_tready_w),
        .m_axis_tdata  (lb_tdata_w),
        .m_axis_tlast  (lb_tlast_w)
    );


    nr_rx_chain #(
        .N_FFT     (N_FFT),
        .CP_LEN_MAX(CP_LEN_MAX),
        .SAMP_W    (SAMP_W),
        .MOD_ORDER (MOD_ORDER),
        .DATA_W    (DATA_W),
        .POLY_W    (POLY_W)
    ) u_rx (
        .clk           (clk),
        .rst_n         (rst_n),
        .s_axis_tvalid (lb_tvalid_w),
        .s_axis_tready (lb_tready_w),
        .s_axis_tdata  (lb_tdata_w),
        .s_axis_tlast  (lb_tlast_w),
        .cp_len        (cp_len),
        .scrambler_seed(scrambler_seed),
        .m_axis_tvalid (m_axis_tvalid),
        .m_axis_tready (m_axis_tready),
        .m_axis_tdata  (m_axis_tdata),
        .m_axis_tlast  (m_axis_tlast),
        .crc_ok        (crc_ok)
    );

endmodule : nr_chain_top
