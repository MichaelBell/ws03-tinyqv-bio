# SRAM macros

define_pdn_grid \
    -macro \
    -instances i_chip_core.tt.i_tinyqv.cpu.i_scratch.i_sram \
    -name sram_macros_NS \
    -starts_with POWER \
    -halo "$::env(PDN_HORIZONTAL_HALO) $::env(PDN_VERTICAL_HALO)"

add_pdn_connect \
    -grid sram_macros_NS \
    -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"

add_pdn_connect \
    -grid sram_macros_NS \
    -layers "$::env(PDN_VERTICAL_LAYER) Metal3"

# Add stripes on W/E edges of SRAM
add_pdn_stripe \
    -grid sram_macros_NS \
    -layer Metal4 \
    -width 1.36 \
    -offset 0.68 \
    -spacing 0.28 \
    -pitch 298.30 \
    -starts_with GROUND \
    -number_of_straps 2

# Since the above stripes block the top level PDN at Metal4, add some more stripes
# to improve the PDN's integrity and ensure a better connection for the macro.
add_pdn_stripe \
    -grid sram_macros_NS \
    -layer Metal4 \
    -width 4.00 \
    -offset 50.80 \
    -spacing 0.28 \
    -pitch 48.86 \
    -starts_with GROUND \
    -number_of_straps 5

define_pdn_grid \
    -macro \
    -instances {i_chip_core.tt.i_bio.*.i_femto_bio_core.i_femtoram.i_ram.ram1024.sram_0 i_chip_core.tt.i_bio.*.i_femto_bio_core.i_femtoram.i_ram.ram1024.sram_1} \
    -name sram_macros_WE \
    -starts_with POWER \
    -halo "$::env(PDN_HORIZONTAL_HALO) $::env(PDN_VERTICAL_HALO)"

add_pdn_connect \
    -grid sram_macros_WE \
    -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"

add_pdn_connect \
    -grid sram_macros_WE \
    -layers "$::env(PDN_VERTICAL_LAYER) Metal3"

# Add stripes on W/E edges of SRAM
add_pdn_stripe \
    -grid sram_macros_WE \
    -layer Metal4 \
    -width 1.36 \
    -offset 0.68 \
    -spacing 0.28 \
    -pitch 512.81 \
    -starts_with POWER \
    -number_of_straps 1

add_pdn_stripe \
    -grid sram_macros_WE \
    -layer Metal4 \
    -width 1.36 \
    -offset 508.49 \
    -spacing 0.28 \
    -pitch 5.0 \
    -starts_with GROUND \
    -number_of_straps 2

# Since the above stripes block the top level PDN at Metal4, add some more stripes
# to improve the PDN's integrity and ensure a better connection for the macro.
add_pdn_stripe \
    -grid sram_macros_WE \
    -layer Metal4 \
    -width 4.00 \
    -offset 28.0 \
    -spacing 0.28 \
    -pitch 45.98 \
    -starts_with GROUND \
    -number_of_straps 11
