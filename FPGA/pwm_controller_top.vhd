library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity pwm_controller_top is
    Port (
        clk         : in  std_logic;
        rst         : in  std_logic;
        uart_rx     : in  std_logic;
        uart_tx     : out std_logic;
        trafo_pwm_o : out std_logic;
        led_pwm_o   : out std_logic;
        camera_pwm_o: out std_logic
    );
end pwm_controller_top;

architecture Behavioral of pwm_controller_top is
    
    constant CLK_FREQ_HZ : integer := 100_000_000;

    -- UART signals
    signal rx_data      : std_logic_vector(7 downto 0);
    signal rx_data_valid: std_logic;
    signal tx_data      : std_logic_vector(7 downto 0);
    signal tx_start     : std_logic;
    signal tx_busy      : std_logic;
    
    -- Trigger signals
    signal trigger_sequence  : std_logic;
    signal sequence_delay_ms : std_logic_vector(15 downto 0);
    signal trafo_start_pulse : std_logic;

    -- PWM config signals
    signal trafo_period     : std_logic_vector(15 downto 0);
    signal trafo_duty       : std_logic_vector(15 downto 0);
    signal trafo_pulse_count: std_logic_vector(4 downto 0);
    signal led_on_time      : std_logic_vector(15 downto 0);
    signal led_delay        : std_logic_vector(15 downto 0);
    signal camera_on_time   : std_logic_vector(23 downto 0);
    -- **MODIFIED**: Signal renamed to reflect microsecond precision
    signal camera_delay_us  : std_logic_vector(15 downto 0);
    
    -- PWM status signals
    signal trafo_active : std_logic;
    signal led_active   : std_logic;

begin

    -- UART Module Instantiation
    uart_inst : entity work.uart
    generic map (
        CLK_FREQ_HZ => CLK_FREQ_HZ,
        BAUD_RATE   => 115200
    )
    port map (
        clk         => clk,
        rst         => rst,
        rx_i        => uart_rx,
        tx_o        => uart_tx,
        rx_data_o   => rx_data,
        rx_valid_o  => rx_data_valid,
        tx_data_i   => tx_data,
        tx_start_i  => tx_start,
        tx_busy_o   => tx_busy
    );

    -- Command Control Module Instantiation
    pwm_control_inst : entity work.pwm_control
    port map (
        clk                 => clk,
        rst                 => rst,
        rx_data_i           => rx_data,
        rx_data_valid_i     => rx_data_valid,
        tx_data_o           => tx_data,
        tx_start_o          => tx_start,
        tx_busy_i           => tx_busy,
        trigger_sequence_o  => trigger_sequence,
        sequence_delay_ms_o => sequence_delay_ms,
        trafo_period_o      => trafo_period,
        trafo_duty_o        => trafo_duty,
        trafo_pulse_count_o => trafo_pulse_count,
        led_on_time_o       => led_on_time,
        led_delay_o         => led_delay,
        camera_on_time_o    => camera_on_time,
        -- **MODIFIED**: Mapped to the renamed port
        camera_delay_us_o   => camera_delay_us
    );
    
    -- Sequence Trigger Module Instantiation
    seq_trigger_inst : entity work.sequence_trigger
    generic map (
        CLK_FREQ_HZ => CLK_FREQ_HZ
    )
    port map (
        clk           => clk,
        rst           => rst,
        trigger_i     => trigger_sequence,
        delay_ms_i    => sequence_delay_ms,
        start_pulse_o => trafo_start_pulse
    );

    -- Trafo PWM Generator Instantiation
    trafo_pwm_inst : entity work.trafo_pwm
    generic map (
        CLK_FREQ_HZ => CLK_FREQ_HZ
    )
    port map (
        clk          => clk,
        rst          => rst,
        period_us_i  => trafo_period,
        duty_us_i    => trafo_duty,
        pulse_count_i=> trafo_pulse_count,
        start_i      => trafo_start_pulse,
        pwm_o        => trafo_pwm_o,
        active_o     => trafo_active
    );
    
    -- LED PWM Generator Instantiation
    led_pwm_inst : entity work.led_pwm
    generic map (
        CLK_FREQ_HZ => CLK_FREQ_HZ
    )
    port map (
        clk              => clk,
        rst              => rst,
        on_time_us_i     => led_on_time,
        delay_us_i       => led_delay,
        trafo_active_i   => trafo_active,
        pwm_o            => led_pwm_o,
        led_active_o     => led_active
    );
    
    -- Camera PWM Generator Instantiation
    camera_pwm_inst : entity work.camera_pwm
    generic map (
        CLK_FREQ_HZ => CLK_FREQ_HZ
    )
    port map (
        clk              => clk,
        rst              => rst,
        exposure_ms_i    => camera_on_time,
        -- **MODIFIED**: Mapped to the renamed port
        delay_us_i       => camera_delay_us,
        led_active_i     => led_active,
        pwm_o            => camera_pwm_o
    );

end Behavioral;
