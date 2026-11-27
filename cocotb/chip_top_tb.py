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

from riscvmodel.regnames import x0, x1, sp, gp, tp, a0, a1, a2, a3, a4, a5
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
    c = Clock(clock, 20.832, "ns")
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

async def read_reg(dut, reg, allow_long_delay=False, allow_long_delay_before=False):
    offset = random.randint(-0x400, 0x3FF)
    instr = InstructionSW(gp, reg, offset).encode()
    await send_instr(dut, instr, False, allow_long_delay_before)

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

async def read_byte(dut, reg, expected_val):
  await send_instr(dut, InstructionSW(tp, reg, 0x18).encode())

  await start_nops(dut)
  for i in range(240):
      if dut.debug_uart_tx.value == 0:
          break
      else:
          await Timer(5, "ns")
  assert dut.debug_uart_tx.value == 0
  bit_time = 1000
  await Timer(bit_time / 2, "ns")
  assert dut.debug_uart_tx.value == 0
  for i in range(8):
      await Timer(bit_time, "ns")
      assert dut.debug_uart_tx.value == (expected_val & 1)
      expected_val >>= 1
  await Timer(bit_time, "ns")
  assert dut.debug_uart_tx.value == 1

  await stop_nops()


#@cocotb.test()
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

    # Check BIO ID
    await send_instr(dut, InstructionLUI(a0, 0x9000).encode())
    await send_instr(dut, InstructionLW(x1, a0, 0x4).encode())
    assert await read_reg(dut, x1) == 0x08000480

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

#@cocotb.test()
async def test_uart(dut):
    """Run a simple UART test"""

    # Create a logger for this testbench
    logger = logging.getLogger("my_testbench")

    logger.info("Startup sequence...")

    # Start up
    await start_up(dut)

    logger.info("Running the UART test...")

    # Test UART TX
    uart_byte = 0x54
    await send_instr(dut, InstructionADDI(x1, x0, uart_byte).encode())
    await send_instr(dut, InstructionSW(tp, x1, 0x80).encode())

    await start_nops(dut)
    bit_time = 8680
    await Timer(bit_time / 2, "ns")
    assert dut.uart_tx.value == 0
    for i in range(8):
        await Timer(bit_time, "ns")
        assert dut.uart_tx.value == (uart_byte & 1)
        uart_byte >>= 1
    await Timer(bit_time, "ns")
    assert dut.uart_tx.value == 1

    # Test UART RX
    for j in range(5):
        assert dut.uart_rts.value == 0

        uart_rx_byte = random.randint(0, 255)
        val = uart_rx_byte
        dut.uart_rx.value = 0
        await Timer(bit_time, "ns")
        for i in range(8):
            dut.uart_rx.value = val & 1
            await Timer(bit_time, "ns")
            assert dut.uart_rts.value == 0
            val >>= 1
        dut.uart_rx.value = 1
        await Timer(bit_time, "ns")
        assert dut.uart_rts.value == 0

        uart_rx_byte2 = random.randint(0, 255)
        val = uart_rx_byte2
        dut.uart_rx.value = 0
        await Timer(bit_time, "ns")
        for i in range(8):
            dut.uart_rx.value = val & 1
            await Timer(bit_time, "ns")
            assert dut.uart_rts.value == 1
            val >>= 1
        dut.uart_rx.value = 1
        await Timer(bit_time, "ns")
        assert dut.uart_rts.value == 1

        await stop_nops()

        await send_instr(dut, InstructionLW(x1, tp, 0x84).encode())
        await read_byte(dut, x1, 0x2)
        await send_instr(dut, InstructionLW(x1, tp, 0x80).encode())
        await read_byte(dut, x1, uart_rx_byte)
        assert dut.uart_rts.value == 0
        await send_instr(dut, InstructionLW(x1, tp, 0x84).encode())
        await read_byte(dut, x1, 0x2)
        await send_instr(dut, InstructionLW(x1, tp, 0x80).encode())
        await read_byte(dut, x1, uart_rx_byte2)
        assert dut.uart_rts.value == 0
        await send_instr(dut, InstructionLW(x1, tp, 0x84).encode())
        await read_byte(dut, x1, 0)

        if j != 4:
            await start_nops(dut)

    # Test Debug UART TX
    #uart_byte = 0x5A
    #await send_instr(dut, InstructionADDI(x1, x0, uart_byte).encode())
    #await read_byte(dut, x1, uart_byte)

    logger.info("Done!")

