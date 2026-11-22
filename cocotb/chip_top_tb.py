# SPDX-FileCopyrightText: © 2025 Project Template Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import random
import logging
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, Edge, RisingEdge, FallingEdge, ClockCycles
from cocotb_tools.runner import get_runner

from riscvmodel.insn import *

from riscvmodel.regnames import x0, x1, sp, gp, tp, a0, a1, a2, a3, a4
from riscvmodel import csrnames
from riscvmodel.variant import RV32E

sim = os.getenv("SIM", "icarus")
gl = os.getenv("GL", False)
pdk_root = os.getenv("PDK_ROOT", Path(__file__).resolve().parent / "../gf180mcu")
pdk = os.getenv("PDK", "gf180mcuD")
scl = os.getenv("SCL", "gf180mcu_as_sc_mcu7t3v3")
pad = os.getenv("PAD", "gf180mcu_ocd_io")
sram = os.getenv("SRAM", "gf180mcu_ocd_ip_sram")
slot = os.getenv("SLOT", "1x1")

hdl_toplevel = "tb_top"

if not os.path.exists("output"):
    os.mkdir("output")

async def set_defaults(dut):
    dut.uart_rx.value = 1
    dut.gpio_in.value = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
    dut.prog_n.value = 1


async def start_clock(clock):
    """Start the clock"""
    c = Clock(clock, 39.682, "ns")
    cocotb.start_soon(c.start())


async def reset(clk, reset, dut, active_low=True):
    """Reset dut"""
    await Timer(200, "ns")

    cocotb.log.info("Reset asserted...")

    reset.value = not active_low
    await Timer(200, "ns")

    dut.qspi_data.value = 1
    await Timer(800, "ns")
    await RisingEdge(clk)

    reset.value = active_low
    await FallingEdge(clk)

    dut.qspi_data.value = "ZZZZ"

    cocotb.log.info("Reset deasserted.")

async def start_up(dut):
    """Startup sequence"""
    await set_defaults(dut)
    await start_clock(dut.clk_PAD)
    await reset(dut.clk_PAD, dut.rst_n_PAD, dut)

    assert dut.bidir_PAD.value[6:0] == "1000011"

    await ClockCycles(dut.clk_PAD, 2)

    # Expect flash and RAM init
    await setup_flash(dut)
    await ClockCycles(dut.clk_PAD, 2)
    await setup_ram(dut, True)
    await ClockCycles(dut.clk_PAD, 2)
    await setup_ram(dut, False)
    await ClockCycles(dut.clk_PAD, 3)

    # Read starts at address 0
    await start_read(dut, 0)

def check_qspi_data_out(dut, val):
    assert dut.bidir_PAD.value[1] == (1 if val & 1 else 0)
    assert dut.bidir_PAD.value[2] == (1 if val & 2 else 0)
    assert dut.bidir_PAD.value[4] == (1 if val & 4 else 0)
    assert dut.bidir_PAD.value[5] == (1 if val & 8 else 0)

def get_qspi_data_out(dut):
    val = 0
    if dut.bidir_PAD.value[1] == 1: val |= 1
    if dut.bidir_PAD.value[2] == 1: val |= 2
    if dut.bidir_PAD.value[4] == 1: val |= 4
    if dut.bidir_PAD.value[5] == 1: val |= 8
    return val

def check_spi_data_out(dut, val):
    assert dut.bidir_PAD.value[1] == (1 if val & 1 else 0)
    assert dut.bidir_PAD.value[2] == 0 # Pulled down

def set_qspi_data(dut, val):
    dut.qspi_data.value = val

