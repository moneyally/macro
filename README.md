# ⚡ 매크로 PRO

밀리초 정밀 키보드·마우스 매크로 (Windows). 여러 매크로를 만들어 단축키로 돌리고,
녹화/편집/반복/문구 타이핑/이미지 클릭까지 되는 개인용 자동화 도구.

> ⚠️ 매크로 탐지하는 게임·프로그램엔 쓰지 마세요(계정 정지 위험). 일반 반복작업용입니다.

## 기능
- **여러 매크로 관리** — 목록으로 추가·복사·삭제·순서변경, 각 매크로에 실행 단축키 지정
- **F12 실행↔편집 전환** — 실행 모드에선 지정 단축키로 매크로 발동
- **녹화/재생** — 키보드·마우스·스크롤·이동 기록, 절대 스케줄이라 오래 돌려도 안 밀림
- **동작 조립** — 🖱클릭 / ✎문구 타이핑 / 🔑단축키 / ➡이동 / ⏱대기 / 🖲스크롤 / 🖼이미지 찾아 클릭
- **밀리초 정밀** — `perf_counter` + Windows 타이머 1ms + 하이브리드 슬립
- **한/영(IME) 감지** — 실행 중 영문 고정(문구 타이핑 깨짐 방지)
- **종료 안전** — 눌린 키/버튼 모두 떼기, 마우스 위치 복구
- **F8 좌표 찍기**, 반복(무한), 배속, 타이밍 랜덤(사람처럼)
- `.m` 파일로 저장/불러오기

## 실행
```
pip install -r requirements.txt
python run.py
```

## exe 만들기
- **로컬**: `build_exe.bat` 더블클릭 → `dist/MacroPRO.exe`
- **자동(GitHub Actions)**: 이 저장소에 push 하면 `build-windows-exe` 워크플로우가
  윈도우 exe 를 만들어 Artifacts 로 올립니다.

## 구조
```
run.py                  진입점
macropro/
  timing.py             밀리초 타이밍(perf_counter·winmm·하이브리드 슬립)
  keys.py               키/버튼 직렬화·조합키 파싱
  ime.py                한/영 IME 감지·전환(ctypes imm32)
  engine.py             입력 조작 + 눌린키 추적·모두 떼기
  recorder.py           녹화
  player.py             재생(주기·반복·복구·IME·절대 스케줄)
  model.py              Macro / MacroSet / .m 파일
  ui/
    theme.py            색·폰트 토큰(웜 팔레트)
    widgets.py          둥근 버튼·카드·알약 위젯(Canvas)
    editor.py           동작 편집 창
    app.py              메인 창
```

## 단축키
- `F8` 좌표 찍기 · `F9` 녹화 시작/정지 · `F10` 정지 · `F12` 실행↔편집 전환

오픈소스 기반: [pynput](https://github.com/moses-palmer/pynput) ·
[pyautogui](https://github.com/asweigart/pyautogui) · [pillow](https://python-pillow.org/)
