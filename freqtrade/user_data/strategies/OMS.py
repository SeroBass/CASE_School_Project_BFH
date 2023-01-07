# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy, merge_informative_pair)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class OMS(IStrategy):
    # Source of Strategy Idea: https://daviddtech.medium.com/easy-1-minute-scalping-trading-strategy-simple-but-profitable-e9a62885c1df
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy
    timeframe = '1m'

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "0": 0.009,
    }

    # Optimal stoploss designed for the strategy.
    stoploss = -0.009

    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Optional order type mapping.
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    def informative_pairs(self):

        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # EMA
        dataframe['ema'] = ta.EMA(dataframe, timeperiod=50)

        # Engulfing Patterns
        dataframe['eng_l'] = self.eng(dataframe)['Eng_l']
        dataframe['eng_s'] = self.eng(dataframe)['Eng_s']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Long Position Entry
        dataframe.loc[
            (
                    (dataframe['close'] > dataframe['ema']) &
                    (dataframe['rsi'] > 50) &
                    (dataframe['eng_l'] == 1)
            ),
            'enter_long'] = 1

        # Short Position Entry
        dataframe.loc[
            (
                    (dataframe['close'] < dataframe['ema']) &
                    (dataframe['rsi'] < 50) &
                    (dataframe['eng_s'] == 1)
            ),
            'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # Engulfing Patter Definition
    def eng(self, dataframe: DataFrame):
        df = dataframe.copy()

        def bull(open, close):
            if open > close:
                return -1
            else:
                return 1

        df['red_green'] = np.vectorize(bull)(df['open'], df['close'])
        df.loc[(df['red_green'] > 0) & (df['red_green'].shift(1) < 0) &
               (df['close'] >= df['open'].shift(1)) & (df['close'].shift(1) >= df['open']
                                                       ),
        'eng_l'] = 1
        df.loc[(df['red_green'] < 0) & (df['red_green'].shift(1) > 0) &
               (df['close'] <= df['open'].shift(1)) & (df['close'].shift(1) <= df['open']
                                                       ),
        'eng_s'] = 1

        df.drop(['red_green'], inplace=True, axis=1)
        return DataFrame(index=df.index, data={
            'Eng_l': df['eng_l'],
            'Eng_s': df['eng_s']
        })
