
# 쉽고 간편한 키움증권 API, easy-kiwoom

## 특징

### 1. 높은 수준의 추상화
```python
import easykiwoom

market = easykiwoom.Market()
order = {
    '구분': '매수',
    '주식코드': '005930',
    '수량': 10,
    '가격': 0,
    '시장가': True
}
market.send_order(order)
```

기존의 복잡한 키움증권 API 따윈 몰라도 괜찮습니다.

위의 직관적인, 짧은 코드로도 주식을 매수할 수 있습니다.

### 2. 64비트 환경

easy-kiwoom은 실제 API를 호출하는 프록시 프로그램을 따로 동작시킴으로써 사용자에게 64비트 환경을 제공합니다.

### 3. thread-safe

easy-kiwoom은 모든 요청을 queue에 담아 순차적으로 처리함으로써 thread-safe함을 보장합니다.

<br/>

## 사용 방법

Market 객체를 생성하고, 이의 메소드를 호출함으로써 주식거래를 진행할 수 있습니다.
대표적으로 아래와 같은 기능을 제공합니다.
자세한 명세는 메서드의 주석에 상세히 기술되어 있습니다.

1. 주식의 실시간 호가 및 가격 정보를 조회

    `get_price_info`, `get_ask_bid_info`

2. 주식을 (시장가 / 지정가)로 (매수 / 매도), 혹은 취소

    `send_order`, `cancel_order`

3. 영웅문 상의 조건검색식에 맞는 주식을 조회

    `get_matching_stocks`

4. 보유 주식 정보 조회

    `get_balance`

5. 주문 가능 금액 조회

    `get_deposit`

<br/>

## 사용 예시

다양한 사용 예시는 깃헙 레포지토리의 `examples` 폴더를 참고해주세요.

<br/>

## 유의사항 및 자세한 사용방법

1. 주식 거래를 시작하기 전 `initialize` 메서드를 호출해야 합니다.
주식 거래가 끝난 후에는 `terminate` 메서드를 호출해야 합니다.

2. 키움증권 API는 시간 당 요청 제한이 존재합니다. (실시간 가격, 호가 정보는 제외)
따라서 만약 이를 초과한 요청을 보낸다면 easy-kiwoom은 요청이 실패하지 않도록 경고 메시지와 함께 일정 시간 프로그램을 대기시킵니다.

3. 실시간 가격 정보 조회를 하기 전에 `register_price_info` 메서드로 조회할 주식 코드를 한번 등록해야 합니다.
실시간 호가 정보도 마찬가지로 `register_ask_bid_info` 메서드를 통해 등록해야 합니다.

4. `send_order` 메서드를 통해 주식을 매수/매도한 후, `get_order_result` 메서드를 통해 주식이 전부 매수/매도될 때까지, 혹은 취소될 때까지 대기할 수 있습니다.

<br/>


## 설치 방법

### 1. 키움증권 OPEN API+ 신청 및 설치

https://www.kiwoom.com/h/customer/download/VOpenApiInfoView?dummyVal=0

### 2. easykiwoom 패키지 설치
```shell
pip install easykiwoom
```

또는 리포지토리 clone 후
```shell
pip install /path/to/cloned/repository
```

<br/>