# TinyQV with Femto BIO for Wafer Space

This is a version of TinyQV with 4 BIO cores for Wafer Space.

TinyQV is an RV32EC SoC.  It executes instructions directly from a QSPI flash (e.g. WS25Q128JVSIQ), and uses one or two QSPI APS6404 PSRAMs for RAM.

Femto BIO is a successor to [Baochip's BIO](https://baochip.github.io/baochip-1x/ch02-00-bio-overview.html), switching to a simpler RISC-V core based on [FemtoRV](https://github.com/BrunoLevy/learn-fpga/tree/master/FemtoRV).  The design goal of this is predictable performance of 2 clocks per instruction (except branches), which is roughly twice as fast (per clock) as Baochip BIO.

It also includes:

* UART, [SPI](https://github.com/TinyTapeout/ttsky25a-tinyQV/blob/main/docs/user_peripherals/30_spi.md) and [PWM](https://github.com/TinyTapeout/ttsky25a-tinyQV/blob/main/docs/user_peripherals/21_matt_pwm.md) peripherals
* USB CDC (to document).

The design is intended to run at 3v3 at 48MHz.

## TODO

* Add programming interface as on previous TQVs
* Add old style SPI on non-quarter slot
* Document USB CDC (and add docs to TQVE too!)

Testing!!

## Pinout

| Pin      | Function |
| -------  | -------- |
| CLK      | Clock (48MHz) |
| RST_N    | Reset (active low) |
| Input[0] | UART RX |
| Input[1] | Flash programming mode (active low, pulled up) |
| Bidir[0] | QSPI Flash CS |
| Bidir[1] | QSPI D0 / MOSI |
| Bidir[2] | QSPI D1 / MISO |
| Bidir[3] | QSPI SCK |
| Bidir[4] | QSPI D2 |
| Bidir[5] | QSPI D3 |
| Bidir[6] | QSPI RAM A CS |
| Bidir[7] | QSPI RAM B CS / Audio |
| Bidir[39:8] | GPIO 31-0 |
| Bidir[40] | UART TX |
| Bidir[41] | UART RTS |
| Bidir[42] | Debug UART TX |
| Bidir[43] | Flash programming MISO |
| Input[2]  | Flash programming MOSI |
| Input[3]  | Flash programming CS |
| Prog_CLK  | Flash programming SCK |

## Address map

| Address range | Device |
| ------------- | ------ |
| 0x0000000 - 0x0FFFFFF | Flash |
| 0x1000000 - 0x17FFFFF | RAM A |
| 0x1800000 - 0x1FFFFFF | RAM B |
| 0x8000000 - 0x8000033 | DEBUG  |
| 0x8000040 - 0x800007F | GPIO |
| 0x8000080 - 0x80000BF | UART  |
| 0x80000C0 - 0x80001FF | User peripherals 3-7 |
| 0x8000400 - 0x800043F | Simple user peripherals 0-3 |
| 0x9000000 - 0x90000FF | Femto BIO config |
| 0x9008000 - 0x90080FF | Femto BIO core 0 config |
| 0x9009000 - 0x90097FF | Femto BIO core 0 memory |
| 0x9008000 - 0x90080FF | Femto BIO core 1 config |
| 0x9009000 - 0x90097FF | Femto BIO core 1 memory |
| 0x9008000 - 0x90080FF | Femto BIO core 2 config |
| 0x9009000 - 0x90097FF | Femto BIO core 2 memory |
| 0x9008000 - 0x90080FF | Femto BIO core 3 config |
| 0x9009000 - 0x90097FF | Femto BIO core 3 memory |
| 0xFFFFC00 - 0xFFFFDFF | Scratch RAM |
| 0xFFFFF00 - 0xFFFFF07 | TIME |

### DEBUG

| Register | Address | Description |
| -------- | ------- | ----------- |
| ID       | 0x8000008 (R) | Instance of TinyQV: "WS02" |
| DEBUG_UART_DATA | 0x8000018 (W) | Transmits the byte on the debug UART |
| STATUS   | 0x800001C (R) | Bit 0 indicates whether the debug UART TX is busy, bytes should not be written to the data register while this bit is set. |

### BIO config

| Register | Address | Description |
| -------- | ------- | ----------- |
| BIO_SEL  | 0x8000034 (RW) | BIO control of each GPIO 31-0 |
| CTRL     | 0x9000000 (RW) | Bits 3-0 enable BIO cores.  Core is reset when bit is 0. |
| CONFIG   | 0x9000004 (R)  | BIO configuration 31-16: RAM size, 15-8: Num cores, 7-0: Version (128). |
| FLEVEL   | 0x900000C (R)  | FIFO levels in 15-12, 11-8, 7-4, 3-0 for FIFOS 3-0. |
| FIFO_TX0 | 0x9000010 (W)  | Write (push) FIFO 0 |
| FIFO_TX1 | 0x9000014 (W)  | Write (push) FIFO 1 |
| FIFO_TX2 | 0x9000018 (W)  | Write (push) FIFO 2 |
| FIFO_TX3 | 0x900001C (W)  | Write (push) FIFO 3 |
| FIFO_RX0 | 0x9000020 (R)  | Read (pop) FIFO 0 |
| FIFO_RX1 | 0x9000024 (R)  | Read (pop) FIFO 1 |
| FIFO_RX2 | 0x9000028 (R)  | Read (pop) FIFO 2 |
| FIFO_RX3 | 0x900002C (R)  | Read (pop) FIFO 3 |
| EVENT_SET| 0x9000038 (W)  | 1 bits set the corresponding event bit (23-0). |
| EVENT_CLR| 0x900003C (W)  | 1 bits clear the corresponding event bit (23-0). |
| EVENT_STATUS | 0x9000040 (R) | Read event status |

Event status bits 31-24 are not configurable as in Baochip BIO, they flag FIFO full (31, 29, 27, 25) and empty (30, 28, 26, 24) for each FIFO.

### TIME

| Register | Address | Description |
| -------- | ------- | ----------- |
| MTIME_DIVIDER | 0x800002C | MTIME counts at clock / (MTIME_DIVIDER + 1).  Bits 0 and 1 are fixed at 1, so multiples of 4MHz are supported. |
| MTIME    | 0xFFFFF00 (RW) | Get/set the 1MHz time count |
| MTIMECMP | 0xFFFFF04 (RW) | Get/set the time to trigger the timer interrupt |

This is a simple timer which follows the spirit of the Risc-V timer but using a 32-bit counter instead of 64 to save area.
In this version the MTIME register is updated at 1/64th of the clock frequency (nominally 1MHz), and MTIMECMP is used to trigger an interrupt.
If MTIME is after MTIMECMP (by less than 2^30 microseconds to deal with wrap), the timer interrupt is asserted.

### GPIO

| Register | Address | Description |
| -------- | ------- | ----------- |
| OUT | 0x8000040 (RW) | Control for GPIO 16-0 if the GPIO peripheral is selected |
| IN  | 0x8000044 (R) | Reads the current state of GPIO 16-0 |
| OE  | 0x8000048 (RW) | Output enable for GPIO 16-0. Default on for GPIO 16 and 7-0. |
| PULL_UP | 0x800004c (RW) | Pull up for GPIO 16-0. |
| PULL_DOWN | 0x8000050 (RW) | Pull down for GPIO 16-0. |

### UART

| Register | Address | Description |
| -------- | ------- | ----------- |
| TX_DATA | 0x8000080 (W) | Transmits the byte on the UART |
| RX_DATA | 0x8000080 (R) | Reads any received byte |
| TX_BUSY | 0x8000084 (R) | Bit 0 indicates whether the UART TX is busy, bytes should not be written to the data register while this bit is set. Bit 1 indicates whether a received byte is available to be read. |
| DIVIDER | 0x8000088 (R/W) | 13 bit clock divider to set the UART baud rate |
| RX_SELECT | 0x800008C (R/W) | Selects UART RX pin, default 2 (dedicated RX) |

| UART RX Select | Pin |
| -------------- | --- |
| 0 | `ui_in[7]` |
| 1 | `ui_in[3]` |
| 2-3 | `uart_rx` (default, dedicated pin) |

# gf180mcu Project Template

Project template for wafer.space MPW runs using the gf180mcu PDK.

## Dependencies

Too manage all dependencies, the project template includes a Nix shell with all the required tools.
Install Nix and LibreLane by following the Nix-based installation instructions: https://librelane.readthedocs.io/en/latest/installation/nix_installation/index.html
To activate the shell, simply run `nix-shell` in the root directory of this repository. The subsequent steps assume that you are in the Nix shell of the project template.

## Prerequisites

The project template uses the open-pdks gf180mcuD variant of the PDK.
To clone the latest compatible PDK version via [Ciel](https://github.com/fossi-foundation/ciel), run `make clone-pdk`.

## Implement the Design

With the Nix shell enabled, run the implementation:

```
make librelane
```

You can find all output artifacts in the `librelane/runs/<timestamp>/` directory.

## View the Design

After completion, you can view the design using the OpenROAD GUI:

```
make librelane-openroad
```

Or using KLayout:

```
make librelane-klayout
```

## Verification and Simulation

For the verification of the chip we use [cocotb](https://www.cocotb.org/). Cocotb is a Python-based testbench environment. The simulator that is used by the project template is [Icarus Verilog](https://github.com/steveicarus/iverilog).

The testbench is located in `cocotb/chip_top_tb.py`. To run the RTL simulation, run the following command:

```
make sim
```

To run the GL (gate-level) simulation, run the following command:

```
make sim-gl
```

> [!NOTE]
> You need to have the latest implementation of your design in the `final/` folder. After a run has completed without errors, the final views will be copied to `final/`.

In both cases, a waveform file will be generated under `cocotb/sim_build/chip_top.fst`.
You can view it using a waveform viewer, for example, [GTKWave](https://gtkwave.github.io/gtkwave/).

```
make sim-view
```

You can now update the testbench according to your design.

## Implementing Your Own Design

The source files for this template can be found in the `src/` directory. `chip_top.sv` defines the top-level ports and instantiates `chip_core`, the chip ID (QR code), the marker, and the wafer.space logo. To comply with the default bonding setup, do not change the number of pads in order to keep the original bondpad positions. To ensure compatibility with the default breakout PCB, do not change any of the power or ground pads. However, you can change the type of the signal pads, e.g. to bidirectional, input-only, or analog pads. The template provides the `NUM_INPUT_PADS`, `NUM_BIDIR_PADS`, and `NUM_ANALOG_PADS` parameters for this purpose.

The actual pad positions are defined in the LibreLane configuration file under `librelane/slots/<slot>.yaml`. The variables `PAD_SOUTH`/`PAD_EAST`/`PAD_NORTH`/`PAD_WEST` determine the respective pad placement. The LibreLane configuration also allows you to customize the flow (enable or disable steps), specify the source files, set various variables for the steps, and instantiate macros. For more information about the configuration, please refer to the LibreLane documentation: https://librelane.readthedocs.io/en/latest/

To implement your own design, simply edit `chip_core.sv`. The `chip_core` module receives the clock and reset, as well as the signals from the pads defined in `chip_top`. As an example, a 42-bit wide counter is implemented.

> [!NOTE]
> For more comprehensive SystemVerilog support, enable the `USE_SLANG` variable in the LibreLane configuration.

## Choosing a Different Slot Size

The template supports the following slot sizes: `1x1`, `0p5x1`, `1x0p5`, `0p5x0p5`.
By default, the design is implemented using the `1x1` slot definition.

To select a different slot size, simply set the `SLOT` environment variable.
This can be done when invoking a make target:

```
SLOT=0p5x0p5 make librelane
```

Alternatively, you can export the slot size:

```
export SLOT=0p5x0p5
```

You can change the slot that is selected by default in the Makefile by editing the value of `DEFAULT_SLOT`.

## Selecting Different IP Libraries

The project template has support for selecting libraries with the `SCL`, `PAD`, and `SRAM` environment variables. For possible values, see the sections below.

For example, to build the 0p5x0p5 chip with 3v3 libraries:

```
SLOT=0p5x0p5 SCL=gf180mcu_as_sc_mcu7t3v3 PAD=gf180mcu_ocd_io SRAM=gf180mcu_ocd_ip_sram make librelane
```

The default values can be changed in the Makefile.

> [!NOTE]
> Not all of the community-created IPs have been tested yet, so support for them is experimental!
> wafer.space is not responsible for any IP that you use on your chip.

### SCL - Standard Cell Libraries

| IP                       | Provider  | Voltage    | Status           | Notes                    |
|--------------------------|-----------|------------|------------------|--------------------------|
| gf180mcu_fd_sc_mcu7t5v0  | foundry   | 5V or 3.3V | silicon-verified | slow option, dense layout |
| gf180mcu_fd_sc_mcu9t5v0  | foundry   | 5V or 3.3V | silicon-verified | faster than 7t variant, uses more area |
| gf180mcu_as_sc_mcu7t3v3  | community | 3.3V       | simulation-only  | fastest available option |
| gf180mcu_ocd_sc_rt12t3v3 | community | 3.3V       | simulation-only  | radiation-tolerant       |

### PAD - I/O Pad Libraries

| IP                       | Provider  | Voltage    | Status           | Notes                    |
|--------------------------|-----------|------------|------------------|--------------------------|
| gf180mcu_fd_io           | foundry   | 5V or 3.3V | silicon-verified | connects IO and core power domains together |
| gf180mcu_ocd_io          | community | 5V or 3.3V | silicon-verified | keeps IO and core power domains separate, e.g. IO at 5V and core at 3.3V (DVDD >= VDD) |

### SRAM - SRAM Libraries

| IP                       | Provider  | Voltage    | Status           | Notes                    |
|--------------------------|-----------|------------|------------------|--------------------------|
| gf180mcu_fd_ip_sram      | foundry   | 5V or 3.3V | silicon-verified | 128, 256 and 512 bytes   |
| gf180mcu_ocd_ip_sram     | community | 3.3V       | partially silicon-verified | smaller area, 64, 128, 256, 512 and 1024 bytes |

## Building a Standalone Padring for Analog Design

To build just the padring without any standard cell rows, digital routing or filler cells, run the following command:

```
make librelane-padring
```

It is also possible to build the padring for other slot sizes:

```
SLOT=0p5x0p5 make librelane-padring
```

## Precheck

To check whether your design is suitable for manufacturing, run the [gf180mcu-precheck](https://github.com/wafer-space/gf180mcu-precheck) with your layout.
