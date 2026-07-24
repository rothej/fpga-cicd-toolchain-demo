/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/crc_checker.sv
 * Project : fpga-cicd-toolchain-demo
 *
 * Byte-serial CRC checker. Wraps crc_engine and compares its output against
 * a caller-supplied reference CRC word.
 *
 * Protocol:
 *   Same init, data_valid, last handshake as crc_engine.
 *   crc_ref must be valid coincident with the last && data_valid beat.
 *   crc_pass and crc_fail are mutually exclusive single-cycle pulses that fire
 *   one cycle after last.
 */

`timescale 1ns / 1ps

module crc_checker
    import crc_pkg::*;
(
    input  logic            clk,
    input  logic            rst_n,
    input  logic            init,
    input  crc_type_e       crc_type,
    input  logic      [7:0] data_in,
    input  logic            data_valid,
    input  logic            last,        // coincident with final data_valid beat
    input  crc_word_t       crc_ref,     // expected CRC; must be valid on last && data_valid
    output logic            crc_pass,    // single-cycle pulse, computed == expected
    output logic            crc_fail     // single-cycle pulse, computed != expected
);

    /*
     * CRC engine instance
     */
    crc_word_t engine_crc_out;
    logic      engine_crc_valid;

    crc_engine u_crc_engine (
        .clk       (clk),
        .rst_n     (rst_n),
        .init      (init),
        .crc_type  (crc_type),
        .data_in   (data_in),
        .data_valid(data_valid),
        .last      (last),
        .crc_out   (engine_crc_out),
        .crc_valid (engine_crc_valid)
    );

    /*
    * Reference capture and comparison
    *
    * crc_ref is registered on the last && data_valid beat so it is stable
    * exactly one cycle later when engine_crc_valid pulses. This avoids
    * requiring the caller to hold crc_ref for two cycles.
    */
    crc_word_t crc_ref_r;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            crc_ref_r <= '0;
            crc_pass  <= 1'b0;
            crc_fail  <= 1'b0;
        end else begin
            crc_pass <= 1'b0;  // default: de-assert every cycle
            crc_fail <= 1'b0;

            // Capture reference coincident with the last data beat.
            if (data_valid && last) begin
                crc_ref_r <= crc_ref;
            end

            // Compare one cycle later when the engine has finished.
            if (engine_crc_valid) begin
                if (engine_crc_out == crc_ref_r) begin
                    crc_pass <= 1'b1;
                end else begin
                    crc_fail <= 1'b1;
                end
            end
        end
    end

endmodule : crc_checker