async def setup_flash(dut):
    assert dut.bidir_PAD.value[0] == 0
    assert dut.bidir_PAD.value[6] == 1
    assert dut.bidir_PAD.value[3] == 0

    # Reset
    cmd = 0xFF
    for i in range(8):
        check_spi_data_out(dut, (1 if cmd & 0x80 else 0))
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 1
        check_spi_data_out(dut, (1 if cmd & 0x80 else 0))
        cmd <<= 1
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == (0 if i < 7 else 1)
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 0

    for _ in range(2):
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 1
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 0

    await ClockCycles(dut.clk_PAD, 1, False)
    assert dut.bidir_PAD.value[0] == 0
    assert dut.bidir_PAD.value[6] == 1
    assert dut.bidir_PAD.value[3] == 0

    # Command
    cmd = 0xEB
    for i in range(8):
        check_spi_data_out(dut, (1 if cmd & 0x80 else 0))
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 1
        check_spi_data_out(dut, (1 if cmd & 0x80 else 0))
        cmd <<= 1
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 0

    # Address
    addr = 0
    for i in range(6):
        check_qspi_data_out(dut, (addr >> (20 - i * 4)) & 0xF)
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 1
        check_qspi_data_out(dut, (addr >> (20 - i * 4)) & 0xF)
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 0

    # Continuous read
    for i in range(2):
        check_qspi_data_out(dut, 0xA)
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 1
        check_qspi_data_out(dut, 0xA)
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 0

    for i in range(8):
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 1
        if i == 7:
            break
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 0
        assert dut.bidir_PAD.value[6] == 1
        assert dut.bidir_PAD.value[3] == 0

async def setup_ram(dut, ram_a):
    assert dut.bidir_PAD.value[0] == 1
    assert dut.bidir_PAD.value[6] == (0 if ram_a else 1)
    assert dut.bidir_PAD.value[7] == (1 if ram_a else 0)
    assert dut.bidir_PAD.value[3] == 0

    # Command
    cmd = 0x35
    for i in range(8):
        check_spi_data_out(dut, (1 if cmd & 0x80 else 0))
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 1
        assert dut.bidir_PAD.value[6] == (0 if ram_a else 1)
        assert dut.bidir_PAD.value[7] == (1 if ram_a else 0)
        assert dut.bidir_PAD.value[3] == 1
        check_spi_data_out(dut, (1 if cmd & 0x80 else 0))
        cmd <<= 1
        if i == 7:
            break
        await ClockCycles(dut.clk_PAD, 1, False)
        assert dut.bidir_PAD.value[0] == 1
        assert dut.bidir_PAD.value[6] == (0 if ram_a else 1)
        assert dut.bidir_PAD.value[7] == (1 if ram_a else 0)
        assert dut.bidir_PAD.value[3] == 0

select = None

def check_selected(dut):
    assert dut.bidir_PAD.value[0] == (0 if "FLASH" == select else 1)
    assert dut.bidir_PAD.value[6] == (0 if "RAM A" == select else 1)
    assert dut.bidir_PAD.value[7] == (0 if "RAM B" == select else 1)

def is_selected(dut):
    if "FLASH" == select: return dut.bidir_PAD.value[0] == 0
    if "RAM A" == select: return dut.bidir_PAD.value[6] == 0
    if "RAM B" == select: return dut.bidir_PAD.value[7] == 0
    return False

async def start_read(dut, addr, allow_interrupt=False):
    global select

    if addr is None:
        select = "FLASH"
    elif addr >= 0x1800000:
        select = "RAM B"
    elif addr >= 0x1000000:
        select = "RAM A"
    else:
        select = "FLASH"

    check_selected(dut)
    assert dut.bidir_PAD.value[3] == 0

    if select != "FLASH":
        # Command
        cmd = 0x0B
        for i in range(2):
            await ClockCycles(dut.clk_PAD, 1)
            check_selected(dut)
            assert dut.bidir_PAD.value[3] == 1
            check_qspi_data_out(dut, (cmd & 0xF0) >> 4)
            cmd <<= 4
            await ClockCycles(dut.clk_PAD, 1)
            check_selected(dut)
            assert dut.bidir_PAD.value[3] == 0

    # Address
    for i in range(6):
        await ClockCycles(dut.clk_PAD, 1)
        if allow_interrupt and not is_selected(dut): return False
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 1
        if addr is not None:
            check_qspi_data_out(dut, (addr >> (20 - i * 4)) & 0xF)
        await ClockCycles(dut.clk_PAD, 1)
        if allow_interrupt and not is_selected(dut): return False
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 0

    # Dummy
    if select == "FLASH":
        for i in range(2):
            await ClockCycles(dut.clk_PAD, 1)
            if allow_interrupt and not is_selected(dut): return False
            check_selected(dut)
            assert dut.bidir_PAD.value[3] == 1
            check_qspi_data_out(dut, 0xA)
            await ClockCycles(dut.clk_PAD, 1)
            if allow_interrupt and not is_selected(dut): return False
            check_selected(dut)
            assert dut.bidir_PAD.value[3] == 0

    for i in range(4):
        await ClockCycles(dut.clk_PAD, 1)
        if allow_interrupt and not is_selected(dut): return False
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 1
        await ClockCycles(dut.clk_PAD, 1)
        if allow_interrupt and not is_selected(dut): return False
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 0

    return True

