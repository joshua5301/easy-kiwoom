import easykiwoom


market = easykiwoom.Market()
market.connect()
market.initialize()
deposit = market.get_deposit()
balance = market.get_balance()
conditions = market.get_condition()
matching_stocks = market.get_matching_stocks(conditions[0]['name'], conditions[0]['index'])

print(deposit, balance, conditions, matching_stocks, sep='\n')