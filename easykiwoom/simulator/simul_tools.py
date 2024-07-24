import threading
import queue
import time
import datetime
import math
import faulthandler
from collections import defaultdict
from functools import wraps

# faulthandler.dump_traceback_later(10)

OriginalThread = None
OriginalQueue = None
original_sleep = None

_blocked_count_lock = threading.RLock()
_blocked_count = defaultdict(int)
def _trace_blocked(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cur_thread_id = threading.get_ident()
        with _blocked_count_lock:
            _blocked_count[cur_thread_id] += 1
        if _get_nonblocked_thread_num() == 0:
            with _is_all_blocked:
                _is_all_blocked.notify_all()
        try:
            value = func(*args, **kwargs)
        finally:
            with _blocked_count_lock:
                _blocked_count[cur_thread_id] -= 1
        return value
    return wrapper

_thread_count_lock = threading.RLock()
_thread_count = 1
def _trace_thread(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global _thread_count
        try:
            value = func(*args, **kwargs)
        finally:
            with _thread_count_lock:
                _thread_count -= 1
            if _get_nonblocked_thread_num() == 0:
                with _is_all_blocked:
                    _is_all_blocked.notify_all()
        return value
    return wrapper

def _get_nonblocked_thread_num():
    with _thread_count_lock, _blocked_count_lock:
        blocked_thread_num = 0
        for thread_id, num in _blocked_count.items():
            if num >= 1:
                blocked_thread_num += 1
        assert _thread_count - blocked_thread_num >= 0
        return _thread_count - blocked_thread_num

class KiwoomThread:
    """
    주의) run 메서드를 오버라이드하는 대신 생성자의 target 인자로 thread가 실행할 함수를 지정해주세요.
    """
    def __init__(self, group = None, target = None, name = None, args = (), kwargs = None, daemon = None):
        target = _trace_thread(target)
        self._thread = OriginalThread(group, target, name, args, kwargs, daemon=daemon)
    
    def start(self):
        global _thread_count
        with _thread_count_lock:
            _thread_count += 1
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread.is_alive():
            _trace_blocked(self._thread.join)(timeout)

class KiwoomQueue:

    def __init__(self, *args, **kwargs):
        self._queue = OriginalQueue(*args, **kwargs)
    
    def get(self, block: bool = True, timeout: float | None = None):
        if block == True:
            try:
                block = False
                return self._queue.get(block, timeout)
            except:
                block = True
                return _trace_blocked(self._queue.get)(block, timeout)
        else:
            return self._queue.get(block, timeout)
    
    def put(self, item, block: bool = True, timeout: float | None = None):
        if block == True:
            try:
                block = False
                self._queue.put(item, block, timeout)
            except:
                block = True
                _trace_blocked(self._queue.put)(item, block, timeout)
        else:
            self._queue.put(item, block, timeout)
        original_sleep(0.01)
        
_elapsed_seconds = 0
_frozen_datetime = None
_is_all_blocked = threading.Condition()
_first_sleep_barrier = threading.Barrier(0)
_second_sleep_barrier = threading.Barrier(0)
_sleeping_thread_count = 0
_sleep_count_lock = threading.RLock()

def kiwoom_sleep(seconds: float):
    seconds = math.ceil(seconds)
    for _ in range(seconds):
        _sleep_one_second()

def _sleep_one_second():
    global _first_sleep_barrier, _second_sleep_barrier, _sleeping_thread_count, _is_all_blocked
    def time_passes():
        global _elapsed_seconds
        _elapsed_seconds += 1
        _frozen_datetime.tick()
    
    with _sleep_count_lock:
        _sleeping_thread_count += 1
        assert _first_sleep_barrier.n_waiting == 0
        assert _second_sleep_barrier.n_waiting == 0
        _first_sleep_barrier = threading.Barrier(_sleeping_thread_count, action=time_passes)
        _second_sleep_barrier = threading.Barrier(_sleeping_thread_count)
    
    cur_thread_id = threading.get_ident()
    with _blocked_count_lock:
        _blocked_count[cur_thread_id] += 1
    with _is_all_blocked:
        _is_all_blocked.notify_all()
        while _get_nonblocked_thread_num() > 0:
            _is_all_blocked.wait()
    _first_sleep_barrier.wait()
    with _blocked_count_lock:
        _blocked_count[cur_thread_id] -= 1
    with _sleep_count_lock:
        _sleeping_thread_count -= 1
    _second_sleep_barrier.wait()

def get_elapsed_seconds():
    return _elapsed_seconds

def reset_elapsed_seconds():
    global _elapsed_seconds
    _elapsed_seconds = 0