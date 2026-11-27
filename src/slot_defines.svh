`ifdef SLOT_1X1

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 6
`define NUM_DVSS_PADS 8

`define NUM_VDD_PADS 2
`define NUM_VSS_PADS 2

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 50
`define NUM_ANALOG_PADS 0

`define NUM_BIO_CORES 4
`define BIO_RAM_WIDTH 11

`endif

`ifdef SLOT_0P5X1

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 7
`define NUM_DVSS_PADS 7

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 50
`define NUM_ANALOG_PADS 0

`define NUM_BIO_CORES 3
`define BIO_RAM_WIDTH 11

`endif

`ifdef SLOT_1X0P5

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 7
`define NUM_DVSS_PADS 7

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 4
`define NUM_BIDIR_PADS 50
`define NUM_ANALOG_PADS 0

`define NUM_BIO_CORES 3
`define BIO_RAM_WIDTH 11

`endif

`ifdef SLOT_0P5X0P5

// Power/ground pads for core and I/O
`define NUM_DVDD_PADS 3
`define NUM_DVSS_PADS 3

`define NUM_VDD_PADS 1
`define NUM_VSS_PADS 1

// Signal pads
`define NUM_INPUT_PADS 1
`define NUM_BIDIR_PADS 45
`define NUM_ANALOG_PADS 0

`define NUM_BIO_CORES 1
`define BIO_RAM_WIDTH 10

`endif
