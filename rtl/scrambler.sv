/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/scrambler.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.211 S7.3.1.1
 *
 * Byte-serial Gold-code scrambler / descrambler.
 * Self-inverse: applying with the same cinit to scrambled data recovers
 * the original bytes, making this module suitable for both TX and RX paths.
 *
 * Gold sequence generators:
 *   x1[n+31] = x1[n+3]  ^ x1[n]
 *   x2[n+31] = x2[n+3]  ^ x2[n+2] ^ x2[n+1] ^ x2[n]
 *   c[n]     = x1[n] ^ x2[n]
 *
 * Eight bits of the Gold sequence are consumed per clock cycle so one byte
 * of scrambled output is produced per s_axis_tvalid beat. The output is
 * registered; m_axis_tvalid is asserted one cycle after s_axis_tvalid.
 *
 * Note: TS 38.211 requires Nc = 1600 warm-up steps before the sequence is
 * used. This implementation initialises the LFSRs directly from cinit for
 * demo simplicity. Both TX and RX paths must use the same cinit.
 *
 * Protocol:
 *   Assert cinit_load for one cycle to reload both LFSRs before the first
 *   s_axis_tvalid beat. Output arrives one cycle after each input beat.
 *   m_axis_tready is accepted on the port for interface compliance; the
 *   module always asserts s_axis_tready (unit-latency, no buffering required).
 */

`timescale 1ns / 1ps

module scrambler #(
    parameter int unsigned DATA_W = 8
) (
    input  logic              clk,
    input  logic              rst_n,
    input  logic              cinit_load,     // synchronous LFSR reload; sample cinit
    input  logic [      30:0] cinit,          // x2 seed (TS 38.211 S7.3.1.1)
    input  logic [DATA_W-1:0] s_axis_tdata,
    input  logic              s_axis_tvalid,
    input  logic              s_axis_tlast,
    output logic              s_axis_tready,
    output logic [DATA_W-1:0] m_axis_tdata,
    output logic              m_axis_tvalid,
    output logic              m_axis_tlast,
    input  logic              m_axis_tready
);

    // x1 fixed initial state: x1[0]=1, x1[1..30]=0 (TS 38.211 S7.3.1.1)
    localparam logic [30:0] X1_INIT = 31'h0000_0001;

    /*
     * LFSR state convention
     *
     * sr[0] is the oldest bit and is the next output. Each step:
     *   new_bit = feedback(sr)
     *   sr      = {new_bit, sr[30:1]}
     *
     * get_x1_byte / get_x2_byte  - return 8 Gold bits, bit[7] = first out
     * next_x1_state / next_x2_state - LFSR state after consuming 8 bits
     */

    function automatic logic [7:0] get_x1_byte(input logic [30:0] sr);
        logic [30:0] s;
        logic [ 7:0] bits;
        logic        nb;
        s = sr;
        for (int i = 7; i >= 0; i--) begin
            bits[i] = s[0];
            nb      = s[3] ^ s[0];
            s       = {nb, s[30:1]};
        end
        return bits;
    endfunction : get_x1_byte

    function automatic logic [30:0] next_x1_state(input logic [30:0] sr);
        logic [30:0] s;
        logic        nb;
        s = sr;
        for (int i = 0; i < 8; i++) begin
            nb = s[3] ^ s[0];
            s  = {nb, s[30:1]};
        end
        return s;
    endfunction : next_x1_state

    function automatic logic [7:0] get_x2_byte(input logic [30:0] sr);
        logic [30:0] s;
        logic [ 7:0] bits;
        logic        nb;
        s = sr;
        for (int i = 7; i >= 0; i--) begin
            bits[i] = s[0];
            nb      = s[3] ^ s[2] ^ s[1] ^ s[0];
            s       = {nb, s[30:1]};
        end
        return bits;
    endfunction : get_x2_byte

    function automatic logic [30:0] next_x2_state(input logic [30:0] sr);
        logic [30:0] s;
        logic        nb;
        s = sr;
        for (int i = 0; i < 8; i++) begin
            nb = s[3] ^ s[2] ^ s[1] ^ s[0];
            s  = {nb, s[30:1]};
        end
        return s;
    endfunction : next_x2_state


    logic [30:0] x1, x2;

    // Combinational Gold byte for the current LFSR state.
    logic [7:0] gold_byte;

    always_comb begin
        gold_byte = get_x1_byte(x1) ^ get_x2_byte(x2);
    end

    // Always ready: unit-latency, no input buffering needed.
    assign s_axis_tready = 1'b1;


    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x1            <= X1_INIT;
            x2            <= '0;
            m_axis_tdata  <= '0;
            m_axis_tvalid <= 1'b0;
            m_axis_tlast  <= 1'b0;
        end else begin
            m_axis_tvalid <= 1'b0;  // default: de-assert every cycle
            m_axis_tlast  <= 1'b0;

            if (cinit_load) begin
                x1 <= X1_INIT;
                x2 <= cinit;
            end else if (s_axis_tvalid) begin
                m_axis_tdata  <= s_axis_tdata ^ DATA_W'(gold_byte);
                m_axis_tvalid <= 1'b1;
                m_axis_tlast  <= s_axis_tlast;
                x1            <= next_x1_state(x1);
                x2            <= next_x2_state(x2);
            end
        end
    end

endmodule : scrambler
