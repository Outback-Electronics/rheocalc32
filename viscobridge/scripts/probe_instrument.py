#!/usr/bin/env python3
"""Diagnostic probe: opens the serial port ONCE, sends K/E/R one at a time
on the same connection, and prints every reply as raw hex + ASCII so you
can see exactly what the instrument sends -- no guessing, no reopening
the port between commands.

Usage:
    python3 probe_instrument.py /dev/ttyUSB0

Put the probe in a KNOWN reference temperature before running this
(e.g. an ice-water bath == 0.0 degC, or next to a calibrated thermometer)
so you have ground truth to check the decoded temp_c against.
"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"

TORQUE_FULL_SCALE_COUNTS = 0x2B00 - 0x0400
TEMP_COUNTS_PER_DEGREE = 40.0
CANDIDATE_ZERO_COUNTS = {
    "manual (Appendix G, 0x2700)": 0x2700,
    "current code (0x0F0B)": 0x0F0B,
}


def send(ser, body, read_timeout=2.0):
    ser.reset_input_buffer()
    ser.write((body + "\r").encode("ascii"))
    prev = ser.timeout
    ser.timeout = read_timeout
    raw = ser.read_until(b"\r")
    ser.timeout = prev
    print(f">>> {body!r}")
    print(f"<<< raw bytes: {raw!r}")
    print(f"<<< hex:       {raw.hex()}")
    return raw.decode("ascii", errors="replace").strip()


def main():
    ser = serial.Serial(PORT, 9600, bytesize=8, parity="N", stopbits=1, timeout=2.0)
    ser.reset_input_buffer()
    time.sleep(0.2)

    send(ser, "K")          # reset - no response expected
    time.sleep(0.5)

    reply = send(ser, "E")  # enable
    time.sleep(0.5)

    reply = send(ser, "R")  # retrieve
    if not reply.startswith("R") or len(reply) < 11:
        print(f"\n!! Reply does not match expected <R><vvvv><tttt><ss> framing: {reply!r}")
        print("!! This means the driver's protocol assumption may not match this hardware.")
        ser.close()
        return

    vvvv = int(reply[1:5], 16)
    tttt = int(reply[5:9], 16)
    ss = reply[9:11]

    print(f"\nParsed fields from {reply!r}:")
    print(f"  vvvv (torque counts) = 0x{vvvv:04X} ({vvvv})")
    print(f"  tttt (temp counts)   = 0x{tttt:04X} ({tttt})")
    print(f"  ss   (status)        = {ss}")

    print("\nDecoded temperature under each candidate zero-count constant:")
    for label, zero_counts in CANDIDATE_ZERO_COUNTS.items():
        temp_c = (tttt - zero_counts) / TEMP_COUNTS_PER_DEGREE
        print(f"  {label:35s} -> {temp_c:.2f} degC")

    print("\nCompare these two numbers against your known reference temperature")
    print("(ice bath / calibrated thermometer) to see which constant is actually correct.")

    ser.close()


if __name__ == "__main__":
    main()
