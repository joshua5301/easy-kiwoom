import datetime
import logging
import queue
import json
import socket
import threading
from collections import defaultdict
from .utils import *

logger = logging.getLogger(__name__)

class Market():
    """
    주식시장을 구현한 클래스
    
    Client는 이 클래스의 메서드를 통해 주식과 계좌 정보를 얻고 이를 바탕으로 매매할 수 있습니다.
    여러 쓰레드가 동시에 메서드를 호출해도 안전합니다.
    """
    def __init__(self):
        self._result_buffer = defaultdict(dict)
        self._result_buffer_lock = threading.Lock()
        self._socket_buffer = ''
        self._socket_buffer_size = 8192
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._receiver_thread = threading.Thread(target=self._save_proxy_responses, name='kiwoomproxy_receiver', daemon=True)
        self._resetter_thread = threading.Thread(target=reset_API_call_count, name='API_call_count_resetter', daemon=True)

        self._balance = None
        self._price_info = {}
        self._ask_bid_info = {}

    def connect(self):
        """
        키움증권의 프록시와 연결합니다.
        """
        self._socket.connect(('127.0.0.1', 53939))
        self._receiver_thread.start()
        self._resetter_thread.start()
    
    def _read_from_proxy(self) -> dict:
        chunk = self._socket.recv(self._socket_buffer_size)
        if not chunk:
            raise ConnectionError("프록시와의 연결이 끊어졌습니다.")
        self._socket_buffer += chunk.decode()
        parts = self._socket_buffer.split('\n')
        responses, self._socket_buffer = parts[:-1], parts[-1]
        responses = [json.loads(response) for response in responses]
        return responses
    
    def _save_proxy_responses(self):
        while True:
            responses = self._read_from_proxy()
            for response in responses:
                type, key, value = response['type'], response['key'], response['value']
                if type == 'balance_change':
                    balance_change = value
                    if balance_change['보유수량'] == 0:
                        del self._balance[balance_change['종목코드']]
                    else:
                        self._balance[balance_change['종목코드']] = balance_change
                if type == 'completed_order':
                    order_number = key
                    with self._result_buffer_lock:
                        if order_number not in self._result_buffer['completed_order']:
                            self._result_buffer['completed_order'][order_number] = queue.Queue(maxsize=1)
                    self._result_buffer['completed_order'][order_number].put(value, block=False)
                if type == 'price_info':
                    self._price_info[key] = value
                if type == 'ask_bid_info':
                    self._ask_bid_info[key] = value
                else:
                    self._result_buffer[type][key].put(value, block=False)

    def _send_to_proxy(self, info_dict: dict) -> None:
        """
        요청 정보를 키움증권 프록시에 전달합니다.

        Parameters
        ----------
        info_dict : dict
            info_dict = {
                'method': str
                'key': str
            }
        """
        data = (json.dumps(info_dict) + '\n').encode()
        self._socket.sendall(data)

    @trace
    def initialize(self) -> None:
        """
        주식시장을 초기화합니다.
        (로그인 -> 계좌번호 로드 -> 초기 잔고 로드)
        
        다른 메서드를 사용하기 전에 오직 한번만 호출되어야 합니다.
        """
        while True:
            self._result_buffer['login_result'][''] = queue.Queue(maxsize=1)
            self._send_to_proxy({'method': 'login', 'args': {}})
            login_result = self._result_buffer['login_result'][''].get()
            del self._result_buffer['login_result']['']
            if login_result == 0:
                break

        self._send_to_proxy({'method': 'load_account_number', 'args': {}})
        
        request_name = get_unique_request_name()
        self._result_buffer['balance'][request_name] = queue.Queue(maxsize=1)
        self._send_to_proxy({'method': 'request_balance', 'args': {'request_name': request_name}})
        self._balance = self._result_buffer['balance'][request_name].get()
        del self._result_buffer['balance'][request_name]

    @request_api_method
    @trace
    def get_condition(self) -> list[dict]:
        """
        조건검색식을 로드하고 각각의 이름과 인덱스를 반환합니다.

        Returns
        -------
        list[dict]
            조건검색식의 list를 반환합니다.
            
            dict = {
                'name': str,
                'index': int,  
            }
        """

        self._result_buffer['condition_name'][''] = queue.Queue(maxsize=1)
        self._send_to_proxy({'method': 'request_condition_name', 'args': {}})
        condition_list = self._result_buffer['condition_name'][''].get()
        del self._result_buffer['condition_name']['']
        return condition_list

    @request_api_method
    @trace
    def get_matching_stocks(self, condition_name: str, condition_index: int) -> list[str]:
        """
        주어진 조건검색식과 부합하는 주식 코드의 리스트를 반환합니다.
        동일한 condition에 대한 요청은 1분 내 1번으로 제한됩니다.

        Parameters
        ----------
        condition_name : str
            조건검색식의 이름입니다.
        condition_index : int
            조건검색식의 인덱스입니다.

        Returns
        -------
        list[str]
            부합하는 주식 종목의 코드 리스트를 반환합니다.
        """
        
        self._result_buffer['condition_search_result'][condition_name] = queue.Queue(maxsize=1)
        self._send_to_proxy({'method': 'request_condition_search', 'args': {'condition_name': condition_name, 'condition_index': condition_index}})
        matching_stocks = self._result_buffer['condition_search_result'][condition_name].get()
        del self._result_buffer['condition_search_result'][condition_name]
        return matching_stocks
    
    @request_api_method
    @trace
    def get_deposit(self) -> int:
        """
        계좌의 주문가능금액을 반환합니다.

        Returns
        -------
        int
            주문가능금액을 반환합니다.
        """
        request_name = get_unique_request_name()
        self._result_buffer['deposit'][request_name] = queue.Queue(maxsize=1)
        self._send_to_proxy({'method': 'request_deposit', 'args': {'request_name': request_name}})
        deposit = self._result_buffer['deposit'][request_name].get()
        del self._result_buffer['deposit'][request_name]
        return deposit

    @request_api_method
    @trace
    def get_balance(self) -> dict[str, dict]:
        """
        보유주식정보를 반환합니다.
        
        주의: 연속조회는 아직 지원되지 않으므로 '시작 할 당시' 보유주식이 많을 경우 
        정보의 일부분만 전송될 수 있습니다.

        Returns
        -------
        dict[str, dict]
            보유주식정보를 반환합니다.
            dict[stock_code] = {
                '종목코드': str,
                '종목명': str,
                '보유수량': int,
                '주문가능수량': int,
                '매입단가': int,
            }
        """
        return self._balance
    
    @order_api_method
    @trace
    def send_order(self, order_dict: dict) -> str:
        """
        주문을 전송합니다.

        Parameters
        ----------
        order_dict : dict
            order_dict = {
                '구분': '매도' or '매수',
                '주식코드': str,
                '수량': int,
                '가격': int,
                '시장가': bool
            }
            
            시장가 주문을 전송할 경우 가격은 0으로 전달해야 합니다.

        Returns
        -------
        str
            unique한 주문 번호를 반환합니다.
        """
        request_name = get_unique_request_name()
        self._result_buffer['accepted_order'][request_name] = queue.Queue(maxsize=1)
        self._send_to_proxy({'method': 'request_order', 'args': {'order_dict': order_dict, 'request_name': request_name}})
        order_number = self._result_buffer['accepted_order'][request_name].get()
        del self._result_buffer['accepted_order'][request_name]
        return order_number
 
    @trace
    def get_order_info(self, order_number: str) -> dict:
        """
        주문 번호을 가지고 주문 정보를 얻어옵니다.
        만약 주문이 전부 체결되지 않았다면 체결될 때까지 기다립니다.

        Parameters
        ----------
        order_number : str
            send_order 함수로 얻은 unique한 주문 번호입니다.

        Returns
        -------
        dict
            주문 정보입니다.
        """
        with self._result_buffer_lock:
            if order_number not in self._result_buffer['completed_order']:
                self._result_buffer['completed_order'][order_number] = queue.Queue(maxsize=1)
        order_info = self._result_buffer['completed_order'][order_number].get()
        return order_info 
    
    @trace
    def register_price_info(self, stock_code_list: list[str], is_add: bool = False) -> None:
        """
        주어진 주식 코드에 대한 실시간 가격 정보를 등록합니다.

        Parameters
        ----------
        stock_code_list : list[str]
            실시간 정보를 등록하고 싶은 주식의 코드 리스트입니다.
        is_add : bool, optional
            True일시 화면번호에 존재하는 기존의 등록은 사라집니다.
            False일시 기존에 등록된 종목과 함께 실시간 정보를 받습니다.
            Default로 False입니다.
        """
        self._send_to_proxy({'method': 'request_price_register', 'args': {'stock_code_list': stock_code_list, 'is_add': is_add}})

    @trace
    def register_ask_bid_info(self, stock_code_list: list[str], is_add: bool = False) -> None:
        """
        주어진 주식 코드에 대한 실시간 호가 정보를 등록합니다.

        Parameters
        ----------
        stock_code_list : list[str]
            실시간 정보를 등록하고 싶은 주식의 코드 리스트입니다.
        is_add : bool, optional
            True일시 화면번호에 존재하는 기존의 등록은 사라집니다.
            False일시 기존에 등록된 종목과 함께 실시간 정보를 받습니다.
            Default로 False입니다.
        """
        self._send_to_proxy({'method': 'request_ask_bid_register', 'args': {'stock_code_list': stock_code_list, 'is_add': is_add}})

    @trace
    def get_price_info(self, stock_code: str) -> dict:
        """
        주어진 주식 코드에 대한 실시간 가격 정보를 가져옵니다.
        주식시장이 과열되면 일정시간동안 거래가 중지되어 정보가 들어오지 않을 수 있습니다.

        Parameters
        ----------
        stock_code : str
            실시간 정보를 가져올 주식 코드입니다.

        Returns
        -------
        dict
            주어진 주식 코드의 실시간 가격 정보입니다.
            info_dict = {
                '체결시간': str (HHMMSS),
                '현재가': int,
                '시가': int,
                '고가': int,
                '저가': int,
            }
        """
        cur_price_info = self._price_info[stock_code]
        cur_time = datetime.datetime.now().replace(year=1900, month=1, day=1)
        info_time: datetime.datetime = cur_price_info['체결시간']
        time_delta = cur_time - info_time
        if time_delta.total_seconds() > 10:
            logger.warning('!!! 실시간 체결 데이터의 시간이 실제 시간과 큰 차이가 있습니다. !!!')
            logger.warning('!!! 주식이 상/하한가이거나 과열될 경우 일어날 수 있습니다. !!!')
            logger.warning(f'!!! {stock_code} - {info_time} vs {cur_time} !!!')
        return cur_price_info
    
    @trace
    def get_ask_bid_info(self, stock_code: str) -> dict:
        """
        주어진 주식 코드에 대한 실시간 호가 1. 정보를 가져옵니다.
        주식시장이 과열되면 일정시간동안 거래가 중지되어 정보가 들어오지 않을 수 있습니다.

        Parameters
        ----------
        stock_code : str
            실시간 정보를 가져올 주식 코드입니다.

        Returns
        -------
        dict
            주어진 주식 코드의 실시간 호가 정보입니다.
           info_dict = {
                '호가시간': str (HHMMSS),
                '매수호가정보': list[tuple[int, int]],
                '매도호가정보': list[tuple[int, int]],
            }
            
            매수호가정보는 (가격, 수량)의 호가정보가 리스트에 1번부터 10번까지 순서대로 들어있습니다.
            매도호가정보도 마찬가지입니다.
        """
        cur_ask_bid_info = self._ask_bid_info[stock_code]
        cur_time = datetime.datetime.now().replace(year=1900, month=1, day=1)
        info_time: datetime.datetime = cur_ask_bid_info['호가시간']
        time_delta = cur_time - info_time
        if time_delta.total_seconds() > 10:
            logger.warning('!!! 실시간 호가 데이터의 시간이 실제 시간과 큰 차이가 있습니다. !!!')
            logger.warning('!!! 주식이 상/하한가이거나 과열될 경우 일어날 수 있습니다. !!!')
            logger.warning(f'!!! {stock_code} - {info_time} vs {cur_time} !!!')
        return cur_ask_bid_info
            
    