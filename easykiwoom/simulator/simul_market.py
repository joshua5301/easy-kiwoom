import threading
import copy
import os
import sys
import uuid

import pandas as pd
from . import simul_tools

START_DEPOSIT = 1000000

_market_lock = threading.Lock()
def _syncronized(func):
    def wrapper(*args, **kwargs):
        with _market_lock:
            return func(*args, **kwargs)
    return wrapper

class SimulMarket():
    """
    과거 데이터 기반으로 거래를 진행하는 클래스입니다.
    실제 거래를 진행하는 Market 클래스를 대체할 수 있습니다.
    """
    _only_instance = None
    def __new__(cls, *args, **kwargs):
        if cls._only_instance is None:
            cls._only_instance = super(SimulMarket, cls).__new__(cls, *args, **kwargs)
        return cls._only_instance
    
    def __init__(self) -> None:
        self._ask_bid_info = {}
        self._deposit = START_DEPOSIT
        self._balance = {}
        
        self._order_number_to_result: dict[str, simul_tools.KiwoomQueue] = {}
        self._cancel_request: dict[str, bool] = {}

    def initialize(self) -> None:
        raise NotImplementedError('이 메서드는 monkey patch되어야 합니다.')

    def get_condition_names(self) -> list[dict]:
        raise NotImplementedError('이 메서드는 monkey patch되어야 합니다.')

    def get_matching_stocks(self, condition_name: str, condition_index: int) -> list[str]:
        raise NotImplementedError('이 메서드는 monkey patch되어야 합니다.')
    
    def get_stocks_with_volume_spike(self, criterion: str) -> list[str]:
        raise NotImplementedError('이 메서드는 monkey patch되어야 합니다.')
    
    @_syncronized
    def get_deposit(self) -> int:
        return self._deposit
    
    @_syncronized
    def get_balance(self) -> dict[str, dict]:
        return copy.deepcopy(self._balance)

    @_syncronized
    def send_order(self, order_dict: dict) -> str:

        @_syncronized
        def trade_at_market_price(order_dict: dict):
            cur_price = self.get_price_info(order_dict['주식코드'])
            # 매수 주문을 처리합니다.
            if order_dict['구분'] == '매수':
                if order_dict['주식코드'] not in self._balance:
                    if order_dict['수량'] == 0:
                        raise ValueError('주식 0개를 주문할 수는 없습니다.')
                    self._balance[order_dict['주식코드']] = {
                        '종목코드': order_dict["주식코드"],
                        '종목명': f'{order_dict["주식코드"]}의 종목명',
                        '보유수량': order_dict['수량'],
                        '주문가능수량': order_dict['수량'],
                        '매입단가': cur_price,
                    }
                else:
                    cur_stock_balance = self._balance[order_dict['주식코드']]
                    total_value = (cur_stock_balance['보유수량'] * cur_stock_balance['매입단가'] +
                                order_dict['수량'] * cur_price)
                    total_amount = cur_stock_balance['보유수량'] + order_dict['수량']
                    cur_stock_balance['보유수량'] += order_dict['수량']
                    cur_stock_balance['주문가능수량'] += order_dict['수량']
                    cur_stock_balance['매입단가'] = int(total_value / total_amount)
                self._deposit -= order_dict['수량'] * cur_price
                if self._deposit < 0:
                    raise RuntimeError('주문가능금액이 충분하지 않습니다.')
            # 매도주문을 처리합니다.
            elif order_dict['구분'] == '매도':
                if order_dict['주식코드'] not in self._balance:
                    raise RuntimeError('보유하지 않은 종목은 팔 수 없습니다.')
                cur_stock_balance = self._balance[order_dict['주식코드']]
                cur_stock_balance['보유수량'] -= order_dict['수량']
                cur_stock_balance['주문가능수량'] -= order_dict['수량']
                self._deposit += order_dict['수량'] * cur_price * 0.998
                if cur_stock_balance['주문가능수량'] < 0:
                    raise RuntimeError('보유 주식이 충분하지 않습니다.')
                elif cur_stock_balance['주문가능수량'] == 0:
                    del self._balance[order_dict['주식코드']]
        
        def trade_until_finished(order_dict: dict, order_number: str):
            completed_order_result = order_dict
            canceled_order_result = order_dict
            # 시장가 주문의 경우
            if order_dict['시장가']:
                trade_at_market_price(order_dict)
                self._order_number_to_result[order_number].put('완료', block=False)
                return
            # 지정가 주문의 경우
            while not self._cancel_request[order_number]:
                cur_price = self.get_price_info(order_dict['주식코드'])
                target_price = order_dict['가격']
                if (order_dict['구분'] == '매도' and cur_price >= target_price or 
                    order_dict['구분'] == '매수' and cur_price <= target_price):
                    trade_at_market_price(order_dict)
                    self._order_number_to_result[order_number].put('완료', block=False)
                    return
                simul_tools.kiwoom_sleep(1)
            # 취소 요청이 들어왔을 때
            self._order_number_to_result[order_number].put('취소', block=False)
        
        order_number = str(uuid.uuid4())
        self._order_number_to_result[order_number] = simul_tools.KiwoomQueue(maxsize=1)
        self._cancel_request[order_number] = False
        trading_thread = simul_tools.KiwoomThread(target=trade_until_finished, args=(order_dict, order_number), name='trader', daemon=True)
        trading_thread.start()
        return order_number
    
    def get_order_result(self, order_number: str) -> dict:
        order_result = self._order_number_to_result[order_number].get()
        return order_result
    
    def cancel_order(self, order_number: str):
        self._cancel_request[order_number] = True
    
    def register_price_info(self, stock_code_list: list[str], is_add: bool = False) -> None:
        pass

    def register_ask_bid_info(self, stock_code_list: list[str], is_add: bool = False) -> None:
        pass

    def get_price_info(self, stock_code: str) -> dict:
        try:
            return self._ask_bid_info[stock_code][simul_tools._elapsed_seconds]['매수호가정보'][0][0]
        except IndexError:
            raise sys.exit(0)
    
    def get_ask_bid_info(self, stock_code: str) -> dict:
        try:
            return self._ask_bid_info[stock_code][simul_tools._elapsed_seconds]
        except IndexError:
            raise sys.exit(0)
        