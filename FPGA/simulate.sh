#!/bin/bash

# Clean up previous simulation files
rm -f *.cf *.vcd

# Step 1: Analyze (compile) all VHDL files using the VHDL-2008 standard.
echo "Analyzing VHDL files..."
ghdl -a --std=08 uart.vhd
ghdl -a --std=08 sequence_trigger.vhd
ghdl -a --std=08 trafo_pwm.vhd
ghdl -a --std=08 led_pwm.vhd
ghdl -a --std=08 camera_pwm.vhd
ghdl -a --std=08 pwm_control.vhd
ghdl -a --std=08 pwm_controller_top.vhd
ghdl -a --std=08 tb_pwm_controller.vhd

# Step 2: Elaborate the top-level testbench.
echo "Elaborating the testbench..."
ghdl -e --std=08 tb_pwm_controller

# Step 3: Run the simulation.
echo "Running the simulation..."
ghdl -r --std=08 tb_pwm_controller --vcd=wave.vcd

# Step 4: Open the waveform in GTKWave.
echo "Simulation finished. Opening GTKWave..."
gtkwave wave.vcd