async def start_write(dut, addr):
    global select

    if addr >= 0x1800000:
        select = "RAM B"
    else:
        select = "RAM A"

    check_selected(dut)
    assert dut.bidir_PAD.value[3] == 0
    dut.qspi_data.value = "ZZZZ"

    # Command
    cmd = 0x02
    for i in range(2):
        await ClockCycles(dut.clk_PAD, 1, False)
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 1
        check_qspi_data_out(dut, (cmd & 0xF0) >> 4)
        cmd <<= 4
        await ClockCycles(dut.clk_PAD, 1, False)
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 0

    # Address
    for i in range(6):
        await ClockCycles(dut.clk_PAD, 1, False)
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 1
        check_qspi_data_out(dut, (addr >> (20 - i * 4)) & 0xF)
        await ClockCycles(dut.clk_PAD, 1, False)
        check_selected(dut)
        assert dut.bidir_PAD.value[3] == 0

nibble_shift_order = [4, 0, 12, 8, 20, 16, 28, 24]

async def send_instr(dut, data, ok_to_exit=False, allow_long_delay=False):
    instr_len = 8 if (data & 3) == 3 else 4
    for i in range(instr_len):
        set_qspi_data(dut, (data >> (nibble_shift_order[i])) & 0xF)
        await ClockCycles(dut.clk_PAD, 1)
        for _ in range(400 if allow_long_delay else 20):
            if ok_to_exit and not is_selected(dut):
                return
            check_selected(dut)
            if dut.bidir_PAD.value[3] == 0:
                await ClockCycles(dut.clk_PAD, 1)
            else:
                break
        assert dut.bidir_PAD.value[3] == 1
        await ClockCycles(dut.clk_PAD, 1)
        assert dut.bidir_PAD.value[3] == 0
        if i != instr_len - 1:
            if ok_to_exit and not is_selected(dut):
                return
            check_selected(dut)

async def expect_store(dut, addr, bytes=4, allow_long_delay=False, allow_interrupt=False):
    global select

    val = 0
    for i in range(12):
        if addr >= 0x1800000:
            select = "RAM B"
        else:
            select = "RAM A"

        if is_selected(dut):
            await start_write(dut, addr)
            for j in range(bytes*2):
                await ClockCycles(dut.clk_PAD, 1, False)
                check_selected(dut)
                if j > 0 and (j % 8) == 0:
                    await ClockCycles(dut.clk_PAD, 1, False)
                    check_selected(dut)
                    assert dut.bidir_PAD.value[3] == 0
                    await ClockCycles(dut.clk_PAD, 1, False)
                assert dut.bidir_PAD.value[3] == 1
                val |= get_qspi_data_out(dut) << (nibble_shift_order[j % 8])
                await ClockCycles(dut.clk_PAD, 1, False)
                if j != bytes*2-1:
                    check_selected(dut)
                else:
                    assert not is_selected(dut)
                assert dut.bidir_PAD.value[3] == 0
            await ClockCycles(dut.clk_PAD, 1, False)
            assert not is_selected(dut)
            break
        elif dut.bidir_PAD.value[0] == 0:
            select = "FLASH"
            await send_instr(dut, 0x0001, True, allow_long_delay)
        else:
            await ClockCycles(dut.clk_PAD, 1, False)
    else:
        assert False

    for i in range(8):
        await ClockCycles(dut.clk_PAD, 1)
        if dut.bidir_PAD.value[0] == 0:
            if hasattr(dut.uut, "tt"):
                interrupted = not await start_read(dut, dut.uut.tt.i_tinyqv.instr_addr.value.to_unsigned() * 2, allow_interrupt)
            else:
                interrupted = not await start_read(dut, None, allow_interrupt)
            if interrupted:
                allow_interrupt = False
            else:
                break
    else:
        assert False

    return val

