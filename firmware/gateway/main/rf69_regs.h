#ifndef RF69_REGS_H
#define RF69_REGS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* SX1231H crystal and frequency resolution: FSTEP = FXOSC / 2^19. */
#define RF69_FXOSC_HZ       32000000u
#define RF69_FSTEP_DIVISOR  524288u

/* RegVersion value for the SX1231H used by RF69 / RFM69HCW. */
#define RF69_VERSION_SX1231H 0x24u

typedef enum {
    RF69_REG_FIFO           = 0x00,
    RF69_REG_OPMODE         = 0x01,
    RF69_REG_BITRATE_MSB    = 0x02,
    RF69_REG_BITRATE_LSB    = 0x03,
    RF69_REG_FDEV_MSB       = 0x04,
    RF69_REG_FDEV_LSB       = 0x05,
    RF69_REG_FRF_MSB        = 0x06,
    RF69_REG_FRF_MID        = 0x07,
    RF69_REG_FRF_LSB        = 0x08,
    RF69_REG_PALEVEL        = 0x11,
    RF69_REG_RXBW           = 0x12,
    RF69_REG_VERSION        = 0x10,
    RF69_REG_IRQFLAGS1      = 0x27,
    RF69_REG_IRQFLAGS2      = 0x28,
    RF69_REG_SYNCCONFIG     = 0x2E,
    RF69_REG_SYNCVALUE1     = 0x2F,
    RF69_REG_SYNCVALUE2     = 0x30,
    RF69_REG_PACKETCONFIG1  = 0x37,
    RF69_REG_PAYLOADLENGTH  = 0x38,
    RF69_REG_FIFOTHRESH     = 0x3C,
    RF69_REG_PACKETCONFIG2  = 0x3D,
    RF69_REG_DIOMAPPING1    = 0x40
} rf69_reg_t;

/* SPI address byte: bit 7 selects write, bits 6:0 are the register address. */
#define RF69_SPI_READ(addr)  ((uint8_t)((addr) & 0x7Fu))
#define RF69_SPI_WRITE(addr) ((uint8_t)((addr) | 0x80u))

/* Return 0 when the requested value cannot be represented by the chip. */
uint32_t rf69_frf_from_hz(uint32_t hz);
uint16_t rf69_bitrate_from_bps(uint32_t bps);
uint16_t rf69_fdev_from_hz(uint32_t hz);

#ifdef __cplusplus
}
#endif

#endif /* RF69_REGS_H */
