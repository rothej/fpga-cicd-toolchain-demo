/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/crc_engine.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.212 S5.1
 *
 * Byte-serial CRC engine supporting all six NR CRC types defined in crc_pkg.
 * The CRC type is runtime-selectable via the crc_type port; polynomial and width
 * are resolved each cycle through crc_pkg accessor functions.
 *
 * Protocol:
 *   Assert init for one cycle before the first data_valid beat to clear the LFSR.
 *   Drive data_in + data_valid for each input byte. Assert last coincident with
 *   the final data_valid beat. crc_valid pulses for one cycle after last.
 *
 * Parameters CRC_WIDTH and POLY are accepted but unused internally; the module
 * resolves polynomial and width from crc_type via crc_pkg at runtime. These
 * parameters exist solely for Makefile -G flag compatibility.
 *
 * Auto-reset: the LFSR resets to zero when last fires, so back-to-back
 * transactions do not require an explicit init pulse between them.
 */

`timescale 1ns / 1ps

module crc_engine
    import crc_pkg::*;
#(
    // Accepted but unused - resolved at runtime via crc_type / crc_pkg.
    parameter int unsigned CRC_WIDTH = 24,
    parameter int unsigned POLY      = 24'h864CFB
) (
    input  logic            clk,
    input  logic            rst_n,
    input  logic            init,        // synchronous LFSR clear, start of new frame
    input  crc_type_e       crc_type,
    input  logic      [7:0] data_in,
    input  logic            data_valid,
    input  logic            last,        // asserted coincident with the final data_valid beat
    output crc_word_t       crc_out,
    output logic            crc_valid    // single-cycle pulse, registered
);

    /*
     * next_lfsr_bit - compute one-bit CRC LFSR step.
     *
     * The LFSR is right-justified and masked to the active CRC width. Feedback is
     * taken from bit [w-1] where w = get_crc_width(ctype). Note: the variable
     * bit-select on lfsr generates an N:1 mux in gate-level synthesis; this is
     * intentional and expected for a runtime-configurable CRC type.
     *
     * The generator polynomial stored in crc_pkg excludes the implicit leading x^N
     * term. Per TS 38.212 S5.1 the LFSR is initialized to all-zeros.
     */
    function automatic crc_word_t next_lfsr_bit(input crc_word_t lfsr, input logic bit_in,
                                                input crc_type_e ctype);
        int unsigned w;
        crc_word_t   poly;
        crc_word_t   mask;
        logic        feedback;

        w        = get_crc_width(ctype);
        poly     = get_crc_poly(ctype);
        mask     = get_crc_mask(ctype);
        feedback = bit_in ^ lfsr[w-1];

        if (feedback) begin
            return ((lfsr << 1) & mask) ^ poly;
        end else begin
            return (lfsr << 1) & mask;
        end
    endfunction : next_lfsr_bit


    /*
     * next_lfsr_byte - apply eight bit-serial steps, MSB of byte_in first.
     * Bit ordering matches 3GPP TS 38.212 S5.1.
     */
    function automatic crc_word_t next_lfsr_byte(input crc_word_t lfsr, input logic [7:0] byte_in,
                                                 input crc_type_e ctype);
        crc_word_t state;
        state = lfsr;

        for (int i = 7; i >= 0; i--) begin
            state = next_lfsr_bit(state, byte_in[i], ctype);
        end

        return state;
    endfunction : next_lfsr_byte


    // LFSR state register.
    crc_word_t lfsr;

    /*
     * Combinational next-state - computed once and shared between the LFSR
     * update and the crc_out capture to avoid calling next_lfsr_byte twice
     * in the clocked block.
     */
    crc_word_t lfsr_next;

    always_comb begin
        lfsr_next = next_lfsr_byte(lfsr, data_in, crc_type);
    end


    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr      <= '0;
            crc_out   <= '0;
            crc_valid <= 1'b0;
        end else begin
            crc_valid <= 1'b0;  // default: de-assert every cycle

            if (init) begin
                lfsr <= '0;
            end else if (data_valid) begin
                if (last) begin
                    crc_out   <= lfsr_next;
                    crc_valid <= 1'b1;
                    lfsr      <= '0;  // auto-reset: ready for next packet
                end else begin
                    lfsr <= lfsr_next;
                end
            end
        end
    end

endmodule : crc_engine
