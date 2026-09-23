/*************************************************************************************************
 * Copyright 2026 Joshua Rothe
 * All Rights Reserved Worldwide
 *
 * Licensed under the MIT License (MIT)
 *************************************************************************************************/
/*
 * File    : rtl/crc_pkg.sv
 * Project : fpga-cicd-toolchain-demo
 * Spec    : 3GPP TS 38.212 S5.1
 *
 * Defines the CRC type enumeration, generator polynomial constants, and accessor functions
 * used by crc_engine.sv, crc_checker.sv, and the nr_chain integration testbench.
 */

package crc_pkg;

    /*
     * crc_type_e, TS 38.212 S5.1
     * Encoding order follows the spec section ordering.
     */
    typedef enum logic [2:0] {
        CRC24A = 3'b000,  // S5.1.1; transport block (DL/UL data channels)
        CRC24B = 3'b001,  // S5.1.2; code block segmentation
        CRC24C = 3'b010,  // S5.1.3; UL-SCH, LDPC base graph 1 (>3824 bits)
        CRC16  = 3'b011,  // S5.1.4; UCI on PUSCH
        CRC11  = 3'b100,  // S5.1.5; UCI on PUCCH formats 2/3/4
        CRC6   = 3'b101   // S5.1.6; UCI on PUCCH (payload <= 11 bits)
    } crc_type_e;

    // Total defined CRC types, used for coverage bin sizing in TBs.
    localparam int unsigned NUM_CRC_TYPES = 6;

    /*
     * Maximum CRC register width across all types. All shift registers in crc_engine are this
     * wide; narrower CRCs are right-justified and masked on output via get_crc_mask().
     */
    localparam int unsigned CRC_WIDTH_MAX = 24;

    typedef logic [CRC_WIDTH_MAX - 1 : 0] crc_word_t;


    // Returns the number of CRC parity bits for a given type.
    function automatic int unsigned get_crc_width(input crc_type_e crc_type);
        unique case (crc_type)
            CRC24A:  return 24;
            CRC24B:  return 24;
            CRC24C:  return 24;
            CRC16:   return 16;
            CRC11:   return 11;
            CRC6:    return 6;
            // verilator coverage_off
            default: return 0;
            // verilator coverage_on
        endcase
    endfunction : get_crc_width


    /*
     * Returns the generator polynomial for a given CRC type as a crc_word_t.
     *
     * Representation: bit [N-1] = coefficient of D^(N-1), bit [0] = D^0. The leading D^N term
     * is implicit. Polynomials narrower than CRC_WIDTH_MAX are zero-padded in the upper bits.
     *
     *   CRC24A : D^24+D^23+D^18+D^17+D^14+D^11+D^10+D^7+D^6+D^5+D^4+D^3+D+1
     *   CRC24B : D^24+D^23+D^6+D^5+D+1
     *   CRC24C : D^24+D^23+D^21+D^20+D^17+D^15+D^13+D^12+D^8+D^4+D^2+D+1
     *   CRC16  : D^16+D^12+D^5+1
     *   CRC11  : D^11+D^10+D^9+D^5+1
     *   CRC6   : D^6+D^5+1
     */
    function automatic crc_word_t get_crc_poly(input crc_type_e crc_type);
        unique case (crc_type)
            CRC24A:  return 24'h864CFB;
            CRC24B:  return 24'h800063;
            CRC24C:  return 24'hB2B117;
            CRC16:   return 24'h001021;
            CRC11:   return 24'h000621;
            CRC6:    return 24'h000021;
            // verilator coverage_off
            default: return 24'h000000;
            // verilator coverage_on
        endcase  // crc_type
    endfunction : get_crc_poly


    /*
     * Returns an N-bit wide all-ones mask for output trimming in crc_engine.
     *
     * The w == CRC_WIDTH_MAX branch is explicit to avoid a shift of N bits on an N-bit type,
     * which is undefined in several tools.
     *
     *   CRC24A/B/C -> 24'hFFFFFF
     *   CRC16      -> 24'h00FFFF
     *   CRC11      -> 24'h0007FF
     *   CRC6       -> 24'h00003F
     */
    function automatic crc_word_t get_crc_mask(input crc_type_e crc_type);
        int unsigned w;
        w = get_crc_width(crc_type);
        // verilator coverage_off
        if (w == 0) begin
            return '0;
        end
        // verilator coverage_on
        if (w == CRC_WIDTH_MAX) begin
            return '1;
        end
        return (crc_word_t'(1) << w) - crc_word_t'(1);
    endfunction : get_crc_mask

endpackage : crc_pkg
