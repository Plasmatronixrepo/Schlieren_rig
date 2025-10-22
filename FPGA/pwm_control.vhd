library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity pwm_control is
    port (
        clk                 : in  std_logic;
        rst                 : in  std_logic;
        rx_data_i           : in  std_logic_vector(7 downto 0);
        rx_data_valid_i     : in  std_logic;
        tx_data_o           : out std_logic_vector(7 downto 0);
        tx_start_o          : out std_logic;
        tx_busy_i           : in  std_logic;

        trigger_sequence_o  : out std_logic;
        sequence_delay_ms_o : out std_logic_vector(15 downto 0);
        trafo_period_o      : out std_logic_vector(15 downto 0);
        trafo_duty_o        : out std_logic_vector(15 downto 0);
        trafo_pulse_count_o : out std_logic_vector(4 downto 0);
        led_on_time_o       : out std_logic_vector(15 downto 0);
        led_delay_o         : out std_logic_vector(15 downto 0);
        camera_on_time_o    : out std_logic_vector(23 downto 0);
        -- **MODIFIED**: Port renamed to reflect microsecond precision
        camera_delay_us_o   : out std_logic_vector(15 downto 0)
    );
end pwm_control;

architecture Behavioral of pwm_control is

    -- State machine designed to guarantee data is stable before trigger is asserted.
    type state_t is (IDLE, RECEIVE_DATA_1, RECEIVE_DATA_2, ASSERT_TRIGGER, SEND_ACK);
    signal state : state_t := IDLE;

    -- Command definitions
    constant CMD_TRIGGER_SEQUENCE     : std_logic_vector(7 downto 0) := x"01";
    constant CMD_SET_TRAFO_PERIOD       : std_logic_vector(7 downto 0) := x"10";
    constant CMD_SET_TRAFO_DUTY         : std_logic_vector(7 downto 0) := x"11";
    constant CMD_SET_TRAFO_PULSE_COUNT  : std_logic_vector(7 downto 0) := x"12";
    constant CMD_SET_LED_ON_TIME        : std_logic_vector(7 downto 0) := x"20";
    constant CMD_SET_LED_DELAY          : std_logic_vector(7 downto 0) := x"21";
    constant CMD_SET_CAMERA_ON_TIME     : std_logic_vector(7 downto 0) := x"30";
    constant CMD_SET_CAMERA_DELAY       : std_logic_vector(7 downto 0) := x"31";

    -- Internal registers to hold all configuration values stably.
    signal command_reg          : std_logic_vector(7 downto 0);
    signal data_reg_1           : std_logic_vector(7 downto 0);
    signal sequence_delay_ms_s  : std_logic_vector(15 downto 0) := (others => '0');
    signal trafo_period_s       : std_logic_vector(15 downto 0) := (others => '0');
    signal trafo_duty_s         : std_logic_vector(15 downto 0) := (others => '0');
    signal trafo_pulse_count_s  : std_logic_vector(4 downto 0)  := (others => '0');
    signal led_on_time_s        : std_logic_vector(15 downto 0) := (others => '0');
    signal led_delay_s          : std_logic_vector(15 downto 0) := (others => '0');
    signal camera_on_time_s     : std_logic_vector(23 downto 0) := (others => '0');
    -- **MODIFIED**: Internal signal renamed
    signal camera_delay_us_s    : std_logic_vector(15 downto 0) := (others => '0');

begin

    -- The trigger is asserted combinatorially only during the ASSERT_TRIGGER state.
    trigger_sequence_o  <= '1' when state = ASSERT_TRIGGER else '0';
    
    -- All data outputs are driven continuously and stably from internal registers.
    sequence_delay_ms_o <= sequence_delay_ms_s;
    trafo_period_o      <= trafo_period_s;
    trafo_duty_o        <= trafo_duty_s;
    trafo_pulse_count_o <= trafo_pulse_count_s;
    led_on_time_o       <= led_on_time_s;
    led_delay_o         <= led_delay_s;
    camera_on_time_o    <= camera_on_time_s;
    -- **MODIFIED**: Mapped new internal signal to renamed port
    camera_delay_us_o   <= camera_delay_us_s;
    
    process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state <= IDLE;
                tx_start_o <= '0';
                -- Reset all internal config registers
                sequence_delay_ms_s <= (others => '0');
                trafo_period_s      <= (others => '0');
                trafo_duty_s        <= (others => '0');
                trafo_pulse_count_s <= (others => '0');
                led_on_time_s       <= (others => '0');
                led_delay_s         <= (others => '0');
                camera_on_time_s    <= (others => '0');
                camera_delay_us_s   <= (others => '0');
            else
                tx_start_o <= '0';

                case state is
                    when IDLE =>
                        if rx_data_valid_i = '1' then
                            command_reg <= rx_data_i;
                            state <= RECEIVE_DATA_1;
                        end if;

                    when RECEIVE_DATA_1 =>
                        if rx_data_valid_i = '1' then
                            data_reg_1 <= rx_data_i;
                            state <= RECEIVE_DATA_2;
                        end if;

                    when RECEIVE_DATA_2 =>
                        if rx_data_valid_i = '1' then
                            -- This is the cycle where the data register is updated.
                            case command_reg is
                                when CMD_TRIGGER_SEQUENCE =>
                                    sequence_delay_ms_s <= data_reg_1 & rx_data_i;
                                    state <= ASSERT_TRIGGER; -- On the next cycle, we will trigger.
                                when CMD_SET_TRAFO_PERIOD =>
                                    trafo_period_s <= data_reg_1 & rx_data_i;
                                    state <= SEND_ACK;
                                when CMD_SET_TRAFO_DUTY =>
                                    trafo_duty_s <= data_reg_1 & rx_data_i;
                                    state <= SEND_ACK;
                                when CMD_SET_TRAFO_PULSE_COUNT =>
                                    trafo_pulse_count_s <= data_reg_1(4 downto 0);
                                    state <= SEND_ACK;
                                when CMD_SET_LED_ON_TIME =>
                                    led_on_time_s <= data_reg_1 & rx_data_i;
                                    state <= SEND_ACK;
                                when CMD_SET_LED_DELAY =>
                                    led_delay_s <= data_reg_1 & rx_data_i;
                                    state <= SEND_ACK;
                                when CMD_SET_CAMERA_ON_TIME =>
                                    camera_on_time_s <= x"00" & data_reg_1 & rx_data_i;
                                    state <= SEND_ACK;
                                when CMD_SET_CAMERA_DELAY =>
                                    -- **MODIFIED**: Assignment now goes to the renamed signal
                                    camera_delay_us_s <= data_reg_1 & rx_data_i;
                                    state <= SEND_ACK;
                                when others =>
                                    state <= SEND_ACK;
                            end case;
                        end if;
                        
                    when ASSERT_TRIGGER =>
                        -- This state lasts for exactly one clock cycle, creating the trigger pulse.
                        -- The data has been stable for a full cycle at this point.
                        state <= SEND_ACK;
                        
                    when SEND_ACK =>
                        if tx_busy_i = '0' then
                            tx_data_o <= command_reg;
                            tx_start_o <= '1';
                            state <= IDLE;
                        end if;
                end case;
            end if;
        end if;
    end process;
end Behavioral;
