/* Host-only regression tests for the dependency-free RF69 register math. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "../main/rf69_regs.h"

int main(void)
{
    /* FXOSC = 32 MHz, FSTEP = FXOSC / 2^19 = 61.03515625 Hz. */
    assert(rf69_frf_from_hz(915000000u) == 0xE4C000u);
    assert(rf69_bitrate_from_bps(4800u) == 0x0D05u);
    assert(rf69_fdev_from_hz(5000u) == 0x0052u);

    /* The decoded carrier must stay within one FSTEP of 915.000 MHz. */
    uint32_t frf = rf69_frf_from_hz(915000000u);
    int64_t decoded_hz = ((int64_t)frf * (int64_t)RF69_FXOSC_HZ) / 524288;
    assert(decoded_hz >= 914999940 && decoded_hz <= 915000060);

    /* Zero/invalid inputs must be rejected instead of silently wrapping. */
    assert(rf69_frf_from_hz(0u) == 0u);
    assert(rf69_bitrate_from_bps(0u) == 0u);
    assert(rf69_fdev_from_hz(0u) == 0u);

    printf("rf69_regs: all host tests passed\n");
    return 0;
}
