#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

cc -std=c11 -Wall -Wextra -Werror -O2 \
    -o "$scratch/test_rf69_regs" \
    test_rf69_regs.c ../main/rf69_regs.c

"$scratch/test_rf69_regs"