async def read_reg(dut, reg, allow_long_delay=False):
    offset = random.randint(-0x400, 0x3FF)
    instr = InstructionSW(gp, reg, offset).encode()
    await send_instr(dut, instr)

    return await expect_store(dut, 0x1000400 + offset, 4, allow_long_delay)

send_nops = True
nop_task = None

async def nops_loop(dut):
    while send_nops:
        await send_instr(dut, InstructionADDI(x0, x0, 0).encode())

async def start_nops(dut):
    global send_nops, nop_task
    send_nops = True
    nop_task = cocotb.start_soon(nops_loop(dut))

    # This ensures that the nop task is actually started, so that it can be instantly stopped.
    await Timer(2, "ps")

async def stop_nops():
    global send_nops, nop_task
    send_nops = False
    if nop_task is not None:
        await nop_task
    nop_task = None

async def load_val(dut, reg, val):
    value_upper = (val + 0x800) >> 12
    value_lower = val & 0xfff
    if value_lower >= 0x800:
        value_lower -= 0x1000

    await send_instr(dut, InstructionLUI(reg, value_upper).encode())
    await send_instr(dut, InstructionADDI(reg, reg, value_lower).encode())

@cocotb.test()
async def test_start(dut):
    """Run a simple GPIO test"""

    # Create a logger for this testbench
    logger = logging.getLogger("my_testbench")

    logger.info("Startup sequence...")

    # Start up
    await start_up(dut)

    logger.info("Running the GPIO test...")

    # Read ID
    await send_instr(dut, InstructionLW(x1, tp, 0x8).encode())
    assert await read_reg(dut, x1) == ord('3') | (ord('_') << 8) | (ord('S') << 16) | (ord('W') << 24)

    # Set up GPIO
    await send_instr(dut, InstructionADDI(x1, x0, -1).encode())
    await send_instr(dut, InstructionSW(tp, x1, 0x48).encode())
    await send_instr(dut, InstructionADDI(x1, x0, 1).encode())
    for j in range(6):
        await send_instr(dut, InstructionSB(tp, x1, 0x60 + j).encode())

    dut.uart_rx.value = "Z"

    for i in range(40):
        gpio_out = random.randint(0, (1 << 32) - 1)
        await load_val(dut, x1, gpio_out)
        await send_instr(dut, InstructionSW(tp, x1, 0x40).encode())
        for _ in range(3):
            await send_instr(dut, InstructionADDI(x0, x0, 0).encode())
        for j in range(32):
            assert dut.bidir_PAD.value[j+8] == (1 if (gpio_out >> j) & 1 else 0)

    logger.info("Done!")


