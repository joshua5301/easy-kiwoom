def get_kiwoom_price(price: int) -> int:
    kiwoom_price = price
    if kiwoom_price < 2000:
        pass
    elif 2000 <= kiwoom_price < 5000:
        kiwoom_price = kiwoom_price - kiwoom_price % 5
    elif 5000 <= kiwoom_price < 20000:
        kiwoom_price = kiwoom_price - kiwoom_price % 10
    elif 20000 <= kiwoom_price < 50000:
        kiwoom_price = kiwoom_price - kiwoom_price % 50
    elif 50000 <= kiwoom_price < 200000:
        kiwoom_price = kiwoom_price - kiwoom_price % 100
    elif 200000 <= kiwoom_price < 500000:
        kiwoom_price = kiwoom_price - kiwoom_price % 500
    else:
        kiwoom_price = kiwoom_price - kiwoom_price % 1000
    return kiwoom_price

def _get_next_kiwoom_price(price: int) -> int:
    kiwoom_price = get_kiwoom_price(price)
    if kiwoom_price < 2000:
        kiwoom_price += 1
    elif 2000 <= kiwoom_price < 5000:
        kiwoom_price += 5
    elif 5000 <= kiwoom_price < 20000:
        kiwoom_price += 10
    elif 20000 <= kiwoom_price < 50000:
        kiwoom_price += 50
    elif 50000 <= kiwoom_price < 200000:
        kiwoom_price += 100
    elif 200000 <= kiwoom_price < 500000:
        kiwoom_price += 500
    else:
        kiwoom_price += 1000
    return kiwoom_price

def _get_prev_kiwoom_price(price: int) -> int:
    return get_kiwoom_price(price - 1) if price > 0 else 1

def get_shifted_kiwoom_price(price: int, steps: int):
    cur_price = get_kiwoom_price(price)
    if steps > 0:
        for _ in range(abs(steps)):
            cur_price = _get_next_kiwoom_price(cur_price)
    else:
        for _ in range(abs(steps)):
            cur_price = _get_prev_kiwoom_price(cur_price)
    return cur_price

if __name__ == '__main__':
    print(get_shifted_kiwoom_price(1400, 2))