# ESP32-S3 FSK 915 MHz gateway firmware

Objective: replace the RAK4631/Meshtastic gateway with an in-house ESP32-S3-WROOM-1 + RF69/RFM69HCW SPI gateway speaking FSK at 915 MHz. This feature covers only the gateway and its radio link to peer RFM69HC nodes; the companion server is explicitly out of scope.
Branch: `main` (user constraint: work on current branch, no push) | Delivery: `ask-on-risk` | Test runner: `bash firmware/gateway/host_tests/run.sh` and `idf.py build` inside the ESP-IDF environment

## Specs

S1. User: "Vamos a utilizar el plan Original, vamos a hacer nuestro propio meshtastic, el protocolo de comunicación ahora va a ser radiofrecuencia FSK a 915MHz"
- Authorized scope: new C firmware under `firmware/gateway/` only. No changes to `server/`, `config/`, credentials, ports or the preserved files listed in `unificar-servidor-gateway.md`.
- The radio must be configured for the 915 MHz band in FSK mode with configurable bitrate, deviation, sync word, CRC and optional AES key.
- No air parameter may be asserted as true for the peer nodes without evidence. Defaults are candidates, not facts, and must be labelled as unverified.

S2. User: "Vamos a hacer el código en C para que la comunicación sea lo más rápida posible"
- Implementation language is C using the ESP-IDF SPI master driver and FreeRTOS primitives; no Meshtastic, RadioHead or other radio library is a dependency.
- RF register calculations live in dependency-free C so they can be tested on the host before hardware is available.