def chip_top_runner():

    proj_path = Path(__file__).resolve().parent

    sources = []
    defines = {f"SLOT_{slot.upper()}": True}
    includes = [proj_path / "../src/"]
    src_path = proj_path / "../src/"

    # Set the LibreLane PDK/SCL/PAD defines
    defines[f"PDK_{pdk.replace('-','_')}"] = True
    defines[f"SCL_{scl}"] = True
    defines[f"PAD_{pad}"] = True
    defines[f"SRAM_{sram}"] = True

    sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
    sources.append(Path(pdk_root) / pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v")
    sources.append(Path(pdk_root) / pdk / "libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v")

    if gl:
        # We use the powered netlist
        sources.append(proj_path / f"../final/pnl/chip_top.pnl.v")

        defines.update({"FUNCTIONAL": True, "USE_POWER_PINS": True})
    else:
        sources.append(src_path / "chip_top.sv")
        sources.append(src_path / "chip_core.sv")
        sources.append(src_path / "femto-bio/femto_bio_core.v")
        sources.append(src_path / "femto-bio/femto_bio_top.v")
        sources.append(src_path / "femto-bio/femto_quark_bi.v")
        sources.append(src_path / "femto-bio/femto_ram_mux.v")
        sources.append(src_path / "femto-bio/femto_ram.v")
        sources.append(src_path / "femto-bio/femto_reg_file.v")
        sources.append(src_path / "femto-bio/pio_divider.v")
        sources.append(src_path / "femto-bio/regfifo.v")
        sources.append(src_path / "tinyQV/cpu/tinyqv.v")
        sources.append(src_path / "tinyQV/cpu/alu.v")
        sources.append(src_path / "tinyQV/cpu/buffer.v")
        sources.append(src_path / "tinyQV/cpu/core.v")
        sources.append(src_path / "tinyQV/cpu/counter.v")
        sources.append(src_path / "tinyQV/cpu/cpu.v")
        sources.append(src_path / "tinyQV/cpu/decode.v")
        sources.append(src_path / "tinyQV/cpu/mem_ctrl.v")
        sources.append(src_path / "tinyQV/cpu/qspi_ctrl.v")
        sources.append(src_path / "tinyQV/cpu/qspi_setup.v")
        sources.append(src_path / "tinyQV/cpu/register.v")
        sources.append(src_path / "tinyQV/cpu/latch_reg.v")
        sources.append(src_path / "tinyQV/cpu/time.v")
        sources.append(src_path / "tinyQV/cpu/internal_ram.v")
        sources.append(src_path / "tinyQV/peri/uart/uart_tx.v")
        sources.append(src_path / "project.v")
        sources.append(src_path / "peripherals.v")
        sources.append(src_path / "peri_byte_empty.v")
        sources.append(src_path / "peri_full_empty.v")
        sources.append(src_path / "user_peripherals/uart/peri_uart.v")
        sources.append(src_path / "user_peripherals/uart/uart_rx.v")
        sources.append(src_path / "user_peripherals/uart/uart_tx.v")
        sources.append(src_path / "user_peripherals/spi.v")
        sources.append(src_path / "user_peripherals/matt_pwm/matt_pwm.v")
        sources.append(src_path / "user_peripherals/matt_pwm/pwm_strobe_gen.v")
        sources.append(src_path / "user_peripherals/matt_pwm/pwm.v")
        sources.append(src_path / "user_peripherals/usbcdc/peripheral.v")
        sources.append(src_path / "user_peripherals/usbcdc/bulk_endp.v")
        sources.append(src_path / "user_peripherals/usbcdc/ctrl_endp.v")
        sources.append(src_path / "user_peripherals/usbcdc/in_fifo.v")
        sources.append(src_path / "user_peripherals/usbcdc/out_fifo.v")
        sources.append(src_path / "user_peripherals/usbcdc/phy_rx.v")
        sources.append(src_path / "user_peripherals/usbcdc/phy_tx.v")
        sources.append(src_path / "user_peripherals/usbcdc/sie.v")
        sources.append(src_path / "user_peripherals/usbcdc/usb_cdc.v")

    sources += [
        # IO pad models
        Path(pdk_root) / pdk / f"libs.ref/{pad}/verilog/{pad}.v",
        
        # SRAM macros
        Path(pdk_root) / pdk / f"libs.ref/{sram}/verilog/{sram}__sram512x8m8wm1.v",
        Path(pdk_root) / pdk / f"libs.ref/{sram}/verilog/{sram}__sram1024x8m8wm1.v",
        
        # Custom IP
        proj_path / "../ip/gf180mcu_ws_ip__logo/vh/gf180mcu_ws_ip__logo.v",
        proj_path / "../ip/gf180mcu_ws_ip__marker/vh/gf180mcu_ws_ip__marker.v",
        proj_path / "../ip/gf180mcu_ws_ip__qrcode_id/vh/gf180mcu_ws_ip__qrcode_id.v",
        proj_path / "../ip/gf180mcu_ws_ip__shuttle_id/vh/gf180mcu_ws_ip__shuttle_id.v",
        proj_path / "../ip/gf180mcu_ws_ip__project_id/vh/gf180mcu_ws_ip__project_id.v",
        
        # Testbench
        "tb_top.v"
    ]

    build_args = []

    if sim == "icarus":
        # For debugging
        # build_args = ["-Winfloop", "-pfileline=1"]
        build_args += ["-gno-strict-declaration"]

    if sim == "verilator":
        build_args = ["--timing", "--trace", "--trace-fst", "--trace-structs"]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        defines=defines,
        always=True,
        includes=includes,
        build_args=build_args,
        waves=True,
    )

    plusargs = []

    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module="chip_top_tb,",
        plusargs=plusargs,
        waves=True,
    )


if __name__ == "__main__":
    chip_top_runner()
