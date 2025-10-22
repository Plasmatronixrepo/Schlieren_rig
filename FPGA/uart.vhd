library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity uart is
    generic (
        CLK_FREQ_HZ : integer := 100_000_000; -- System clock frequency in Hz
        BAUD_RATE   : integer := 115200      -- Baud rate
    );
    port (
        clk        : in  std_logic;
        rst        : in  std_logic;
        rx_i       : in  std_logic;
        tx_o       : out std_logic;
        rx_data_o  : out std_logic_vector(7 downto 0);
        rx_valid_o : out std_logic;
        tx_data_i  : in  std_logic_vector(7 downto 0);
        tx_start_i : in  std_logic;
        tx_busy_o  : out std_logic
    );
end uart;

architecture rtl of uart is

    -- Constants for baud rate generation
    constant CLK_PERIOD_NS : integer := 1_000_000_000 / CLK_FREQ_HZ;
    constant BAUD_PERIOD_NS: integer := 1_000_000_000 / BAUD_RATE;
    constant CLKS_PER_BAUD : integer := BAUD_PERIOD_NS / CLK_PERIOD_NS;

    -- TX signals
    type tx_state_type is (IDLE, START_BIT, DATA_BITS, STOP_BIT);
    signal tx_state      : tx_state_type := IDLE;
    signal tx_clk_counter: integer range 0 to CLKS_PER_BAUD - 1 := 0;
    signal tx_bit_index  : integer range 0 to 8 := 0;
    signal tx_data_reg   : std_logic_vector(7 downto 0) := (others => '0');
    signal tx_busy_s     : std_logic := '0';
    
    -- RX signals
    type rx_state_type is (IDLE, START_BIT, DATA_BITS, STOP_BIT);
    signal rx_state      : rx_state_type := IDLE;
    signal rx_clk_counter: integer range 0 to CLKS_PER_BAUD - 1 := 0;
    signal rx_bit_index  : integer range 0 to 8 := 0;
    signal rx_data_reg   : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_valid_s    : std_logic := '0';

begin

    tx_busy_o <= tx_busy_s;
    
    -- TX Process
    tx_process: process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                tx_state <= IDLE;
                tx_clk_counter <= 0;
                tx_bit_index <= 0;
                tx_o <= '1';
                tx_busy_s <= '0';
            else
                case tx_state is
                    when IDLE =>
                        tx_o <= '1';
                        tx_busy_s <= '0';
                        if tx_start_i = '1' then
                            tx_data_reg <= tx_data_i;
                            tx_state <= START_BIT;
                            tx_clk_counter <= 0;
                            tx_bit_index <= 0;
                            tx_busy_s <= '1';
                        end if;
                        
                    when START_BIT =>
                        tx_o <= '0';
                        if tx_clk_counter = CLKS_PER_BAUD - 1 then
                            tx_clk_counter <= 0;
                            tx_state <= DATA_BITS;
                        else
                            tx_clk_counter <= tx_clk_counter + 1;
                        end if;
                        
                    when DATA_BITS =>
                        tx_o <= tx_data_reg(tx_bit_index);
                        if tx_clk_counter = CLKS_PER_BAUD - 1 then
                            tx_clk_counter <= 0;
                            if tx_bit_index = 7 then
                                tx_bit_index <= 0;
                                tx_state <= STOP_BIT;
                            else
                                tx_bit_index <= tx_bit_index + 1;
                            end if;
                        else
                            tx_clk_counter <= tx_clk_counter + 1;
                        end if;
                        
                    when STOP_BIT =>
                        tx_o <= '1';
                        if tx_clk_counter = CLKS_PER_BAUD - 1 then
                            tx_clk_counter <= 0;
                            tx_state <= IDLE;
                        else
                            tx_clk_counter <= tx_clk_counter + 1;
                        end if;
                end case;
            end if;
        end if;
    end process tx_process;
    
    -- RX Process
    rx_process: process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                rx_state <= IDLE;
                rx_clk_counter <= 0;
                rx_bit_index <= 0;
                rx_valid_s <= '0';
            else
                rx_valid_s <= '0'; -- Default to not valid
                case rx_state is
                    when IDLE =>
                        if rx_i = '0' then
                            rx_state <= START_BIT;
                            rx_clk_counter <= 0;
                        end if;
                        
                    when START_BIT =>
                        -- Wait for half a bit period to sample in the middle
                        if rx_clk_counter = (CLKS_PER_BAUD / 2) - 1 then
                            if rx_i = '0' then
                                rx_clk_counter <= 0;
                                rx_state <= DATA_BITS;
                                rx_bit_index <= 0;
                            else -- False start bit
                                rx_state <= IDLE;
                            end if;
                        else
                            rx_clk_counter <= rx_clk_counter + 1;
                        end if;
                        
                    when DATA_BITS =>
                        if rx_clk_counter = CLKS_PER_BAUD - 1 then
                            rx_clk_counter <= 0;
                            rx_data_reg(rx_bit_index) <= rx_i;
                            if rx_bit_index = 7 then
                                rx_bit_index <= 0;
                                rx_state <= STOP_BIT;
                            else
                                rx_bit_index <= rx_bit_index + 1;
                            end if;
                        else
                            rx_clk_counter <= rx_clk_counter + 1;
                        end if;
                        
                    when STOP_BIT =>
                        if rx_clk_counter = CLKS_PER_BAUD - 1 then
                            rx_clk_counter <= 0;
                            if rx_i = '1' then -- Valid stop bit
                                rx_data_o <= rx_data_reg;
                                rx_valid_s <= '1';
                            end if;
                            rx_state <= IDLE;
                        else
                            rx_clk_counter <= rx_clk_counter + 1;
                        end if;
                end case;
            end if;
        end if;
    end process rx_process;

    rx_valid_o <= rx_valid_s;

end rtl;