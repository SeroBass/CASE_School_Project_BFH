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


class FMS(IStrategy):
    # Source of Squeeze Momentum Indicator by LazyBear: https://www.tradingview.com/script/nqQ1DT5a-Squeeze-Momentum-Indicator-LazyBear/
    # Source of Strategy Idea: https://daviddtech.medium.com/83-win-rate-5-minute-ultimate-scalping-trading-strategy-89c4e89fb364

    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Can this strategy go short?
    can_short: bool = True

    minimal_roi = {
        "0": 0.027,
    }

    # Optimal stoploss designed for the strategy.
    stoploss = -0.02

    process_only_new_candles = True

    use_exit_signal = False
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

        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # EMA
        dataframe['ema'] = ta.EMA(dataframe, timeperiod=200)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=200, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # Squeeze Momentum
        dataframe['val'] = self.SM(dataframe, 200, 2, 20, 1.5)['Val']
        dataframe['sqzOn'] = self.SM(dataframe, 200, 2, 20, 1.5)['SqzOn']
        dataframe['sqzOff'] = self.SM(dataframe, 200, 2, 20, 1.5)['SqzOff']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Long Position Entry
        dataframe.loc[
            (
                    (dataframe['close'] > dataframe['ema']) &
                    (dataframe['adx'] > 25) &
                    (dataframe['val'] > 0) &
                    (dataframe['sqzOff'] > 0) &
                    (dataframe['sqzOff'].shift(1) == 0)
            ),
            'enter_long'] = 1

        # Short Position Entry
        dataframe.loc[
            (
                    (dataframe['close'] < dataframe['ema']) &
                    (dataframe['adx'] > 25) &
                    (dataframe['val'] < 0) &
                    (dataframe['sqzOff'] > 0) &
                    (dataframe['sqzOff'].shift(1) == 0)
            ),
            'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def SM(self, dataframe: DataFrame, BBlen, BBmult, KCLen, KCMult):
        df = dataframe.copy()
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(df), window=BBlen, stds=BBmult)
        df['bb_lowerband'] = bollinger['lower']
        df['bb_middleband'] = bollinger['mid']
        df['bb_upperband'] = bollinger['upper']
        df['tr'] = qtpylib.true_range(df)
        df['ma'] = qtpylib.sma(df['close'], KCLen)
        df['range'] = df['tr']
        df['rangema'] = qtpylib.sma(df['range'], KCLen)
        df['upperKC'] = df['ma'] + df['range'] * KCMult
        df['lowerKC'] = df['ma'] - df['range'] * KCMult
        df['sqzOn'] = np.where((df['bb_lowerband'] > df['lowerKC']) & (df['bb_upperband'] < df['upperKC']), 1, 0)
        df['sqzOff'] = np.where((df['bb_lowerband'] < df['lowerKC']) & (df['bb_upperband'] > df['upperKC']), 1, 0)
        df['highest'] = ta.MAX(df['high'], KCLen)
        df['lowest'] = ta.MIN(df['low'], KCLen)
        df['AVG1'] = (df['highest'] + df['lowest']) / 2
        df['AVG'] = (df['AVG1'] + df['ma']) / 2
        df['last'] = df['close'] - df['AVG']
        df['val'] = ta.LINEARREG(df['last'], BBlen)

        df.drop(['bb_lowerband','bb_middleband', 'bb_upperband','tr', 'ma', 'range', 'rangema', 'upperKC', 'lowerKC', 'AVG1', 'AVG','last','highest', 'lowest'], inplace=True, axis=1)

        return DataFrame(index=df.index, data={
            'Val': df['val'],
            'SqzOn': df['sqzOn'],
            'SqzOff': df['sqzOff']
        })
