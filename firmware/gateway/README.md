# ESP32-S3 FSK 915 MHz gateway (probe stage)

C firmware for the in-house replacement of the RAK4631/Meshtastic gateway.
This project only brings up the radio link to peer RFM69HC nodes. It does not
talk to the companion server, MQTT, or any cloud service.

## Current status

The firmware verifies the SPI link: it reads `RegVersion` (address `0x10`) and
prints the result. `0x24` identifies the SX1231H used by RF69 / RFM69HCW.

Verified wiring on 2026-11-20 by a software pin sweep: **SCK=12, MISO=13,
MOSI=11, NSS=10**. These are the Kconfig/default values; the sweep is only a
fallback if the configured pinout stops answering. DIO0=2 and RESET=15 are
still assumptions.

Radio configuration is **not applied** (`RF69_APPLY_CONFIG=n`) and there is no
TX/RX loop yet. Air parameters are unverified, so the firmware must not change
radio state before the peer nodes are known.

## Facts verified on this machine

- ESP-IDF VS Code extension `espressif.esp-idf-extension-2.3.0` is installed.
- `eim wizard` from the Flatpak VS Code terminal fails with
  `libwebkit2gtk-4.1.so.0: cannot open shared object file`. Run `eim install`
  from a normal host terminal instead; it has no GUI dependency.
- `/dev/ttyACM0` is `303a:1001 Espressif USB JTAG/serial debug unit` and the
  user can write it. ESP32-S3 and ESP32-C6 share this VID/PID, so the chip must
  be confirmed with `esptool.py chip_id` before flashing.
- `firmware_nodo/` contains only the RAK4631 Meshtastic UF2 and its keys; there
  is no RF69 node firmware here to derive air parameters from.

## Assumptions that still need confirmation

| Item | Candidate in this code | Status |
| --- | --- | --- |
| SCK / MISO / MOSI / NSS | GPIO12 / GPIO13 / GPIO11 / GPIO10 | VERIFIED by pin sweep + `RegVersion=0x24` |
| DIO0 / RESET | GPIO2 / GPIO15 | UNVERIFIED wiring; CircuitDigest leaves RST unconnected |
| Bitrate | 4800 bps | UNVERIFIED |
| Deviation | 5 kHz | UNVERIFIED |
| Sync word / CRC / AES | not configured yet | UNKNOWN on peer nodes |
| RF module variant | RF69 / RFM69HCW | UNVERIFIED |

GPIO19/20 (native USB) and GPIO26–32 (flash/PSRAM) are rejected by the driver.

## Build and flash

Run these from a host terminal once `eim install` has completed. Only
`/dev/ttyACM0` exists on this machine (native USB Serial/JTAG); there is no
`/dev/ttyUSB*`. The v1.0 DevKitC-1 guide explicitly says the ESP32-S3 USB
port connection is "not fully implemented in software" and uses the Micro-USB
USB-to-UART port by default. If flashing over `/dev/ttyACM0` fails, move the
cable to the Micro-USB port and use the resulting `/dev/ttyUSB*` device.

```sh
source /home/mik4ela/.espressif/v6.1.1/esp-idf/export.sh
cd firmware/gateway
python -m esptool --port /dev/ttyACM0 chip_id   # must say ESP32-S3
idf.py set-target esp32s3
idf.py menuconfig                               # RF69 Radio -> real pin numbers
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

If `chip_id` reports ESP32-C6, this is the old board and flashing must stop.
If the native USB port resets too early during flashing, hold BOOT, press and
release RESET, then release BOOT before running `idf.py flash`.

In VS Code with the ESP-IDF extension, set `idf.espIdfPath` to
`/home/mik4ela/.espressif/v6.1.1/esp-idf`, then use the extension commands
"Set Espressif device target" (esp32s3), "Build", "Flash" and "Monitor".
Do not run the EIM GUI wizard from the Flatpak terminal: it fails with
`libwebkit2gtk-4.1.so.0: cannot open shared object file`.

Expected log lines:

```
I (...) gateway: SX1231H detected (RegVersion=0x24): SPI and pinout look correct
```

Any other `RegVersion` value means the module identity or the wiring is wrong.
Do not enable `RF69_APPLY_CONFIG` until that line appears.

Observed on 2026-11-20: the doc-derived map (SCK=13/MISO=12) returned
`0xFF`/`0x00`; the pin sweep found SCK=12/MISO=13, and hardware SPI then read
`0x24`. If `RegVersion` is not `0x24` on a future boot, check 3.3 V and GND on
the module, that the signals go to **GPIO numbers** (not J1/J3 header numbers),
and that the module is wired to this ESP32-S3 and not the older ESP32-C6.

## Host tests

The RF register math is dependency-free and runs without the toolchain:

```sh
bash host_tests/run.sh
```

## Next steps

1. Obtain the peer nodes' bitrate, sync word, CRC and AES settings.
2. Enable `RF69_APPLY_CONFIG` and apply those air parameters.
3. Add the TX/RX loop and verify two nodes exchange packets.
4. Only then consider the server integration.