@cocotb.test()
async def test_scratch_memory(dut):

    def encode_sw2(base_reg, reg, imm):
        instr = InstructionSW(base_reg, reg, imm).encode()
        return instr | (3 << 12)

    def encode_sw4(base_reg, reg, imm):
        instr = InstructionSW(base_reg, reg, imm).encode()
        return instr | (7 << 12)

    def encode_lw2(reg, base_reg, imm):
        instr = InstructionLW(reg, base_reg, imm).encode()
        return instr | (3 << 12)

    def encode_lw4(reg, base_reg, imm):
        instr = InstructionLW(reg, base_reg, imm).encode()
        return instr | (7 << 12)

    # Create a logger for this testbench
    logger = logging.getLogger("my_testbench")

    logger.info("Startup sequence...")

    # Start up
    await start_up(dut)

    logger.info("Running the Scratch memory test...")

    RAM_SIZE = 512
    RAM = [0]*RAM_SIZE
    for i in range(0, RAM_SIZE, 4):
        await send_instr(dut, InstructionADDI(x1, x0, i).encode())
        await send_instr(dut, InstructionSW(x0, x1, i-0x400).encode())
        RAM[i] = i & 0xff
        RAM[i+1] = i >> 8

    for i in range(0, RAM_SIZE, 4):
        await send_instr(dut, InstructionLW(x1, x0, i-0x400).encode())
        assert await read_reg(dut, x1) == i

    mask = [0xfff, 0xffe, 0xffc, 0xff8, 0xff0]
    for i in range(20):
        write_len = random.randint(0,4)
        write_addr = random.randint(0,RAM_SIZE - (1 << write_len)) & mask[write_len]
        write_val = random.randint(0,0xffffffff)
        await send_instr(dut, InstructionLUI(a0, (write_val >> 12) + ((write_val >> 11) & 1)).encode())
        await send_instr(dut, InstructionADDI(a0, a0, (write_val & 0xfff) - (0x1000 if write_val & 0x800 else 0)).encode())
        if write_len >= 3:
            write_val2 = random.randint(0,0xffffffff)
            await send_instr(dut, InstructionLUI(a1, (write_val2 >> 12) + ((write_val2 >> 11) & 1)).encode())
            await send_instr(dut, InstructionADDI(a1, a1, (write_val2 & 0xfff) - (0x1000 if write_val2 & 0x800 else 0)).encode())
        if write_len >= 4:
            write_val3 = random.randint(0,0xffffffff)
            write_val4 = random.randint(0,0xffffffff)
            await send_instr(dut, InstructionLUI(a2, (write_val3 >> 12) + ((write_val3 >> 11) & 1)).encode())
            await send_instr(dut, InstructionADDI(a2, a2, (write_val3 & 0xfff) - (0x1000 if write_val3 & 0x800 else 0)).encode())
            await send_instr(dut, InstructionLUI(a3, (write_val4 >> 12) + ((write_val4 >> 11) & 1)).encode())
            await send_instr(dut, InstructionADDI(a3, a3, (write_val4 & 0xfff) - (0x1000 if write_val4 & 0x800 else 0)).encode())

        if write_len == 0: await send_instr(dut, InstructionSB(x0, a0, write_addr-0x400).encode())
        elif write_len == 1: await send_instr(dut, InstructionSH(x0, a0, write_addr-0x400).encode())
        elif write_len == 2: await send_instr(dut, InstructionSW(x0, a0, write_addr-0x400).encode())
        elif write_len == 3: await send_instr(dut, encode_sw2(x0, a0, write_addr-0x400))
        else: await send_instr(dut, encode_sw4(x0, a0, write_addr-0x400))

        read_len = write_len
        read_addr = write_addr
        read_val = write_val        
        if write_len == 0: read_val &= 0xff
        if write_len == 1: read_val &= 0xffff
        if write_len > 2: read_val2 = write_val2
        if write_len > 3: 
            read_val3 = write_val3
            read_val4 = write_val4

        RAM[write_addr] = write_val & 0xff
        if write_len > 0: RAM[write_addr + 1] = (write_val >> 8) & 0xff
        if write_len > 1:
            RAM[write_addr + 2] = (write_val >> 16) & 0xff
            RAM[write_addr + 3] = (write_val >> 24) & 0xff
        if write_len > 2:
            RAM[write_addr + 4] = write_val2 & 0xff
            RAM[write_addr + 5] = (write_val2 >> 8) & 0xff
            RAM[write_addr + 6] = (write_val2 >> 16) & 0xff
            RAM[write_addr + 7] = (write_val2 >> 24) & 0xff
        if write_len > 3:
            RAM[write_addr + 8] = write_val3 & 0xff
            RAM[write_addr + 9] = (write_val3 >> 8) & 0xff
            RAM[write_addr + 10] = (write_val3 >> 16) & 0xff
            RAM[write_addr + 11] = (write_val3 >> 24) & 0xff
            RAM[write_addr + 12] = write_val4 & 0xff
            RAM[write_addr + 13] = (write_val4 >> 8) & 0xff
            RAM[write_addr + 14] = (write_val4 >> 16) & 0xff
            RAM[write_addr + 15] = (write_val4 >> 24) & 0xff

        if read_len == 0: await send_instr(dut, InstructionLBU(a2, x0, read_addr-0x400).encode())
        elif read_len == 1: await send_instr(dut, InstructionLHU(a2, x0, read_addr-0x400).encode())
        elif read_len == 2: await send_instr(dut, InstructionLW(a2, x0, read_addr-0x400).encode())
        elif read_len == 3: await send_instr(dut, encode_lw2(a2, x0, read_addr-0x400))
        else: await send_instr(dut, encode_lw4(a2, x0, read_addr-0x400))
        assert await read_reg(dut, a2, read_len >= 3, read_len == 4) == read_val
        if read_len > 2:
            assert await read_reg(dut, a3) == read_val2
        if read_len > 3:
            assert await read_reg(dut, a4) == read_val3
            assert await read_reg(dut, a5) == read_val4

    for i in range(400):
        if random.randint(0, 1) == 0:
            read_len = random.randint(0,4)
            read_addr = random.randint(0,RAM_SIZE - (1 << read_len)) & mask[read_len]
            if read_len == 0: await send_instr(dut, InstructionLB(a0, x0, read_addr-0x400).encode())
            elif read_len == 1: await send_instr(dut, InstructionLH(a0, x0, read_addr-0x400).encode())
            elif read_len == 2: await send_instr(dut, InstructionLW(a0, x0, read_addr-0x400).encode())
            elif read_len == 3: await send_instr(dut, encode_lw2(a0, x0, read_addr-0x400))
            else: await send_instr(dut, encode_lw4(a0, x0, read_addr-0x400))
            read_val = await read_reg(dut, a0, read_len >= 3)
            assert (read_val & 0xFF) == RAM[read_addr]
            if read_len > 0: assert ((read_val >> 8) & 0xFF) == RAM[read_addr+1]
            if read_len > 1: 
                assert ((read_val >> 16) & 0xFF) == RAM[read_addr+2]
                assert ((read_val >> 24) & 0xFF) == RAM[read_addr+3]
            if read_len > 2:
                assert await read_reg(dut, a1) == RAM[read_addr+7] << 24 | RAM[read_addr+6] << 16 | RAM[read_addr+5] << 8 | RAM[read_addr+4]
            if read_len > 3:
                assert await read_reg(dut, a2) == RAM[read_addr+11] << 24 | RAM[read_addr+10] << 16 | RAM[read_addr+9] << 8 | RAM[read_addr+8]
                assert await read_reg(dut, a3) == RAM[read_addr+15] << 24 | RAM[read_addr+14] << 16 | RAM[read_addr+13] << 8 | RAM[read_addr+12]
        else:
            write_len = random.randint(0,2)
            write_addr = random.randint(0,RAM_SIZE - (1 << write_len)) & mask[write_len]
            write_val = random.randint(0,0xffffffff)
            await send_instr(dut, InstructionLUI(x1, (write_val >> 12) + ((write_val >> 11) & 1)).encode())
            await send_instr(dut, InstructionADDI(x1, x1, (write_val & 0xfff) - (0x1000 if write_val & 0x800 else 0)).encode())

            if write_len == 0: await send_instr(dut, InstructionSB(x0, x1, write_addr-0x400).encode())
            elif write_len == 1: await send_instr(dut, InstructionSH(x0, x1, write_addr-0x400).encode())
            else: await send_instr(dut, InstructionSW(x0, x1, write_addr-0x400).encode())
            
            RAM[write_addr] = write_val & 0xff
            if write_len > 0: RAM[write_addr + 1] = (write_val >> 8) & 0xff
            if write_len > 1:
                RAM[write_addr + 2] = (write_val >> 16) & 0xff
                RAM[write_addr + 3] = (write_val >> 24) & 0xff

