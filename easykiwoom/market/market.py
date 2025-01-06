import copy
import logging
import os
import sys
import queue
import json
import subprocess
import socket
import threading
import psutil
import signal
from collections import defaultdict
from .market_utils import *

logger = logging.getLogger(__name__)

class Market():
    """
    주식시장을 구현한 클래스
    
    Client는 이 클래스의 메서드를 통해 주식과 계좌 정보를 얻고 이를 바탕으로 매매할 수 있습니다.
    여러 쓰레드가 동시에 메서드를 호출해도 안전합니다.
    """

    _only_instance = None
    def __new__(cls, *args, **kwargs):
        if cls._only_instance is None:
            cls._only_instance = super(Market, cls).__new__(cls, *args, **kwargs)
        return cls._only_instance
    
    def __init__(self):
        self._result_buffer = defaultdict(dict)
        self._result_buffer_lock = threading.Lock()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket_buffer = ''
        self._socket_buffer_size = 8192
        self._socket_lock = threading.Lock()
        self._receiver_thread = threading.Thread(target=self._handle_proxy_responses, name='kiwoomproxy_receiver', daemon=True)
        self._resetter_thread = threading.Thread(target=reset_API_call_count, name='API_call_count_resetter', daemon=True)

        self._balance = None
        self._price_info = {}
        self._ask_bid_info = {}
    
    def _request_to_proxy(self, method: str, kwargs: dict) -> None:
        """
        요청 정보를 키움증권 프록시에 전달합니다.

        Parameters
        ----------
        method : str
            프록시에서 실행시킬 함수 이름입니다.
        kwargs : dict
            프록시에서 실행시킬 함수의 인자입니다.
        """
        data = (json.dumps({'method': method, 'kwargs': kwargs}) + '\n').encode()
        with self._socket_lock:
            self._socket.sendall(data)
    
    def _receive_from_proxy(self) -> dict:
        """
        프록시로부터 받은 데이터를 하나 반환합니다.

        Returns
        -------
        dict
            프록시가 서버로부터 전달받은 결과 데이터입니다.
        """
        chunk = self._socket.recv(self._socket_buffer_size)
        if not chunk:
            raise ConnectionError("프록시와의 연결이 끊어졌습니다.")
        self._socket_buffer += chunk.decode()
        parts = self._socket_buffer.split('\n')
        responses, self._socket_buffer = parts[:-1], parts[-1]
        responses = [json.loads(response) for response in responses]
        return responses
    
    def _handle_proxy_responses(self):
        """
        프록시로부터 전달받은 요청의 결과들을 받고 알맞은 메서드로 전달합니다.
        이 과정을 계속해서 반복합니다.
        """
        while True:
            try:
                responses = self._receive_from_proxy()
            except ConnectionError:
                break
            for response in responses:
                type, key, value = response['type'], response['key'], response['value']
                if type == 'balance_change':
                    balance_change = value
                    if balance_change['보유수량'] == 0:
                        del self._balance[balance_change['종목코드']]
                    else:
                        self._balance[balance_change['종목코드']] = balance_change
                # 역전 현상 방지
                elif type == 'order_result':
                    order_number = key
                    with self._result_buffer_lock:
                        if order_number not in self._result_buffer[type]:
                            self._result_buffer[type][order_number] = queue.Queue(maxsize=1)
                    self._result_buffer[type][order_number].put(value, block=False)
                elif type == 'price_change':
                    self._price_info[key] = value
                elif type == 'ask_bid_change':
                    self._ask_bid_info[key] = value
                else:
                    self._result_buffer[type][key].put(value, block=False)
    
    def _get_all_tr_results(self, method_name: str, kwargs: dict) -> list:
        """
        TR 요청을 연속조회한 값을 가져옵니다.

        Parameters
        ----------
        method_name : str
            프록시에서 호출할 TR 요청 메서드입니다.
        kwargs : dict
            호출할 TR 요청 메서드의 인자입니다.

        Returns
        -------
        list
            연속조회한 값이 순차적으로 담겨저 있는 리스트입니다.
        """
        def _get_tr_result(method_name: str, kwargs: dict):
            request_name = get_unique_request_name()
            self._result_buffer['tr_result'][request_name] = queue.Queue(maxsize=1)
            kwargs['request_name'] = request_name
            self._request_to_proxy(method_name, kwargs)
            tr_result, is_next = self._result_buffer['tr_result'][request_name].get()
            del self._result_buffer['tr_result'][request_name]
            return tr_result, is_next
        tr_results = []
        is_next = 2
        while is_next == 2:
            tr_result, is_next = _get_tr_result(method_name, kwargs)
            tr_results.append(tr_result)
        return tr_results

    @trace
    def initialize(self, logging_level: str = 'ERROR') -> None:
        """
        키움증권 프록시와 연결하고 주식시장을 초기화합니다.
        (로그인 -> 계좌번호 로드 -> 초기 잔고 로드)
        
        다른 메서드를 사용하기 전에 오직 한번만 호출되어야 합니다.

        Parameters
        ----------
        logging_level : str, optional
            로깅 레벨을 설정합니다.
            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' 중 하나를 선택할 수 있습니다.
            
            프로그램이 잘 동작하는지 확인하고 싶을 때는 'INFO'를 사용하고,
            일반적인 사용시에는 'ERROR'를 사용하는 것을 추천합니다.
        """
        exe_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'kiwoom_proxy.exe')
        self.proxy = subprocess.Popen(
            [exe_path, logging_level],
            stdin=None,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        while True:
            try:
                self._socket.connect(('127.0.0.1', 53939))
                break
            except ConnectionRefusedError:
                time.sleep(1)

        def signal_handler(sig, frame):
            self.terminate()
            raise KeyboardInterrupt
        signal.signal(signal.SIGINT, signal_handler)

        self._receiver_thread.start()
        self._resetter_thread.start()

        while True:
            self._result_buffer['login_result'][''] = queue.Queue(maxsize=1)
            self._request_to_proxy('login', {})
            login_result = self._result_buffer['login_result'][''].get()
            del self._result_buffer['login_result']['']
            if login_result == 0:
                break

        self._request_to_proxy('load_account_number', {})
        
        tr_results = self._get_all_tr_results('get_balance', {})
        balance = {}
        for tr_result in tr_results:
            balance = balance | tr_result
        self._balance = balance

    @trace
    def terminate(self) -> None:
        """
        키움증권 프록시를 종료합니다.
        """
        self._socket.close()
        parent = psutil.Process(self.proxy.pid)
        for child in parent.children(recursive=True):
            child.terminate()

    @request_api_method
    @trace
    def get_condition_names(self) -> list[dict]:
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

        self._result_buffer['condition_names'][''] = queue.Queue(maxsize=1)
        self._request_to_proxy('get_condition_names', {})
        condition_list = self._result_buffer['condition_names'][''].get()
        del self._result_buffer['condition_names']['']
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
        
        self._result_buffer['matching_stocks'][condition_name] = queue.Queue(maxsize=1)
        self._request_to_proxy('get_matching_stocks', {'condition_name': condition_name, 'condition_index': condition_index})
        matching_stocks = self._result_buffer['matching_stocks'][condition_name].get()
        del self._result_buffer['matching_stocks'][condition_name]
        return matching_stocks

    @request_api_method
    @trace
    def get_stocks_with_volume_spike(self, criterion: str) -> list[str]:
        """
        거래량이 급증한 주식들을 가져옵니다.

        Parameters
        ----------
        criterion : str
            '증가량'의 경우, 전일 대비 절대적인 거래량으로 계산됩니다.
            '증가율'의 경우, 전일 대비 상대적인 거래량으로 계산됩니다.

        Returns
        -------
        list[str]
            거래량 기준 내림차순으로 정렬된 주식 코드 리스트를 반환합니다.
        """
        tr_results = self._get_all_tr_results('get_stocks_with_volume_spike', {'criterion': criterion})
        tr_results = [stock_code for tr_result in tr_results for stock_code in tr_result]
        return tr_results
    
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
        tr_results = self._get_all_tr_results('get_deposit', {})
        return tr_results[0]

    @trace
    def get_balance(self) -> dict[str, dict]:
        """
        보유주식정보를 반환합니다.

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
        return copy.deepcopy(self._balance)
    
    @order_api_method
    @trace
    def send_order(self, order_dict: dict) -> str:
        """
        주문을 전송합니다.
        시장가 주문을 전송할 경우 가격은 0으로 전달해야 합니다.

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

        Returns
        -------
        str
            unique한 주문 번호를 반환합니다.
        """
        request_name = get_unique_request_name()
        self._result_buffer['tr_result'][request_name] = queue.Queue(maxsize=1)
        self._request_to_proxy('send_order', {'order_dict': order_dict, 'request_name': request_name})
        tr_results = self._result_buffer['tr_result'][request_name].get()
        order_number = tr_results[0]
        del self._result_buffer['tr_result'][request_name]
        return order_number
    
    @order_api_method
    @trace
    def cancel_order(self, order_dict: dict):
        """
        지정가 주문을 취소합니다.
        수량을 0으로 입력할 경우, 주문이 전량 취소됩니다.

        Parameters
        ----------
        order_dict : dict
            order_dict = {
                '구분': '매수취소' or '매도취소',
                '주식코드': str,
                '수량': int,
                '원주문번호': str,
            }
            
        """
        request_name = get_unique_request_name()
        self._result_buffer['tr_result'][request_name] = queue.Queue(maxsize=1)
        self._request_to_proxy('cancel_order', {'order_dict': order_dict, 'request_name': request_name})
        tr_results = self._result_buffer['tr_result'][request_name].get()
        order_number = tr_results[0]
        del self._result_buffer['tr_result'][request_name]
        
        with self._result_buffer_lock:
            if order_number not in self._result_buffer['order_result']:
                self._result_buffer['order_result'][order_number] = queue.Queue(maxsize=1)
        _ = self._result_buffer['order_result'][order_number].get()
        
 
    @trace
    def get_order_result(self, order_number: str) -> dict:
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
            info_dict = {
                '종목코드': str,
                '종목명': str,
                '주문상태': str,
                '주문구분': str,
                '주문수량': int,
                '체결가': int,
                '체결량': int,
                '미체결수량': int,
                '주문번호': str,
            }
        """
        with self._result_buffer_lock:
            if order_number not in self._result_buffer['order_result']:
                self._result_buffer['order_result'][order_number] = queue.Queue(maxsize=1)
        while True:
            order_result = self._result_buffer['order_result'][order_number].get()
            if order_result['미체결수량'] == 0:
                break
        return order_result
    
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
        self._request_to_proxy('register_price_info', {'stock_code_list': stock_code_list, 'is_add': is_add})

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
        self._request_to_proxy('register_ask_bid_info', {'stock_code_list': stock_code_list, 'is_add': is_add})

    @request_api_method
    @trace
    def _get_price_info(self, stock_code: str) -> dict:
        tr_results = self._get_all_tr_results('get_price_info', {'stock_code': stock_code})
        return tr_results[0]
    
    @request_api_method
    @trace
    def _get_ask_bid_info(self, stock_code: str) -> dict:
        tr_results = self._get_all_tr_results('get_ask_bid_info', {'stock_code': stock_code})
        return tr_results[0]
    
    @trace
    def get_price_info(self, stock_code: str, wait_time: int = 3) -> dict:
        """
        주어진 주식 코드에 대한 실시간 가격 정보를 가져옵니다.
        register_price_info가 한번 선행되어야 합니다.

        거래가 드물거나 중지되면 정보가 들어오지 않을 수 있습니다.
        이 경우 일정 시간 기다린 뒤에 직접적인 정보 요청을 시도합니다.
        다만 그럴 경우 API 조회 요청 횟수에 포함됩니다.

        Parameters
        ----------
        stock_code : str
            실시간 정보를 가져올 주식 코드입니다.

        wait_time : int, optional
            직접적인 정보 요청을 시도하기 전 대기할 시간입니다.
            Default로 3초입니다.

        Returns
        -------
        dict
            주어진 주식 코드의 실시간 가격 정보입니다.
            info_dict = {
                '현재가': int,
                '시가': int,
                '고가': int,
                '저가': int,
            }
        """
        cur_price_info = None
        while True:
            try:
                cur_price_info = self._price_info[stock_code]
                break
            except KeyError:
                if wait_time <= 0:
                    break
                time.sleep(1)
                wait_time -= 1

        if cur_price_info is None:
            self._price_info[stock_code] = self._get_price_info(stock_code)
            cur_price_info = self._price_info[stock_code]
        return cur_price_info
    
    @trace
    def get_ask_bid_info(self, stock_code: str, wait_time: int = 3) -> dict:
        """
        주어진 주식 코드에 대한 실시간 호가 정보를 가져옵니다.
        register_ask_bid_info가 한번 선행되어야 합니다.

        거래가 드물거나 중지되면 정보가 들어오지 않을 수 있습니다.
        이 경우 일정 시간 기다린 뒤에 직접적인 정보 요청을 시도합니다.
        다만 그럴 경우 API 조회 요청 횟수에 포함됩니다.

        Parameters
        ----------
        stock_code : str
            실시간 정보를 가져올 주식 코드입니다.
        
        wait_time : int, optional
            직접적인 정보 요청을 시도하기 전 대기할 시간입니다.
            Default로 3초입니다.

        Returns
        -------
        dict
            주어진 주식 코드의 실시간 호가 정보입니다.
           info_dict = {
                '매수호가정보': list[tuple[int, int]],
                '매도호가정보': list[tuple[int, int]],
            }
            
            매수호가정보는 (가격, 수량)의 호가정보가 리스트에 1번부터 10번까지 순서대로 들어있습니다.
            매도호가정보도 마찬가지입니다.
        """
        cur_ask_bid_info = None
        while True:
            try:
                cur_ask_bid_info = self._ask_bid_info[stock_code]
                break
            except KeyError:
                if wait_time <= 0:
                    break
                time.sleep(1)
                wait_time -= 1

        if cur_ask_bid_info is None:
            self._ask_bid_info[stock_code] = self._get_ask_bid_info(stock_code)
            cur_ask_bid_info = self._ask_bid_info[stock_code]
        return cur_ask_bid_info
            
    