import easykiwoom
import time

market = easykiwoom.Market()
market.initialize(logging_level='INFO')

conditions = market.get_condition_names()
print(conditions)
stocks = market.get_matching_stocks(conditions[0]['name'], conditions[0]['index'])
print(stocks)