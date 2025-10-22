library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity sequence_trigger is
    generic (
        CLK_FREQ_HZ : integer := 100_000_000
    );
    port (
        clk         : in  std_logic;
        rst         : in  std_logic;
        trigger_i   : in  std_logic;
        delay_ms_i  : in  std_logic_vector(15 downto 0);
        start_pulse_o : out std_logic
    );
end sequence_trigger;

architecture Behavioral of sequence_trigger is
    constant CLKS_PER_MS : integer := CLK_FREQ_HZ / 1_000;

    type state_t is (IDLE, DELAYING, SEND_PULSE);
    signal state : state_t := IDLE;

    signal delay_clks_reg : unsigned(31 downto 0) := (others => '0');
    signal counter        : unsigned(31 downto 0) := (others => '0');

begin
    process(clk)
        variable calc_clks : unsigned(31 downto 0);
    begin
        if rising_edge(clk) then
            if rst = '1' then
                state <= IDLE;
                start_pulse_o <= '0';
                counter <= (others => '0');
            else
                start_pulse_o <= '0';

                case state is
                    when IDLE =>
                	--calc_clks := (others => '0');

                        if trigger_i = '1' then
                            -- The new pwm_control architecture guarantees data is stable when trigger is high.
                            -- We can now safely perform the calculation immediately.
                            calc_clks := resize((unsigned(delay_ms_i) * CLKS_PER_MS), delay_clks_reg'length);
                            delay_clks_reg <= calc_clks;
                            
                            counter <= (others => '0');
                            state <= DELAYING;
                        end if;

                    when DELAYING =>
                        if counter + 1 >= delay_clks_reg then
                            state <= SEND_PULSE;
                        else
                            counter <= counter + 1;
                        end if;
                        
                    when SEND_PULSE =>
                        start_pulse_o <= '1';
                        state <= IDLE;
                end case;
            end if;
        end if;
    end process;
end Behavioral;
