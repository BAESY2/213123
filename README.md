# BTC 5-min Bot — 폴리마켓 비트코인 5분 업/다운 자동매매 봇

폴리마켓의 **비트코인 5분 Up/Down** 마켓에서, 외부 가격 모멘텀과 오더북 임밸런스를
결합한 신호로 자동 매매하는 봇입니다. Python으로 작성되었고 **드라이런(기본) / 라이브**
스위치를 가집니다.

---

## ⚠️ 먼저 솔직하게 (꼭 읽어주세요)

- **$40 → 3시간 → $1,000(25배) → $10,000** 목표는 사실상 **도박**입니다. 5분 Up/Down은
  본질적으로 동전 던지기에 가깝고, 스프레드·수수료 때문에 **기대값은 마이너스**입니다.
  어떤 전략도 3시간 안에 25배를 **신뢰성 있게** 만들 수 없습니다. 25배가 나오려면
  사실상 연속으로 운이 따라야 하며, 그 확률은 매우 낮습니다 (50%씩 이긴다고 가정해도
  $40→$1000은 거의 5연속 올인 수준).
- 그래서 이 봇은 **"잃어도 되는 돈"** 전제하에, 요청하신 **공격적 복리 모드**를
  옵션으로 제공합니다. 기본값은 안전한 **드라이런**이며, 실제 주문은 `ENABLE_LIVE=true`
  일 때만 나갑니다.
- 이 코드는 교육/연구용이며 투자 자문이 아닙니다. 손실 책임은 본인에게 있습니다.

---

## 빠른 시작 (Windows, 더블클릭)

### 방법 A — 원클릭 실행 (`start.bat`)
1. [Python 3.9+](https://www.python.org/downloads/) 설치 (설치 시 **Add Python to PATH** 체크).
2. `start.bat` **더블클릭** → 가상환경 생성·의존성 설치·`.env` 생성·봇 실행까지 자동.
3. 기본은 **드라이런**(실주문 없음). 콘솔에서 신호/가상 손익을 확인하세요.

### 방법 B — 진짜 `.exe` 파일로
- 로컬에서: `build_exe.bat` 더블클릭 → `dist\btc5m-bot.exe` 생성. `.env`를 exe 옆에 두고 실행.
- **Python 설치 없이** 받고 싶으면: GitHub **Actions → Build Windows EXE → Run workflow**
  실행 후, 완료되면 `btc5m-bot-windows` 아티팩트(`btc5m-bot.exe`)를 다운로드.
  (`v*` 태그를 푸시하면 릴리스에 자동 첨부됩니다.)

### 직접 실행 (Mac/Linux/개발자)
```bash
pip install -r requirements.txt
cp .env.example .env
python run_bot.py
```

---

## 라이브 거래 켜기

`.env`를 열고:
```ini
ENABLE_LIVE=true
POLYMARKET_PRIVATE_KEY=0x...        # USDC가 있고 폴리마켓 승인된 Polygon 지갑 키
SIGNATURE_TYPE=0                    # 이메일/매직 지갑이면 1, 프록시면 2 + FUNDER 주소
```
- 라이브 전에 지갑이 USDC를 보유하고, 폴리마켓 컨트랙트에 **allowance 승인**이 되어 있어야
  주문이 체결됩니다 (py-clob-client 문서 참고).
- 키는 절대 커밋하지 마세요. `.env`는 `.gitignore`에 포함되어 있습니다.

---

## 공격적 복리 모드 ("모 아니면 도")

요청하신 $40 → $1,000 → $10,000 플랜은 `.env`에서:
```ini
COMPOUNDING=true            # 고정 베팅 대신 잔고의 일정 비율 베팅 → 복리
BANKROLL_FRACTION=0.5       # 매 트레이드마다 현재 잔고의 50% 베팅 (높을수록 고변동/고위험)
START_BANKROLL=40
BANKROLL_TARGET=1000        # 잔고가 이 값에 도달하면 자동 중지(익절)
BANKROLL_FLOOR=0            # 이 값 이하로 내려가면 자동 중지(손절)
SESSION_MINUTES=180         # 3시간 후 자동 종료
```
- `BANKROLL_FRACTION`을 높일수록(예: 1.0 = 올인) 25배 도달 가능성은 생기지만, **한 번만 져도
  대부분/전부를 잃습니다.** 이게 "모 아니면 도"의 실제 의미입니다.
- 목표($1,000) 도달 시 자동으로 멈추므로, 다음 목표($10,000)는 `BANKROLL_TARGET`을 올려
  재시작하면 됩니다.

---

## 전략 (둘 다 결합)

`src/strategy.py` — 플러그인 구조:

1. **가격 모멘텀**: 외부 BTC 스팟(기본 Binance)의 최근 `MOMENTUM_LOOKBACK_SEC` 수익률을
   `tanh`로 [-1,1] 스케일링.
2. **오더북 임밸런스**: 폴리마켓 CLOB의 Up 토큰 상위 호가 매수/매도 잔량 불균형.
3. 가중합(`MOMENTUM_WEIGHT`)으로 `P(Up)` 추정 → **시장가 대비 엣지(edge)** 계산.
4. `MIN_CONFIDENCE` & `MIN_EDGE`를 모두 넘고, 5분 창의 마지막 `DECISION_WINDOW_SEC`
   구간일 때만 1회 진입 (창 마감 직전이 신호가 가장 선명).

리스크 게이트(`src/risk.py`): 일일 거래 한도, 최대 오픈 노출, 가격 밴드(`MIN/MAX_PRICE`),
세션 시간/목표/손절 자동 중지.

---

## 마켓 탐색

5분 마켓은 타임스탬프로 **결정론적**으로 찾습니다:
```
window_ts = now - (now % 300)
slug      = f"btc-updown-5m-{window_ts}"
GET {gamma}/events?slug=<slug>   → markets[].clobTokenIds (Up/Down)
```
폴리마켓 측 slug 패턴이 바뀌면 `.env`의 `SLUG_TEMPLATE`만 수정하면 됩니다.

---

## 구조
```
run_bot.py            # 진입점 (exe 빌드 타깃)
start.bat             # Windows 원클릭 실행(환경 자동 셋업)
build_exe.bat         # PyInstaller로 .exe 빌드
btc5m-bot.spec        # PyInstaller 스펙
.github/workflows/    # Windows .exe 자동 빌드 CI
src/
  config.py           # .env 설정
  price_feed.py       # BTC 가격 피드 + 모멘텀
  polymarket.py       # 마켓 탐색 + CLOB 주문 래퍼
  strategy.py         # 결합 신호 + 진입 게이트
  risk.py             # 사이징/복리/중지 조건
  executor.py         # 드라이런/라이브 주문
  bot.py              # 메인 루프
tests/                # pytest 단위 테스트
```

테스트: `pip install pytest && python -m pytest -q`

---

## 참고한 오픈소스
- [Polymarket/py-clob-client](https://github.com/Polymarket/py-clob-client) (및 [v2](https://github.com/Polymarket/py-clob-client-v2)) — 공식 CLOB 클라이언트
- [handiko/Polymarket-Market-Finder](https://github.com/handiko/Polymarket-Market-Finder) — 타임스탬프 기반 마켓 탐색
- [Archetapp — BTC 5-Minute Up/Down Trading Bot (gist)](https://gist.github.com/Archetapp/7680adabc48f812a561ca79d73cbac69) — 5분 봇 슬러그/주문 흐름
- [Polymarket Docs](https://docs.polymarket.com/api-reference/clients-sdks)
