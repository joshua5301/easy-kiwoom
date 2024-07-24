import sys
import os
import time
import datetime
import threading
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('Agg')
import mplfinance as mpf

from ..market import Market
from .analyzer_const import RECORD_INTERVAL, RESAMPLE_INTERVAL

class Analyzer:
    """
    Strategy를 통해 이루어진 거래 결과를 분석하는 클래스
    """

    def __init__(self, market: Market, stock_universe: list[str]):
        """
        정보를 기록할 주식들을 받고 이에 대한 정보를 저장할 dict를 초기화합니다.

        Parameters
        ----------
        stock_universe : list[str]
            Analyzer가 정보를 기록하게 될 모든 주식입니다.
        market : Market
            정보를 가져올 마켓입니다.
        """
        
        self.market = market
        self.stock_universe = stock_universe
        self.price_history = {}
        self.ask_bid_history = {}
        self.balance_history = {}
        for stock_code in self.stock_universe:
            self.price_history[stock_code] = {
                '현재가': [],
                '시간': []
            }
            self.ask_bid_history[stock_code] = {
                '시간': []
            }
            for i in range(10):
                self.ask_bid_history[stock_code][f'매도{i + 1}호가'] = []
                self.ask_bid_history[stock_code][f'매도{i + 1}호가수량'] = []
                self.ask_bid_history[stock_code][f'매수{i + 1}호가'] = []
                self.ask_bid_history[stock_code][f'매수{i + 1}호가수량'] = []
            self.balance_history[stock_code] = {
                '매입단가': [],
                '시간': []
            }

        self._recorder_thread = threading.Thread(target=self._start_recording)
        self._is_finished = False

    def start_recording(self):
        """
        일정 주기마다 잔고 정보와 실시간 주식 정보를 기록합니다.

        새로운 쓰레드에서 진행되므로 block되지 않습니다.
        """
        self._recorder_thread.start()

    def end_recording(self) -> None:
        """
        정보 기록을 중지합니다.
        """
        self._is_finished = True
        self._recorder_thread.join()

    def _start_recording(self):
        while self._is_finished is False:
            # 가격 정보를 기록합니다.
            for stock_code in self.stock_universe:
                cur_price = self.market.get_price_info(stock_code)
                self.price_history[stock_code]['현재가'].append(cur_price)
                self.price_history[stock_code]['시간'].append(datetime.datetime.now())

            # 호가 정보를 기록합니다.
            for stock_code in self.stock_universe:
                ask_bid_info = self.market.get_ask_bid_info(stock_code)
                for idx, info in enumerate(ask_bid_info['매도호가정보']):
                    price, amount = info
                    self.ask_bid_history[stock_code][f'매도{idx + 1}호가'].append(price)
                    self.ask_bid_history[stock_code][f'매도{idx + 1}호가수량'].append(amount)
                for idx, info in enumerate(ask_bid_info['매수호가정보']):
                    price, amount = info
                    self.ask_bid_history[stock_code][f'매수{idx + 1}호가'].append(price)
                    self.ask_bid_history[stock_code][f'매수{idx + 1}호가수량'].append(amount)
                self.ask_bid_history[stock_code]['시간'].append(datetime.datetime.now())

            # 잔고 정보를 기록합니다.
            balance = self.market.get_balance()
            for stock_code in self.stock_universe:
                if stock_code in balance.keys():
                    self.balance_history[stock_code]['매입단가'].append(balance[stock_code]['매입단가'])
                else:
                    self.balance_history[stock_code]['매입단가'].append(np.nan)
                self.balance_history[stock_code]['시간'].append(datetime.datetime.now())
            time.sleep(RECORD_INTERVAL)

    def _create_graph(self, output_dir_path: str, stock_code: str) -> None:

        # 현재가에 대한 ohlc 데이터프레임을 만듭니다.
        price_df = pd.DataFrame(self.price_history[stock_code])
        price_df.set_index('시간', inplace=True, drop=True)
        
        # 리샘플링 후 간격마다 누락된 데이터를 채워넣습니다.
        ohlc_df = price_df['현재가'].resample(RESAMPLE_INTERVAL).ohlc()
        ohlc_df['close'] = ohlc_df['close'].ffill()
        ohlc_df['open'] = ohlc_df['open'].fillna(ohlc_df['close'])
        ohlc_df['low'] = ohlc_df['low'].fillna(ohlc_df['close'])
        ohlc_df['high'] = ohlc_df['high'].fillna(ohlc_df['close'])
        
        # 호가정보에 대한 데이터프레임을 만듭니다.
        ask_bid_df = pd.DataFrame(self.ask_bid_history[stock_code])
        ask_bid_df.set_index('시간', inplace=True, drop=True)
        ask_bid_df = ask_bid_df.resample(RESAMPLE_INTERVAL).first().ffill()

        # 매수가에 대한 데이터프레임을 만듭니다.
        avg_price_df = pd.DataFrame(self.balance_history[stock_code])
        avg_price_df.set_index('시간', inplace=True, drop=True)
        avg_price_df = avg_price_df.resample(RESAMPLE_INTERVAL).first()
        
        # 각 데이터프레임의 길이를 동일하게 맞춰줍니다.
        min_len = min(len(ohlc_df), len(avg_price_df), len(ask_bid_df))
        ohlc_df = ohlc_df.iloc[:min_len]
        ask_bid_df = ask_bid_df.iloc[:min_len]
        avg_price_df = avg_price_df.iloc[:min_len]
        
        # 메인 데이터프레임과 addplot들을 plot하고 이를 저장합니다.
        ask_df = ask_bid_df[[f'매도{i + 1}호가수량' for i in range(10)]]
        bid_df = -ask_bid_df[[f'매수{i + 1}호가수량' for i in range(10)]]
        market_colors = mpf.make_marketcolors(up='#E71809', down='#115BCB', inherit=True)
        kiwoom_style = mpf.make_mpf_style(marketcolors=market_colors, gridstyle='-', gridcolor='#D8D8D8', gridaxis='horizontal')
        addplots = [
            mpf.make_addplot(data=avg_price_df, panel=0, secondary_y=False, type='line', color='black'),
            mpf.make_addplot(data=ask_df, panel=1, secondary_y=False, type='bar', color='#115BCB'),
            mpf.make_addplot(data=bid_df, panel=1, secondary_y=False, type='bar', color='#E71809')
        ]
        output_graph_path = os.path.join(output_dir_path, stock_code + '.png')
        mpf.plot(ohlc_df, addplot=addplots, type='candle', figratio=(18,10), tight_layout=True, 
                    datetime_format='%HH %MM %SS', style=kiwoom_style, savefig=output_graph_path)
        
    def _create_csv(self, output_dir_path: str, stock_code: str) -> None:

        ask_bid_df = pd.DataFrame(self.ask_bid_history[stock_code])
        ask_bid_df.set_index('시간', inplace=True, drop=True)
        ask_bid_df = ask_bid_df.resample(RESAMPLE_INTERVAL).first().ffill()
        ask_bid_df.to_csv(os.path.join(output_dir_path, f'{stock_code}.csv'))

    def save_results(self):
        # 결과를 저장할 폴더를 생성합니다.
        start_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        cur_data_path = os.path.join(start_path, 'data', datetime.datetime.now().strftime('%y%m%d-%H%M%S'))
        graph_path = os.path.join(cur_data_path, 'graph')
        csv_path = os.path.join(cur_data_path, 'csv')
        os.makedirs(graph_path, exist_ok=True)
        os.makedirs(csv_path, exist_ok=True)

        # 각 종목마다 ohlc 그래프와 csv 파일을 저장합니다.
        for stock_code in self.stock_universe:
            self._create_csv(csv_path, stock_code)
        
        '''
        for stock_code in self.balance_history.keys():
            self._create_graph(graph_path, stock_code)
        '''
        
        # 분석 결과가 저장된 폴더 창을 띄웁니다.
        os.system(f'start "" "{cur_data_path}"')