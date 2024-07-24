
# 🚧 공사중!! 아직 사용 불가합니다. 🚧

이 프로그램을 사용함으로써 직간접적으로 발생한 모든 손해에 대해 책임지지 않습니다.

<br/>
<br/>
<br/>

# 쉽고 간편한 키움증권 API, easy-kiwoom

## 사용 방법

### 1. 키움증권 OPEN API+ 신청 및 설치

https://www.kiwoom.com/h/customer/download/VOpenApiInfoView?dummyVal=0

### 2. easykiwoom 패키지 설치
```shell
pip install easykiwoom (예정)
```

또는 리포지토리 clone 후
```shell
pip install /path/to/cloned/repository
```

<br/>

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

### 2. 간편한 backtrading

```python
import easykiwoom

simulator = easykiwoom.Simulator()
simulator.set_simul_data('./your/data/path')
simulator.simulate('your_strategy')
```

소스코드 수정없이 전략을 간편하게 검증해보세요.

### 3. 64비트 환경

easy-kiwoom은 실제 API를 호출하는 프록시 프로그램을 따로 동작시킴으로써 사용자에게 64비트 환경을 제공합니다.