#@cocotb.test()
async def test_bio_core_memory(dut):
    # Create a logger for this testbench
    logger = logging.getLogger("my_testbench")

    logger.info("Startup sequence...")

    # Start up
    await start_up(dut)

    logger.info("Running the Scratch memory test...")

    RAM_SIZE = 2048
    RAM_BASE = 0x9009000 # Core 0 memory
    RAM = [0]*RAM_SIZE
    await send_instr(dut, InstructionLUI(sp, RAM_BASE >> 12).encode())
    for i in range(0, RAM_SIZE, 4):
        await send_instr(dut, InstructionLUI(x1, (i >> 12) + ((i >> 11) & 1)).encode())
        await send_instr(dut, InstructionADDI(x1, x1, (i & 0xfff) - (0x1000 if i & 0x800 else 0)).encode())
        await send_instr(dut, InstructionSW(sp, x1, i).encode())
        RAM[i] = i & 0xff
        RAM[i+1] = i >> 8

    for i in range(0, RAM_SIZE, 4):
        await send_instr(dut, InstructionLW(x1, sp, i).encode())
        assert await read_reg(dut, x1) == i

    mask = [0xfff, 0xffe, 0xffc]
    for i in range(20):
        write_len = 2
        write_addr = random.randint(0,RAM_SIZE - (1 << write_len)) & mask[write_len]
        write_val = random.randint(0,0xffffffff)
        await send_instr(dut, InstructionLUI(x1, (write_val >> 12) + ((write_val >> 11) & 1)).encode())
        await send_instr(dut, InstructionADDI(x1, x1, (write_val & 0xfff) - (0x1000 if write_val & 0x800 else 0)).encode())
        await send_instr(dut, InstructionSW(sp, x1, write_addr).encode())

        read_len = write_len
        read_addr = write_addr
        read_val = write_val

        RAM[write_addr] = write_val & 0xff
        RAM[write_addr + 1] = (write_val >> 8) & 0xff
        RAM[write_addr + 2] = (write_val >> 16) & 0xff
        RAM[write_addr + 3] = (write_val >> 24) & 0xff

        await send_instr(dut, InstructionLW(x1, sp, read_addr).encode())
        assert await read_reg(dut, x1) == read_val

    for i in range(300):
        if random.randint(0, 1) == 0:
            read_len = 2
            read_addr = random.randint(0,RAM_SIZE - (1 << read_len)) & mask[read_len]
            await send_instr(dut, InstructionLW(x1, sp, read_addr).encode())
            read_val = await read_reg(dut, x1)
            assert (read_val & 0xFF) == RAM[read_addr]
            assert ((read_val >> 8) & 0xFF) == RAM[read_addr+1]
            assert ((read_val >> 16) & 0xFF) == RAM[read_addr+2]
            assert ((read_val >> 24) & 0xFF) == RAM[read_addr+3]
        else:
            write_len = 2
            write_addr = random.randint(0,RAM_SIZE - (1 << write_len)) & mask[write_len]
            write_val = random.randint(0,0xffffffff)
            await send_instr(dut, InstructionLUI(x1, (write_val >> 12) + ((write_val >> 11) & 1)).encode())
            await send_instr(dut, InstructionADDI(x1, x1, (write_val & 0xfff) - (0x1000 if write_val & 0x800 else 0)).encode())
            await send_instr(dut, InstructionSW(sp, x1, write_addr).encode())
            
            RAM[write_addr] = write_val & 0xff
            RAM[write_addr + 1] = (write_val >> 8) & 0xff
            RAM[write_addr + 2] = (write_val >> 16) & 0xff
            RAM[write_addr + 3] = (write_val >> 24) & 0xff


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

        proj_path / "../ip/gf180mcu_tnt_io/gf180mcu_tnt_io__bi_24t_usb.v",
        
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
