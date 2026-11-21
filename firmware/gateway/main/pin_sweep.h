#ifndef PIN_SWEEP_H
#define PIN_SWEEP_H

#include <stdbool.h>

typedef struct {
    bool found;
    int sck;
    int miso;
    int mosi;
    int nss;
    unsigned combinations;
    unsigned single_hits;
} pin_sweep_result_t;

void pin_sweep_run(pin_sweep_result_t *result);

#endif /* PIN_SWEEP_H */
