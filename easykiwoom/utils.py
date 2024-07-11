import logging
import time
import datetime
import threading
from typing import Callable

cur_key_num = 0
def get_unique_request_name() -> str:
    """
    unique한 임의의 요청 이름을 만들고 반환합니다.

    Returns
    -------
    str
        요청 이름을 반환합니다.
    """
    global cur_key_num
    request_name = f'{cur_key_num:06}'
    cur_key_num += 1
    if cur_key_num >= 1000000:
        raise RuntimeError('너무 많은 이름이 생성돼 더 이상 unique 해질 수 없습니다.')
    return request_name

def trace(func: Callable) -> Callable:
    """
    함수의 시작과 끝을 trace하는 decorator 입니다.
    log level은 DEBUG입니다.

    Parameters
    ----------
    func : Callable
        trace 당할 함수입니다.

    Returns
    -------
    Callable
        시작과 끝을 logging하는 함수를 반환합니다.
    """
    def wrapper(*args, **kwargs):
        logging.debug(f'{threading.current_thread().name} at {datetime.datetime.now()}:')
        logging.debug(f'    {func.__name__} starts with args - {args}, kwargs - {kwargs}')
        result = func(*args, **kwargs)
        logging.debug(f'{threading.current_thread().name} at {datetime.datetime.now()}:')
        logging.debug(f'    {func.__name__} ends with return value - {result}')
        return result
    return wrapper

_request_api_num_per_second = 0
def request_api_method(func: Callable) -> Callable:
    """ 
    키움증권 데이터 조회 요청을 하는 함수는 이 decorator를 사용함으로써 
    과도한 조회로 인한 조회 실패를 방지해야합니다.

    Parameters
    ----------
    func : Callable
        조회를 요청하는 함수입니다.

    Returns
    -------
    Callable
        최근에 호출한 조회 API 횟수에 따라 잠깐 기다리는 closure를 반환합니다.
    """
    
    lock = threading.Lock()
    def wrapper(*args, **kwargs):
        
        # 만약 1초 내로 요청이 3번 이상 왔다면 1초 기다립니다.
        global _request_api_num_per_second
        with lock:
            if _request_api_num_per_second >= 3:
                logging.warning('!!! 너무 많은 조회 요청이 접수되어 1초 기다립니다. !!!')
                logging.warning('!!! 조회 요청의 경우 추가적인 제한에 걸릴 수 있으므로 로직을 수정하는 것을 권합니다. !!!')
                time.sleep(1)
            _request_api_num_per_second += 1
            
        result = func(*args, **kwargs)
        return result
    return wrapper

_order_api_num_per_second = 0
def order_api_method(func: Callable) -> Callable:
    """
    키움증권 주문 요청하는 함수는 이 decorator를 사용함으로써 
    과도한 주문으로 인한 주문 실패를 방지해야합니다.

    Parameters
    ----------
    func : Callable
        주문을 요청하는 함수입니다.

    Returns
    -------
    Callable
        최근에 호출한 주문 API 횟수에 따라 잠깐 기다리는 closure를 반환합니다.
    """
    lock = threading.Lock()
    def wrapper(*args, **kwargs):
        
        # 만약 1초 내로 주문 요청이 3번 이상 왔다면 1초 기다립니다.
        global _order_api_num_per_second
        with lock:
            if _order_api_num_per_second >= 3:
                logging.warning('!!! 너무 많은 주문 요청이 접수되어 1초 기다립니다. !!!')
                time.sleep(1)
            _order_api_num_per_second += 1
            
        result = func(*args, **kwargs)
        return result
    return wrapper

def reset_API_call_count():
    """
    API 호출 횟수를 1초마다 초기화해줍니다.
    """
    global _order_api_num_per_second
    global _request_api_num_per_second
    while True:
        time.sleep(1)
        _order_api_num_per_second = 0
        _request_api_num_per_second = 0