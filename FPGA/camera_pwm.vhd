library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity camera_pwm is
    generic (
        CLK_FREQ_HZ : integer := 100_000_000
    );
    port (
        clk           : in  std_logic;
        rst           : in  std_logic;
        exposure_ms_i : in  std_logic_vector(23 downto 0);
        -- **MODIFIED**: Port renamed and now represents microseconds
        delay_us_i    : in  std_logic_vector(15 downto 0);
        led_active_i  : in  std_logic;
        pwm_o         : out std_logic
    );
end camera_pwm;

architecture Behavioral of camera_pwm is
    -- **MODIFIED**: Changed constant to calculate clock cycles per microsecond
    constant CLKS_PER_US : integer := CLK_FREQ_HZ / 1_000_000;
    constant CLKS_PER_MS : integer := CLK_FREQ_HZ / 1_000;

    type state_t is (IDLE, DELAY, EXPOSURE);
    signal state : state_t := IDLE;

    signal delay_clks_reg    : unsigned(31 downto 0) := (others => '0');
    signal exposure_clks_reg : unsigned(31 downto 0) := (others => '0');
    signal counter           : unsigned(31 downto 0) := (others => '0');
    
    signal led_active_prev : std_logic := '0';

begin
    process(clk)
        variable led_start_edge : boolean;
    begin
        if rising_edge(clk) then
            led_active_prev <= led_active_i;
            led_start_edge := (led_active_i = '1' and led_active_prev = '0');

            if rst = '1' then
                state <= IDLE;
                led_active_prev <= '0';
                counter <= (others => '0');
            else
                case state is
                    when IDLE =>
                        if led_start_edge then
                           -- **MODIFIED**: Latch and calculate delay based on microseconds
                           delay_clks_reg    <= resize((unsigned(delay_us_i) * CLKS_PER_US), delay_clks_reg'length);
                           exposure_clks_reg <= resize((unsigned(exposure_ms_i) * CLKS_PER_US), exposure_clks_reg'length);
                           counter <= (others => '0');
                           state <= DELAY;
                        end if;
                        
                    when DELAY =>
                        if counter + 1 >= delay_clks_reg then
                            counter <= (others => '0');
                            state <= EXPOSURE;
                        else
                            counter <= counter + 1;
                        end if;
                        
                    when EXPOSURE =>
                        if counter + 1 >= exposure_clks_reg then
                            state <= IDLE;
                        else
                            counter <= counter + 1;
                        end if;
                end case;
                
                if state = EXPOSURE then
                    pwm_o <= '1';
                else
                    pwm_o <= '0';
                end if;
            end if;
        end if;
    end process;
end Behavioral;
