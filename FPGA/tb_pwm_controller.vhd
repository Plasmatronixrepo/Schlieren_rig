library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tb_pwm_controller is
end tb_pwm_controller;

architecture testbench of tb_pwm_controller is

    -- Component Declaration for the DUT
    component pwm_controller_top
        port (
            clk         : in  std_logic;
            rst         : in  std_logic;
            uart_rx     : in  std_logic;
            uart_tx     : out std_logic;
            trafo_pwm_o : out std_logic;
            led_pwm_o   : out std_logic;
            camera_pwm_o: out std_logic
        );
    end component;

    -- Clock period definition
    constant clk_period : time := 10 ns; -- 100 MHz
    -- Baud period for 115200
    constant baud_period : time := 8680 ns;

    -- Internal signals to connect to the DUT
    -- Note: These do NOT have modes like 'in' or 'out'
    signal clk          : std_logic := '0';
    signal rst          : std_logic := '0';
    signal uart_rx      : std_logic := '1';
    signal uart_tx      : std_logic;
    signal trafo_pwm_o  : std_logic;
    signal led_pwm_o    : std_logic;
    signal camera_pwm_o : std_logic;

begin

    -- Instantiate the Unit Under Test (UUT)
    uut: pwm_controller_top port map (
        clk          => clk,
        rst          => rst,
        uart_rx      => uart_rx,
        uart_tx      => uart_tx,
        trafo_pwm_o  => trafo_pwm_o,
        led_pwm_o    => led_pwm_o,
        camera_pwm_o => camera_pwm_o
    );

    -- Clock process definition
    clk_process :process
    begin
        clk <= '0';
        wait for clk_period/2;
        clk <= '1';
        wait for clk_period/2;
    end process;

    -- Stimulus process
    stim_proc: process
    
        procedure send_uart_byte(data : in std_logic_vector(7 downto 0)) is
        begin
            -- Start bit
            uart_rx <= '0';
            wait for baud_period;
            
            -- Data bits
            for i in 0 to 7 loop
                uart_rx <= data(i);
                wait for baud_period;
            end loop;
            
            -- Stop bit
            uart_rx <= '1';
            wait for baud_period;
        end procedure;

    begin
        -- Reset the system
        rst <= '1';
        wait for 100 ns;
        rst <= '0';
        wait for 1 ms;

        -- Test Case: Configure all PWMs and trigger with a 10ms delay
        report "TESTCASE: Configure all PWMs";

        -- 1. Configure Trafo PWM: Period=100us, Duty=50us, Pulses=5
        send_uart_byte(x"10"); send_uart_byte(x"00"); send_uart_byte(x"64");
        wait for 100 us;
        send_uart_byte(x"11"); send_uart_byte(x"00"); send_uart_byte(x"32");
        wait for 100 us;
        send_uart_byte(x"12"); send_uart_byte(x"05"); send_uart_byte(x"00");
        wait for 100 us;
        
        -- 2. Configure LED PWM: Delay=20us, On-time=500us
        send_uart_byte(x"21"); send_uart_byte(x"00"); send_uart_byte(x"14");
        wait for 100 us;
        send_uart_byte(x"20"); send_uart_byte(x"01"); send_uart_byte(x"F4"); -- 500us
        wait for 100 us;
        
        -- 3. Configure Camera PWM: Delay=1ms, Exposure=10ms
        send_uart_byte(x"31"); send_uart_byte(x"00"); send_uart_byte(x"01");
        wait for 100 us;
        send_uart_byte(x"30"); send_uart_byte(x"00"); send_uart_byte(x"0A");
        wait for 100 us;

        -- 4. Trigger the sequence with a 10ms delay (0x000A)
        report "TESTCASE: Triggering sequence with 10ms delay.";
        send_uart_byte(x"01"); -- CMD_TRIGGER_SEQUENCE
        send_uart_byte(x"00"); -- MSB of delay
        send_uart_byte(x"0A"); -- LSB of delay (10)
        
        -- The sequence should start after 10ms.
        -- We can wait here and observe the waveforms in the simulator.
        
        wait for 20 ms;
        
        report "TESTCASE: End of simulation.";
        wait;
    end process;

end testbench;
