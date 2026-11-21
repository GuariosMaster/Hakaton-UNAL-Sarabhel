idf_component_register(
    SRCS "gateway_main.c" "rf69.c" "rf69_regs.c" "pin_sweep.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_driver_gpio esp_driver_spi
)
