import os
import sys
import threading
import queue
import time
import datetime
import random
import easykiwoom
import freezegun
import pandas as pd

from . import simul_tools
from .. import utils
from .simul_market import SimulMarket

class Simulator:

    def __init__(self):
        self._ask_bid_info = {}
        self._stocks_with_volume_spike = []
        self._condition_names = []
        self._matching_stocks = {}

    def set_simul_data(self, folder_path: str):

        for file_name in os.listdir(folder_path):
            stock_code, extension = file_name.split('.', maxsplit=1)
            if extension != 'csv':
                raise ValueError(f'csv 확장자가 아닙니다. - {file_name}')
            
            df = pd.read_csv(os.path.join(folder_path, file_name), index_col=0)
            self._ask_bid_info[stock_code] = []
            for cur_time, series in df.iterrows():
                cur_info = {'매도호가정보': [[None, None] for _ in range(10)], '매수호가정보': [[None, None] for _ in range(10)]}
                for info_type, value in series.items():
                    if info_type[2:4] == '10':
                        position = 9
                    else:
                        position = int(info_type[2]) - 1
                    if info_type.startswith('매도') and info_type.endswith('호가'):
                        cur_info['매도호가정보'][position][0] = value
                    elif info_type.startswith('매도') and info_type.endswith('수량'):
                        cur_info['매도호가정보'][position][1] = value
                    elif info_type.startswith('매수') and info_type.endswith('호가'):
                        cur_info['매수호가정보'][position][0] = value
                    elif info_type.startswith('매수') and info_type.endswith('수량'):
                        cur_info['매수호가정보'][position][1] = value
                    else:
                        raise ValueError(f'예상치 못한 index입니다. - {cur_info}')
                self._ask_bid_info[stock_code].append(cur_info)

    def set_random_simul_data(self, stock_codes: list[str], total_time: int = 3600, initial_price: int = 1000):
        for stock_code in stock_codes:
            self._ask_bid_info[stock_code] = []
            cur_price = initial_price
            for cur_time in range(total_time):
                cur_info = {'매도호가정보': [], '매수호가정보': []}
                bid_price = utils.get_shifted_kiwoom_price(cur_price, -1)
                for _ in range(10):
                    bid_price = utils.get_shifted_kiwoom_price(bid_price, 1)
                    bid_amount = random.randint(0, 1000)
                    cur_info['매도호가정보'].append([bid_price, bid_amount])
                ask_price = cur_price
                for _ in range(10):
                    ask_price = utils.get_shifted_kiwoom_price(ask_price, -1)
                    ask_amount = random.randint(0, 1000)
                    cur_info['매수호가정보'].append([ask_price, ask_amount])
                cur_price = utils.get_shifted_kiwoom_price(cur_price, random.randint(-3, 3))
                self._ask_bid_info[stock_code].append(cur_info)
                
    def set_condition_names(self, condition_names: list[str]):
        self._condition_names = condition_names

    def set_matching_stocks(self, condition_name: str, stock_list: list[str]):
        self._matching_stocks[condition_name] = stock_list

    def set_stocks_with_volume_spike(self, stock_list: list[str]):
        self._stocks_with_volume_spike = stock_list

    def simulate(self, file_path: str):
        if not simul_tools.OriginalThread:
            simul_tools.OriginalThread = threading.Thread
        if not simul_tools.OriginalQueue:
            simul_tools.OriginalQueue = queue.Queue
        if not simul_tools.original_sleep:
            simul_tools.original_sleep = time.sleep
        simul_tools._elapsed_seconds = 0

        def initialize(market_self):
            market_self._ask_bid_info = self._ask_bid_info
        SimulMarket.initialize = initialize
        def get_stocks_with_volume_spike(market_self, criterion):
            return self._stocks_with_volume_spike
        SimulMarket.get_stocks_with_volume_spike = get_stocks_with_volume_spike
        def get_matching_stocks(market_self, condition_name):
            return self._matching_stocks[condition_name]
        SimulMarket.get_matching_stocks = get_matching_stocks
        def get_condition_names(market_self):
            return self._condition_names
        SimulMarket.get_condition_names = get_condition_names
        easykiwoom.Market = SimulMarket
        threading.Thread = simul_tools.KiwoomThread
        queue.Queue = simul_tools.KiwoomQueue
        time.sleep = simul_tools.kiwoom_sleep

        sys.modules['easykiwoom'] = easykiwoom
        sys.modules['threading'] = threading
        sys.modules['queue'] = queue
        sys.modules['time'] = time

        sys.path.append(os.path.dirname(file_path))
        with freezegun.freeze_time(datetime.datetime.now()) as frozen_datetime:
            simul_tools._frozen_datetime = frozen_datetime
            __import__(os.path.basename(file_path))
        del sys.modules[os.path.basename(file_path)]
        sys.path.pop()