// rtl/counter.sv
// Parameterized synchronous up-counter with overflow detection.
module counter #(
    parameter int unsigned WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,    // Active-low synchronous reset.
    input  logic             en,
    output logic [WIDTH-1:0] count,
    output logic             overflow
);

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            count    <= '0;
            overflow <= 1'b0;
        end else if (en) begin
            overflow <= &count; // Pulses high one cycle before wrapping.
            count    <= count + 1'b1;
        end else begin
            overflow <= 1'b0;
        end
    end

endmodule : counter
