#include "pin_sweep.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "pin_sweep";

/* Header GPIOs on DevKitC-1, excluding USB (19/20), flash/PSRAM (26-32,
 * 35-37), UART (43/44) and strapping pins (0/45/46). */
static const int kPins[] = {
     2,  3,  4,  5,  6,  7,  8,  9,
    10, 11, 12, 13, 14, 16, 17, 18,
    21, 33, 34, 38, 39, 40, 41, 42,
    47, 48,
};
#define PIN_COUNT (sizeof(kPins) / sizeof(kPins[0]))
#define VERSION_VALUE 0x24u
#define VERSION_ADDR  0x10u

static inline void half_cycle(void)
{
    for (volatile int i = 0; i < 12; ++i) {
        /* delay */
    }
}

/* Bit-banged SPI mode 0 read of one register. No peripheral state is kept,
 * so any pin can be tried without reinitialising the SPI driver. */
static uint8_t read_version(int sck, int miso, int mosi, int nss)
{
    gpio_set_direction(nss, GPIO_MODE_OUTPUT);
    gpio_set_direction(sck, GPIO_MODE_OUTPUT);
    gpio_set_direction(mosi, GPIO_MODE_OUTPUT);
    gpio_set_direction(miso, GPIO_MODE_INPUT);
    gpio_set_pull_mode(miso, GPIO_PULLDOWN_ONLY);

    gpio_set_level(sck, 0);
    gpio_set_level(nss, 1);
    half_cycle();
    gpio_set_level(nss, 0);
    half_cycle();

    for (int bit = 7; bit >= 0; --bit) {
        gpio_set_level(mosi, (VERSION_ADDR >> bit) & 1u);
        half_cycle();
        gpio_set_level(sck, 1);
        half_cycle();
        gpio_set_level(sck, 0);
        half_cycle();
    }

    uint8_t value = 0u;
    for (int bit = 7; bit >= 0; --bit) {
        gpio_set_level(mosi, 0);
        half_cycle();
        gpio_set_level(sck, 1);
        half_cycle();
        value = (uint8_t)((value << 1) | (gpio_get_level(miso) & 1u));
        gpio_set_level(sck, 0);
        half_cycle();
    }

    gpio_set_level(nss, 1);
    return value;
}

void pin_sweep_run(pin_sweep_result_t *result)
{
    if (result == NULL) {
        return;
    }
    result->found = false;
    result->combinations = 0u;
    result->single_hits = 0u;

    ESP_LOGI(TAG, "sweeping %u candidate GPIOs for an RF69 answer (0x%02X)",
             (unsigned)PIN_COUNT, VERSION_VALUE);

    for (size_t a = 0; a < PIN_COUNT; ++a) {
        const int nss = kPins[a];
        for (size_t b = 0; b < PIN_COUNT; ++b) {
            const int sck = kPins[b];
            if (sck == nss) continue;
            for (size_t c = 0; c < PIN_COUNT; ++c) {
                const int mosi = kPins[c];
                if (mosi == nss || mosi == sck) continue;
                for (size_t d = 0; d < PIN_COUNT; ++d) {
                    const int miso = kPins[d];
                    if (miso == nss || miso == sck || miso == mosi) continue;

                    result->combinations++;
                    if (read_version(sck, miso, mosi, nss) != VERSION_VALUE) {
                        continue;
                    }
                    result->single_hits++;

                    /* Confirm three independent reads before accepting a hit. */
                    if (read_version(sck, miso, mosi, nss) == VERSION_VALUE &&
                        read_version(sck, miso, mosi, nss) == VERSION_VALUE) {
                        result->found = true;
                        result->sck = sck;
                        result->miso = miso;
                        result->mosi = mosi;
                        result->nss = nss;
                        ESP_LOGI(TAG, "MATCH: SCK=%d MISO=%d MOSI=%d NSS=%d",
                                 sck, miso, mosi, nss);
                        return;
                    }
                }
            }
        }
    }

    ESP_LOGI(TAG, "sweep finished: %u combinations, %u single 0x24 hits, no confirmed match",
             result->combinations, result->single_hits);
}
