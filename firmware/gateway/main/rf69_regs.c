#include "rf69_regs.h"

static uint32_t scaled_from_hz(uint32_t hz)
{
    if (hz == 0u) {
        return 0u;
    }

    uint64_t scaled = ((uint64_t)hz * RF69_FSTEP_DIVISOR)
                      + (RF69_FXOSC_HZ / 2u);
    scaled /= RF69_FXOSC_HZ;

    return (scaled > 0xFFFFFFFFull) ? 0u : (uint32_t)scaled;
}

uint32_t rf69_frf_from_hz(uint32_t hz)
{
    uint32_t frf = scaled_from_hz(hz);

    /* FRF is a 24-bit register. */
    if (frf == 0u || frf > 0xFFFFFFu) {
        return 0u;
    }
    return frf;
}

uint16_t rf69_bitrate_from_bps(uint32_t bps)
{
    if (bps == 0u) {
        return 0u;
    }

    /* BR = FXOSC / (2 * bitrate), rounded to the nearest integer. */
    uint64_t br = ((uint64_t)RF69_FXOSC_HZ + (uint64_t)bps)
                  / (2ull * (uint64_t)bps);

    return (br == 0u || br > 0xFFFFull) ? 0u : (uint16_t)br;
}

uint16_t rf69_fdev_from_hz(uint32_t hz)
{
    uint32_t fdev = scaled_from_hz(hz);

    return (fdev == 0u || fdev > 0xFFFFu) ? 0u : (uint16_t)fdev;
}
