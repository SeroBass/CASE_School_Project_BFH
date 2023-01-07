# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union
from freqtrade.strategy import IStrategy, informative

from freqtrade.persistence import Trade
from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy, merge_informative_pair)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class TSS(IStrategy):
    # Source of Strategy Idea: "The Simple Strategy" by Markus Heitkoetter
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Can this strategy go short?
    can_short: bool = True

    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "0": 0.2
    }

    # Optimal stoploss designed for the strategy.
    stoploss = -0.2

    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Calls function "custom_stoploss"
    use_custom_stoploss = True

    order_types = {
        'entry': 'market',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    custom_exit_static = {"BTC/USDT": [-1, -1, -1, 1, -1],
                          "ETH/USDT": [-1, -1, -1, 1, -1]}
    # where
    # [0] - long take profit
    # [1] - short take profit
    # [2] - tade id take profit
    # [3] - - ADR to stoploss
    # [4] - trade id stoploss

    # Calculate ADR based on daily candles
    @informative('1d')
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ADR'] = self.custom_ADR(dataframe, candlesback=7)['adr']
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=200, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Long Position Entry
        dataframe.loc[
            (
                (dataframe['rsi'] > 70) &

                (dataframe['bb_upperband'] > dataframe['bb_upperband'].shift(1)) & # points up

                (dataframe['macd'] > 0) & # over 0
                (dataframe['macd'] > dataframe['macdsignal'])  # over signal
            ),
            'enter_long'] = 1

        # Short Position Entry
        dataframe.loc[
            (
                (dataframe['rsi'] < 30) &

                (dataframe['bb_upperband'] < dataframe['bb_upperband'].shift(1)) & # points down

                (dataframe['macd'] < 0) & # under 0
                (dataframe['macd'] < dataframe['macdsignal'])  # under signal
            ),
            'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        return dataframe

    # Calcuation of exit based on ADR
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        if self.custom_exit_static[pair][2] != int(trade.id):
            self.custom_exit_static[pair][2] = int(trade.id)
            if not trade.is_short:
                self.custom_exit_static[pair][0] = last_candle['close'] + (last_candle['ADR_1d'] * 0.15)
            else:
                self.custom_exit_static[pair][1] = last_candle['close'] - (last_candle['ADR_1d'] * 0.15)

        if not trade.is_short and last_candle['close'] > self.custom_exit_static[pair][0]:
            return True
        if trade.is_short and last_candle['close'] < self.custom_exit_static[pair][1]:
            return True

        return False

    # Calculation of the stoploss based on ADR
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if self.custom_exit_static[pair][4] != int(trade.id):
            self.custom_exit_static[pair][4] = int(trade.id)
            if not trade.is_short:

                self.custom_exit_static[pair][3] = last_candle['close'] - (last_candle['ADR_1d'])
                stoploss_ = (last_candle['close'] - self.custom_exit_static[pair][3]) / last_candle['close'] * -1
                return stoploss_
            else:
                self.custom_exit_static[pair][3] = last_candle['close'] + (last_candle['ADR_1d'])

                stoploss_ = (last_candle['close'] - self.custom_exit_static[pair][3]) / last_candle['close']
                return stoploss_

        return 100

    # Calculation of ADR
    def custom_ADR(self, dataframe: DataFrame, candlesback):

        df = dataframe.copy()

        def helper(high, low):
            return high - low

        df['high_low'] = np.vectorize(helper)(df['high'], df['low'])
        df['ADR'] = df['high_low'].rolling(window=candlesback).sum() / candlesback
        df.drop(['high_low'], inplace=True, axis=1)

        return DataFrame(index=df.index, data={
            'adr': df['ADR'],
        })
