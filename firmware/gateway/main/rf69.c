#include "rf69.h"

#include <string.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "rf69";
static spi_device_handle_t s_device;
static bool s_initialized;

/* GPIO19/20: native USB. GPIO26-32: module flash/PSRAM.
 * GPIO35-37: flash/PSRAM on octal SPI module variants (Espressif user guide). */
static bool pin_is_available(int pin)
{
    return pin >= 0 && pin <= 48 && pin != 19 && pin != 20
           && (pin < 26 || pin > 32) && (pin < 35 || pin > 37);
}

static esp_err_t transfer(uint8_t address_byte, bool is_write, uint8_t *value)
{
    uint8_t out[2] = { address_byte, 0u };
    uint8_t in[2] = { 0u, 0u };

    spi_transaction_t transaction;
    memset(&transaction, 0, sizeof(transaction));
    transaction.length = 16;
    transaction.tx_buffer = out;
    transaction.rx_buffer = in;

    esp_err_t err = spi_device_transmit(s_device, &transaction);
    if (err != ESP_OK) {
        return err;
    }

    if (!is_write && value != NULL) {
        *value = in[1];
    }
    return ESP_OK;
}

esp_err_t rf69_init(const rf69_config_t *cfg)
{
    if (cfg == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    const int pins[] = {
        cfg->sck_gpio, cfg->miso_gpio, cfg->mosi_gpio,
        cfg->nss_gpio, cfg->dio0_gpio, cfg->reset_gpio
    };
    for (size_t i = 0; i < sizeof(pins) / sizeof(pins[0]); ++i) {
        if (!pin_is_available(pins[i])) {
            ESP_LOGE(TAG, "GPIO %d is reserved for USB, flash or PSRAM", pins[i]);
            return ESP_ERR_INVALID_ARG;
        }
    }

    if (!s_initialized) {
        spi_bus_config_t bus = {
            .sclk_io_num = cfg->sck_gpio,
            .miso_io_num = cfg->miso_gpio,
            .mosi_io_num = cfg->mosi_gpio,
            .quadwp_io_num = -1,
            .quadhd_io_num = -1,
            .max_transfer_sz = 64,
        };
        esp_err_t err = spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_DISABLED);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "spi_bus_initialize failed: %s", esp_err_to_name(err));
            return err;
        }

        spi_device_interface_config_t device = {
            .clock_speed_hz = 1000000,
            .mode = 0,
            .spics_io_num = cfg->nss_gpio,
            .queue_size = 4,
        };
        err = spi_bus_add_device(SPI2_HOST, &device, &s_device);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "spi_bus_add_device failed: %s", esp_err_to_name(err));
            return err;
        }
        s_initialized = true;
    }

    gpio_reset_pin(cfg->reset_gpio);
    gpio_set_direction(cfg->reset_gpio, GPIO_MODE_OUTPUT);
    gpio_set_level(cfg->reset_gpio, 0);
    vTaskDelay(pdMS_TO_TICKS(1));
    gpio_set_level(cfg->reset_gpio, 1);
    vTaskDelay(pdMS_TO_TICKS(5));

    return ESP_OK;
}

void rf69_deinit(void)
{
    if (s_initialized) {
        spi_bus_remove_device(s_device);
        spi_bus_free(SPI2_HOST);
        s_device = NULL;
        s_initialized = false;
    }
}

esp_err_t rf69_read(uint8_t addr, uint8_t *value)
{
    if (!s_initialized || value == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    return transfer(RF69_SPI_READ(addr), false, value);
}

esp_err_t rf69_write(uint8_t addr, uint8_t value)
{
    if (!s_initialized) {
        return ESP_ERR_INVALID_STATE;
    }
    return transfer(RF69_SPI_WRITE(addr), true, NULL);
}

esp_err_t rf69_read_version(uint8_t *version)
{
    return rf69_read(RF69_REG_VERSION, version);
}

esp_err_t rf69_configure_fsk(const rf69_config_t *cfg)
{
    if (cfg == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    uint32_t frf = rf69_frf_from_hz(cfg->freq_hz);
    uint16_t bitrate = rf69_bitrate_from_bps(cfg->bitrate_bps);
    uint16_t fdev = rf69_fdev_from_hz(cfg->fdev_hz);
    if (frf == 0u || bitrate == 0u || fdev == 0u) {
        ESP_LOGE(TAG, "air parameters are out of range");
        return ESP_ERR_INVALID_ARG;
    }

    esp_err_t err = rf69_write(RF69_REG_FRF_MSB, (uint8_t)(frf >> 16));
    if (err != ESP_OK) return err;
    err = rf69_write(RF69_REG_FRF_MID, (uint8_t)(frf >> 8));
    if (err != ESP_OK) return err;
    err = rf69_write(RF69_REG_FRF_LSB, (uint8_t)frf);
    if (err != ESP_OK) return err;

    err = rf69_write(RF69_REG_BITRATE_MSB, (uint8_t)(bitrate >> 8));
    if (err != ESP_OK) return err;
    err = rf69_write(RF69_REG_BITRATE_LSB, (uint8_t)bitrate);
    if (err != ESP_OK) return err;

    err = rf69_write(RF69_REG_FDEV_MSB, (uint8_t)(fdev >> 8));
    if (err != ESP_OK) return err;
    err = rf69_write(RF69_REG_FDEV_LSB, (uint8_t)fdev);
    if (err != ESP_OK) return err;

    /* Bits 1:0 select the frequency band; 0b11 is 915 MHz. */
    uint8_t band = (cfg->freq_hz >= 900000000u) ? 0x03u
                   : (cfg->freq_hz >= 850000000u) ? 0x02u
                   : (cfg->freq_hz >= 400000000u) ? 0x01u : 0x00u;
    err = rf69_write(RF69_REG_OPMODE, 0x01u | band);  /* FSK, standby */
    if (err != ESP_OK) return err;

    ESP_LOGI(TAG, "FSK configured: frf=0x%06lx bitrate=0x%04x fdev=0x%04x",
             (unsigned long)frf, bitrate, fdev);
    return ESP_OK;
}
