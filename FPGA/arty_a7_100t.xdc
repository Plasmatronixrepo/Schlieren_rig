## This file is a constraints file for the Arty A7-100T PWM project.

## Clock signal
# The Arty A7 has a 100MHz clock source connected to pin E3
set_property -dict { PACKAGE_PIN E3    IOSTANDARD LVCMOS33 } [get_ports {clk}]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports {clk}]

## Reset Button
# Using BTN0 for reset
set_property -dict { PACKAGE_PIN D9    IOSTANDARD LVCMOS33 } [get_ports {rst}]

## USB-UART Bridge
# The Arty A7's USB-UART bridge is connected to the FPGA on these pins.
# These pins are located on the shield connector as A9 (RX) and D10 (TX).
set_property -dict { PACKAGE_PIN A9    IOSTANDARD LVCMOS33 } [get_ports {uart_rx}]
set_property -dict { PACKAGE_PIN D10   IOSTANDARD LVCMOS33 } [get_ports {uart_tx}]

## PWM Outputs
# These signals can be routed to any of the Pmod connectors or other I/O pins.
# For this example, we will use the top row of the JD Pmod connector.

# Pin 1 of JD Pmod
set_property -dict { PACKAGE_PIN G13   IOSTANDARD LVCMOS33 } [get_ports {trafo_pwm_o}]

# Pin 2 of JD Pmod
set_property -dict { PACKAGE_PIN B11   IOSTANDARD LVCMOS33 } [get_ports {led_pwm_o}]

# Pin 3 of JD Pmod
set_property -dict { PACKAGE_PIN A11   IOSTANDARD LVCMOS33 } [get_ports {camera_pwm_o}]

## LEDs for status indication (Optional)
# You can uncomment these lines and connect them to internal signals for debugging.
# For example, you could tie them to the 'active' signals of the PWM modules.
#set_property -dict { PACKAGE_PIN H5    IOSTANDARD LVCMOS33 } [get_ports {led[0]}]
#set_property -dict { PACKAGE_PIN J5    IOSTANDARD LVCMOS33 } [get_ports {led[1]}]
#set_property -dict { PACKAGE_PIN T9    IOSTANDARD LVCMOS33 } [get_ports {led[2]}]
#set_property -dict { PACKAGE_PIN T10   IOSTANDARD LVCMOS33 } [get_ports {led[3]}]