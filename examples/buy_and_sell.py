import easykiwoom
import time

market = easykiwoom.Market()
market.initialize(logging_level='INFO')

stocks = ['005930', '000660', '035420', '035720', '051910']

balance = market.get_balance()
deposit = market.get_deposit()
print(f'잔고: {balance}')
print(f'예수금: {deposit}')

for stock in stocks:
    order = {
        '구분': '매수',
        '주식코드': stock,
        '수량': 1,
        '가격': 0,
        '시장가': True
    }
    order_number = market.send_order(order)
    _ = market.get_order_result(order_number)

balance = market.get_balance()
deposit = market.get_deposit()
print(f'잔고: {balance}')
print(f'예수금: {deposit}')

time.sleep(10)

for stock in stocks:
    order = {
        '구분': '매도',
        '주식코드': stock,
        '수량': 1,
        '가격': 0,
        '시장가': True
    }
    order_number = market.send_order(order)
    _ = market.get_order_result(order_number)

balance = market.get_balance()
deposit = market.get_deposit()
print(f'잔고: {balance}')
print(f'예수금: {deposit}')

market.terminate()