library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity trafo_pwm is
    generic (
        CLK_FREQ_HZ : integer := 100_000_000
    );
    port (
        clk           : in  std_logic;
        rst           : in  std_logic;
        period_us_i   : in  std_logic_vector(15 downto 0);
        duty_us_i     : in  std_logic_vector(15 downto 0);
        pulse_count_i : in  std_logic_vector(4 downto 0);
        start_i       : in  std_logic;
        pwm_o         : out std_logic;
        active_o      : out std_logic
    );
end trafo_pwm;

architecture Behavioral of trafo_pwm is
    constant CLKS_PER_US : integer := CLK_FREQ_HZ / 1_000_000;

    type state_t is (IDLE, ACTIVE);
    signal state : state_t := IDLE;

    signal period_clks_reg : unsigned(23 downto 0) := (others => '0');
    signal duty_clks_reg   : unsigned(23 downto 0) := (others => '0');
    signal pulse_count_reg : unsigned(4 downto 0)  := (others => '0');
    signal counter         : unsigned(23 downto 0) := (others => '0');

begin
    process(clk)
        -- Use variables for immediate calculation inside the process.
        variable calc_period_clks : unsigned(23 downto 0);
        variable calc_duty_clks   : unsigned(23 downto 0);
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state <= IDLE;
                counter <= (others => '0');
                period_clks_reg <= (others => '0');
                duty_clks_reg <= (others => '0');
                pulse_count_reg <= (others => '0');
            else
                case state is
                    when IDLE =>
                        if start_i = '1' then
                            -- Calculations are now safely inside the clocked process.
                            calc_period_clks := resize((unsigned(period_us_i) * CLKS_PER_US), period_clks_reg'length);
                            calc_duty_clks   := resize((unsigned(duty_us_i) * CLKS_PER_US), duty_clks_reg'length);
                            
                            period_clks_reg <= calc_period_clks;
                            duty_clks_reg   <= calc_duty_clks;
                            pulse_count_reg <= unsigned(pulse_count_i);
                            
                            counter <= (others => '0');
                            if unsigned(pulse_count_i) > 0 then
                                state <= ACTIVE;
                            end if;
                        end if;

                    when ACTIVE =>
                        if pulse_count_reg > 0 and period_clks_reg > 0 then
                            if counter + 1 >= period_clks_reg then
                                counter <= (others => '0');
                                pulse_count_reg <= pulse_count_reg - 1;
                            else
                                counter <= counter + 1;
                            end if;
                        else
                            state <= IDLE;
                        end if;
                end case;

                if state = ACTIVE and pulse_count_reg > 0 then
                    active_o <= '1';
                    if counter < duty_clks_reg then
                        pwm_o <= '1';
                    else
                        pwm_o <= '0';
                    end if;
                else
                    active_o <= '0';
                    pwm_o <= '0';
                end if;
            end if;
        end if;
    end process;
end Behavioral;
