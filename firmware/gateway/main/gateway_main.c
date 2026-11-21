#include "esp_log.h"
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "pin_sweep.h"
#include "rf69.h"

static const char *TAG = "gateway";

static bool configured_pinout_works(rf69_config_t *cfg)
{
    esp_err_t err = rf69_init(cfg);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "configured pinout init failed: %s", esp_err_to_name(err));
        rf69_deinit();
        return false;
    }
    uint8_t version = 0u;
    err = rf69_read_version(&version);
    if (err == ESP_OK && version == RF69_VERSION_SX1231H) {
        return true;
    }
    ESP_LOGW(TAG, "configured pinout SCK=%d MISO=%d MOSI=%d NSS=%d -> RegVersion=0x%02X%s; "
                  "falling back to software pin sweep",
             cfg->sck_gpio, cfg->miso_gpio, cfg->mosi_gpio, cfg->nss_gpio, version,
             err != ESP_OK ? " (read failed)" : "");
    rf69_deinit();
    return false;
}

void app_main(void)
{
    rf69_config_t cfg = {
        .sck_gpio   = CONFIG_RF69_SPI_SCK_GPIO,
        .miso_gpio  = CONFIG_RF69_SPI_MISO_GPIO,
        .mosi_gpio  = CONFIG_RF69_SPI_MOSI_GPIO,
        .nss_gpio   = CONFIG_RF69_SPI_NSS_GPIO,
        .dio0_gpio  = CONFIG_RF69_DIO0_GPIO,
        .reset_gpio = CONFIG_RF69_RESET_GPIO,
        .freq_hz    = CONFIG_RF69_FREQ_HZ,
        .bitrate_bps = CONFIG_RF69_BITRATE_BPS,
        .fdev_hz    = CONFIG_RF69_FDEV_HZ,
    };

    ESP_LOGI(TAG, "ESP32-S3 RF69 FSK 915 MHz gateway - probe stage");
    ESP_LOGI(TAG, "wiring: SCK=%d MISO=%d MOSI=%d NSS=%d DIO0=%d RESET=%d",
             cfg.sck_gpio, cfg.miso_gpio, cfg.mosi_gpio,
             cfg.nss_gpio, cfg.dio0_gpio, cfg.reset_gpio);

    if (!configured_pinout_works(&cfg)) {
        pin_sweep_result_t sweep;
        pin_sweep_run(&sweep);
        if (sweep.found) {
            cfg.sck_gpio  = sweep.sck;
            cfg.miso_gpio = sweep.miso;
            cfg.mosi_gpio = sweep.mosi;
            cfg.nss_gpio  = sweep.nss;
            ESP_LOGI(TAG, "using swept pinout: SCK=%d MISO=%d MOSI=%d NSS=%d",
                     cfg.sck_gpio, cfg.miso_gpio, cfg.mosi_gpio, cfg.nss_gpio);
        } else {
            ESP_LOGE(TAG, "No pinout returned RegVersion=0x%02X. Check 3.3V/GND on the RF module.",
                     RF69_VERSION_SX1231H);
        }
    }

    esp_err_t err = rf69_init(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "RF69 init failed: %s", esp_err_to_name(err));
        return;
    }

    uint8_t version = 0u;
    err = rf69_read_version(&version);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "RegVersion read failed: %s", esp_err_to_name(err));
        return;
    }

    if (version == RF69_VERSION_SX1231H) {
        ESP_LOGI(TAG, "SX1231H detected (RegVersion=0x%02X): SPI and pinout look correct",
                 version);
    } else {
        ESP_LOGE(TAG, "Unexpected RegVersion=0x%02X (expected 0x%02X): "
                      "check the RF module identity and the wiring",
                 version, RF69_VERSION_SX1231H);
    }

#if CONFIG_RF69_APPLY_CONFIG
    err = rf69_configure_fsk(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "FSK configuration failed: %s", esp_err_to_name(err));
        return;
    }
#else
    ESP_LOGI(TAG, "radio configuration not applied (enable RF69_APPLY_CONFIG in menuconfig)");
#endif

    while (1) {
        ESP_LOGI(TAG, "alive - waiting for peer node parameters");
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
