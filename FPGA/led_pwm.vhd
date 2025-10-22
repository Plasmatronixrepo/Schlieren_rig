library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity led_pwm is
    generic (
        CLK_FREQ_HZ : integer := 100_000_000
    );
    port (
        clk            : in  std_logic;
        rst            : in  std_logic;
        on_time_us_i   : in  std_logic_vector(15 downto 0);
        delay_us_i     : in  std_logic_vector(15 downto 0);
        trafo_active_i : in  std_logic;
        pwm_o          : out std_logic;
        led_active_o   : out std_logic
    );
end led_pwm;

architecture Behavioral of led_pwm is
    constant CLKS_PER_US : integer := CLK_FREQ_HZ / 1_000_000;
    
    type state_t is (IDLE, DELAY, ON_TIME);
    signal state : state_t := IDLE;

    signal delay_clks_reg   : unsigned(23 downto 0) := (others => '0');
    signal on_time_clks_reg : unsigned(23 downto 0) := (others => '0');
    signal counter          : unsigned(23 downto 0) := (others => '0');
    
    signal trafo_active_prev : std_logic := '0';

begin
    process(clk)
        variable trafo_start_edge : boolean;
    begin
        if rising_edge(clk) then
            trafo_active_prev <= trafo_active_i;
            trafo_start_edge := (trafo_active_i = '1' and trafo_active_prev = '0');

            if rst = '1' then
                state <= IDLE;
                trafo_active_prev <= '0';
            else
                case state is
                    when IDLE =>
                        if trafo_start_edge then
                           delay_clks_reg   <= resize((unsigned(delay_us_i) * CLKS_PER_US), delay_clks_reg'length);
                           on_time_clks_reg <= resize((unsigned(on_time_us_i) * CLKS_PER_US), on_time_clks_reg'length);
                           counter <= (others => '0');
                           state <= DELAY;
                        end if;
                    
                    when DELAY =>
                        if counter + 1 >= delay_clks_reg then
                            counter <= (others => '0');
                            state <= ON_TIME;
                        else
                            counter <= counter + 1;
                        end if;
                        
                    when ON_TIME =>
                        if counter + 1 >= on_time_clks_reg then
                            state <= IDLE;
                        else
                            counter <= counter + 1;
                        end if;
                end case;

                if state = ON_TIME then
                    pwm_o <= '1';
                    led_active_o <= '1';
                else
                    pwm_o <= '0';
                    led_active_o <= '0';
                end if;

                if trafo_active_i = '0' and state /= IDLE then
                    state <= IDLE;
                end if;
            end if;
        end if;
    end process;
end Behavioral;
