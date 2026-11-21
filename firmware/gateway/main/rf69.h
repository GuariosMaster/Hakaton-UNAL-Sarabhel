#ifndef RF69_H
#define RF69_H

#include <stdint.h>

#include "esp_err.h"
#include "rf69_regs.h"

typedef struct {
    int sck_gpio;
    int miso_gpio;
    int mosi_gpio;
    int nss_gpio;
    int dio0_gpio;
    int reset_gpio;
    uint32_t freq_hz;
    uint32_t bitrate_bps;
    uint32_t fdev_hz;
} rf69_config_t;

esp_err_t rf69_init(const rf69_config_t *cfg);
void rf69_deinit(void);
esp_err_t rf69_read(uint8_t addr, uint8_t *value);
esp_err_t rf69_write(uint8_t addr, uint8_t value);
esp_err_t rf69_read_version(uint8_t *version);
esp_err_t rf69_configure_fsk(const rf69_config_t *cfg);

#endif /* RF69_H */