S3. User: "Perfecto, entonces utilicemos el ESP32-S3-WROOM-1"
- Target is `esp32s3`. GPIO26–32 are reserved for flash/PSRAM and must never be assigned to the RF69.
- GPIO19 (D−) and GPIO20 (D+) are reserved for the native USB Serial/JTAG link and must never be assigned to the RF69.
- Doc-derived candidate wiring (UNVERIFIED, must be replaced by the user's real wiring): `SCK=GPIO13, MISO=GPIO12, MOSI=GPIO11, NSS=GPIO10, DIO0=GPIO2, RESET=GPIO15`. Source: CircuitDigest Arduino D2/D10-D13 mapping onto ESP32-S3-DevKitC-1 J1/J3 headers, confirmed present in both the v1.0 and v1.1 Espressif guides. Every pin is Kconfig-configurable.

S4. User: "hasta ahora todavía no lo vamos a conectar con el server que hizo el compañero, solo vamos a organizar the gateway para que se pueda comunicar con radiofrecuencia con otros nodos que también se van a poder comunicar por radiofrecuencia FSK"
- No server, MQTT, HTTP or cloud code is in scope. `server/sarabhel/listener.py` stays untouched in this feature.
- First hardware milestone is a register-level probe: read `RegVersion` (address `0x10`); `0x24` identifies the SX1231H used by RF69/RFM69HCW. Pinout is not considered confirmed until this read succeeds.

S5. User: "ya lo tengo conectado... Yo ya tengo el plugin ESP-IDF en Visual studio"
- Verified on this machine: `espressif.esp-idf-extension-2.3.0` is installed under Flatpak VS Code, but no `idf.py` existed; EIM was installed at `~/.espressif/eim_gui/eim`.
- Verified failure: `eim wizard --idf-features ide` launched from the Flatpak terminal fails with `libwebkit2gtk-4.1.so.0: cannot open shared object file`. Workaround: run `eim install` (CLI, non-interactive) from a host terminal, with `--skip-prerequisites-check true` because `ccache` and `dfu-util` are absent and sudo requires a password. Neither is needed for build or USB Serial/JTAG flashing.
- Verified on host: `/dev/ttyACM0` is `303a:1001 Espressif USB JTAG/serial debug unit`, user `mik4ela` is in group `uucp` and can write it. The exact chip behind that port is still unconfirmed: S3 and C6 share the VID/PID. `esptool.py chip_id` must confirm S3 before flashing.

S6. Verification and delivery
- Host tests: exact register values for 915.000 MHz (`0xE4C000`), 4800 bps (`0x0D05`) and 5 kHz deviation (`0x0052`), plus out-of-range rejection.
- Firmware: `idf.py build` must succeed in the ESP-IDF environment; `idf.py flash monitor` must show a plausible `RegVersion`.
- Observed results must be recorded honestly; an unavailable toolchain or missing hardware is reported as unavailable, never as PASS.
- Checks: `bash firmware/gateway/host_tests/run.sh`, `git diff --check`, `idf.py build`.

## Tasks

- T1 | S1,S2,S6 | inline | done | Dependency-free RF69 register math + host RED/GREEN tests. RED: missing `rf69_regs.h/.c`; GREEN: `bash host_tests/run.sh` exit 0. Risk: none.
- T2 | S3,S4,S5 | inline | done | ESP-IDF project, Kconfig pins/air params, SPI driver, RegVersion probe, README. `idf.py build` PASS on v6.1.1 after two fixes: component-level `main/Kconfig.projbuild` and `esp_driver_gpio`/`esp_driver_spi` in REQUIRES. Host tests PASS. Risk: item 3 (contracts — pin map and air params are Kconfig defaults, not yet confirmed).
- T3 | S1,S3,S4,S5,S6 | inline | done | `chip_id` PASS (ESP32-S3 rev v0.2, PSRAM 8MB on /dev/ttyACM0); flash PASS; software pin sweep found SCK=12 MISO=13 MOSI=11 NSS=10, hardware SPI confirmed `RegVersion=0x24`; defaults fixed and cold boot detects SX1231H in 264 ms with no sweep. Risk: item 5 (hardware/environment).

## Log

L1 (user request, verbatim): "Vamos a utilizar el plan Original, vamos a hacer nuestro propio meshtastic, el protocolo de comunicación ahora va a ser radiofrecuencia FSK a 915MHz"

L2 (user request, verbatim): "Vamos a hacer el código en C para que la comunicación sea lo más rápida posible"

L3 (user request, verbatim): "Perfecto, entonces utilicemos el ESP32-S3-WROOM-1"

L4 (user request, verbatim): "hasta ahora todavía no lo vamos a conectar con el server que hizo el compañero, solo vamos a organizar el gateway para que se pueda comunicar con radiofrecuencia con otros nodos que también se van a poder comunicar por radiofrecuencia FSK"

L5 (user request, verbatim): "ya lo tengo conectado... Yo ya tengo el plugin ESP-IDF en Visual studio. Cómo proseguimos para programar el gateway? Recuerda, hasta ahora todavía no lo vamos a conectar con el server que hizo el compañero, solo vamos a organizar el gateway para que se pueda comunicar con radiofrecuencia con otros nodos que también se van a poder comunicar por radiofrecuencia FSK. Cómo empiezo a cuadrar el gateway? Flashearlo, programarlo, y conectarlo con otros servicios?"

L6 (user report, verbatim): "Aparece: \"sh-5.3$ \"/home/mik4ela/.espressif/eim_gui/eim\" wizard --idf-features ide /home/mik4ela/.espressif/eim_gui/eim: error while loading shared libraries: libwebkit2gtk-4.1.so.0: cannot open shared object file: No such file or directory / sh-5.3$ \""

L7 (verified on host, 2026-11-20): `eim --help` and `eim list` succeed from a host shell, so the library error is specific to the Flatpak VS Code terminal. GitHub API reports latest stable ESP-IDF `v6.1.1` published 2026-11-16; its release notes recommend `eim install -i v6.1.1`.

L8 (verified on host): first `eim install -i v6.1.1 -t esp32s3 --idf-features ide --do-not-track true` exited 1 with "The following prerequisites are not satisfied [\"ccache\", \"dfu-util\"]". Retried with `--skip-prerequisites-check true`; install running in background.

L9 (memory mirror): pending — Engram reported ambiguous projects (`lora-hakaton`, `unal`) for this workspace; no project key was guessed. The local feature document is authoritative.

L10 (implementation): created `firmware/gateway/` with root and component `CMakeLists.txt`, `Kconfig.projbuild` (all six pins plus frequency/bitrate/deviation, `RF69_APPLY_CONFIG` default n), `sdkconfig.defaults`, dependency-free `rf69_regs.h/.c`, SPI driver `rf69.h/.c` with reserved-pin rejection, `gateway_main.c` printing `RegVersion`, `host_tests/` and `README.md`. No server file was touched.

L11 (verification): `bash firmware/gateway/host_tests/run.sh` → RED on missing header/source, then GREEN after implementation (asserts 915 MHz = `0xE4C000`, 4800 bps = `0x0D05`, 5 kHz = `0x0052`, decode within one FSTEP, zero rejection). `git -C PROYECTO diff --check` exit 0; no trailing whitespace in the new files. `idf.py build` UNAVAILABLE until the background EIM install finishes.

L12 (user provided two pinout sources, 2026-11-20): Espressif ESP32-S3-DevKitC-1 v1.1 guide and CircuitDigest RFM69HCW/Arduino guide. Verified from the pages: DevKitC-1 exposes GPIO10-14 on J1 and GPIO2 on J3; GPIO35-37 are unavailable on octal SPI flash/PSRAM modules; the board has both a Micro-USB USB-to-UART port and an ESP32-S3 native USB port, and the guide uses USB-to-UART by default. CircuitDigest wiring table is Arduino-side: D2=DIO0, D10=NSS, D11=MOSI, D12=MISO, D13=SCK, and RST unconnected. Mapped to the S3 headers as `SCK=13, MISO=12, MOSI=11, NSS=10, DIO0=2, RESET=15`; all defaults are still UNVERIFIED against the user's real wires. Kconfig defaults updated; `spi_bus_config_t.miso_io_num` typo fixed; reserved pin check extended to 35-37.

L13 (verification, 2026-11-20 21:25): only `/dev/ttyACM0` exists (VID 303a PID 1001), no `/dev/ttyUSB*`, so the board is connected through the native USB port. `esptool.py chip_id` with system Python failed because the standalone wrapper imports the `esptool` module, which is not installed yet; the EIM venv is still being created. Chip identity remains unconfirmed.

L14 (install complete, 2026-11-20 21:29): EIM reported "Successfully installed IDF" v6.1.1 with activation script `~/.espressif/tools/activate_idf_v6.1.1.sh`. `idf.py --version` → ESP-IDF v6.1.1.

L15 (verification): `python -m esptool --port /dev/ttyACM0 chip_id` → ESP32-S3 (QFN56) rev v0.2, Wi-Fi/BT, 240 MHz, embedded PSRAM 8MB (AP_3v3), 40 MHz crystal, USB-Serial/JTAG, MAC b8:f8:62:e2:c8:68. S3 confirmed; no C6 risk.

L16 (build fixes): first `idf.py build` failed because `driver/gpio.h` needs `esp_driver_gpio` in REQUIRES under ESP-IDF 6. Added `esp_driver_gpio` and `esp_driver_spi`. Second build failed with all `CONFIG_RF69_*` undeclared: a project-root `Kconfig.projbuild` is not loaded by ESP-IDF; moved to `main/Kconfig.projbuild` and ran `idf.py reconfigure`. Third `idf.py build` → "Project build complete", exit 0. `sdkconfig` now contains all RF69 defaults.

L17 (flash and runtime, 2026-11-20): `idf.py -p /dev/ttyACM0 flash` → wrote 203040 bytes at 0x10000, hash verified, exit 0. `idf.py -p /dev/ttyACM0 monitor` boot log: `wiring: SCK=13 MISO=12 MOSI=11 NSS=10 DIO0=2 RESET=15`, then `Unexpected RegVersion=0x00 (expected 0x24)`, then alive loop. SPI completes but no RF69 responds. No radio configuration was applied (`RF69_APPLY_CONFIG` not set). Blocked on user-provided wiring/power facts; no further code change before that evidence.

L18 (housekeeping): added ESP-IDF build artifacts to `.gitignore` (`firmware/gateway/build/`, `sdkconfig.old`, `managed_components/`); `sdkconfig` stays tracked.

L19 (read-back verification): `python -m esptool --port /dev/ttyACM0 verify_flash 0x10000 build/gateway_fsk_915.bin` → "Verification successful (digest matched)", exit 0. The bytes in the chip's flash match the compiled binary; the boot log string `ESP32-S3 RF69 FSK 915 MHz gateway - probe stage` comes from `gateway_main.c`, confirming the flashed app is the one running.

L20 (VS Code wizard diagnosis): the Flatpak user `settings.json` contained `idf.eimExecutableArgs: ["wizard", "--idf-features ide"]` and no `idf.currentSetup`, so the extension kept invoking the EIM setup wizard. EIM's `wizard` works from a host terminal (`eim wizard --help` exit 0) but its GUI needs `libwebkit2gtk-4.1.so.0`, invisible inside the Flatpak sandbox. `eim_idf.json` lists the installed setup at `/home/mik4ela/.espressif/v6.1.1/esp-idf` with activation script `~/.espressif/tools/activate_idf_v6.1.1.sh`. Replaced the Flatpak user settings with `idf.currentSetup` pointing to that path, `idf.showOnboardingOnInit: false`, `idf.port: /dev/ttyACM0`, `idf.flashType: UART`, and removed the wizard args; added the same setup/port settings to `firmware/gateway/.vscode/settings.json`. User must reload the VS Code window.

L21 (VS Code "no build directory to clean" diagnosis): the second `[espIdf.flashDevice] Unhandled error ... There is no build directory to clean, exiting!` (error code `NoBuildDirToClean`, log `Full clean blocked: build directory does not exist.`) was caused by VS Code having the parent folder `/home/mik4ela/Documentos/Hackaton/UNAL` open, which has no `CMakeLists.txt`/`build/`. Confirmed `build/CMakeCache.txt` and `build/gateway_fsk_915.bin` exist only in `PROYECTO/firmware/gateway`. Created `/home/mik4ela/Documentos/Hackaton/UNAL/firmware-gateway.code-workspace` with the gateway folder as root and the IDF/port settings, opened it with `flatpak run com.visualstudio.code --reuse-window <workspace>`, and confirmed its workspaceStorage entry (`f90c9eb5...`). Verified no `eimExecutableArgs`/`wizard` remains, all three settings JSONs are valid, and `idf.py --version` → v6.1.1 from the gateway folder. The plugin now runs in the folder that owns the build directory.

L22 (autoprobe, 2026-11-20): added `rf69_deinit()` and a probe loop in `gateway_main.c` that tries four pin maps (documented GPIO13/12/11/10; MISO/MOSI swapped; J1 header positions 13/12/11/10 → GPIO3/8/18/17; that one swapped). Host tests PASS, build PASS, flash PASS. Monitor output: candidate 0 `RegVersion=0xFF`, candidates 1–3 `0x00`; none returned `0x24`. Conclusion: the RF69 is not on any probed pin set, is unpowered, or is wired to a different board.

L23 (document evidence): re-fetched both source docs. Espressif DevKitC-1 v1.0 header table confirms J1 No.16 = GPIO10, No.17 = GPIO11, No.18 = GPIO12, No.19 = GPIO13, No.8 = GPIO15; J3 No.5 = GPIO2. Header position number != GPIO number (e.g. J1 No.10 = GPIO17). CircuitDigest's connection tables are explicitly for **Arduino Nano** (D2→DIO0, D10→NSS, D11→MOSI, D12→MISO, D13→SCK), do not connect RST, and use 434 MHz modules with logic level converters. Those `Dxx` labels are Arduino pin names, not ESP32 GPIOs — this is the source of the pin-map ambiguity, not a firmware defect. Asked the user whether the RF69 is wired to the ESP32-S3 or to an Arduino-style setup, and for the physical header numbers if on the S3.

L24 (pin sweep SUCCESS, 2026-11-20): after the user said "Intenta nuevamente", replaced the four-candidate probe with `pin_sweep.c/.h`: bit-banged SPI mode 0 over 26 header GPIOs (USB/flash/PSRAM/UART/strapping excluded), trying all 358,800 ordered 4-pin permutations and confirming any `0x24` three times. Host tests, build and flash PASS. Monitor: `MATCH: SCK=12 MISO=13 MOSI=11 NSS=10` at 10484 ms; hardware SPI then returned `RegVersion=0x24`. Root cause: SCK and MISO were swapped versus the doc-derived guess — the module is wired to SCK=GPIO12, MISO=GPIO13, MOSI=GPIO11, NSS=GPIO10. Fixed Kconfig defaults and `sdkconfig` to those values; rewrote `gateway_main.c` so the configured pinout is tried first and the sweep runs only as fallback. Rebuild, flash and cold-boot monitor PASS: `SX1231H detected (RegVersion=0x24)` at 264 ms with no sweep line. `build/config/sdkconfig.h` confirms 12/13/11/10. `RF69_APPLY_CONFIG` still off; no TX/RX until peer air params are known. T3 closed. Risk: item 5 (hardware/environment).
