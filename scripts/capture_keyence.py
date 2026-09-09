"""키엔스 코드 리더기 원문 출력 캡처 도구 (A단계 — 프로토콜 확인용).

리더기(TCP 서버)에 접속해 수신 바이트를 그대로 화면과 파일에 남긴다.
앱 코드와 독립적이며, 리더기 외 어떤 서버에도 접속하지 않는다.

사용 예:
  # 데이터 포트에 붙어 리더기 버튼/외부 트리거로 판독한 결과를 60초간 수집
  python scripts/capture_keyence.py --host 192.168.0.10 --port 9004 --duration 60 --tag full

  # 접속 직후 명령 포트에 트리거 문자열을 보내고 응답 수집 (명령·포트 번호는 모델 매뉴얼 확인)
  python scripts/capture_keyence.py --host 192.168.0.10 --port 9004 --send "LON\r" --duration 15 --tag partial

출력:
  tests/fixtures/qr_reader/<날짜시각>_<tag>.raw   — 수신 바이트 원본 (수정 금지)
  tests/fixtures/qr_reader/<날짜시각>_<tag>.txt   — 제어문자를 <CR><LF><TAB> 등으로 표시한 가독 버전
"""
from __future__ import annotations

import argparse
import datetime as _dt
import socket
import sys
import time
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "qr_reader"

_CTRL = {
    0x0D: "<CR>",
    0x0A: "<LF>\n",
    0x09: "<TAB>",
    0x02: "<STX>",
    0x03: "<ETX>",
    0x1C: "<FS>",
    0x1D: "<GS>",
    0x1E: "<RS>",
}


def make_readable(data: bytes) -> str:
    out = []
    for b in data:
        if b in _CTRL:
            out.append(_CTRL[b])
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append(f"<{b:02X}>")
    return "".join(out)


def unescape_send(text: str) -> bytes:
    """--send 인자의 \\r \\n \\t 표기를 실제 제어문자로 변환."""
    return text.encode("utf-8").decode("unicode_escape").encode("latin-1")


def capture(host: str, port: int, duration: float, send: str | None, tag: str) -> Path:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = FIXTURE_DIR / f"{stamp}_{tag}.raw"
    txt_path = FIXTURE_DIR / f"{stamp}_{tag}.txt"

    print(f"[connect] {host}:{port} ...", flush=True)
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(1.0)
        print("[connected]", flush=True)
        if send:
            payload = unescape_send(send)
            sock.sendall(payload)
            print(f"[sent] {make_readable(payload)}", flush=True)

        chunks: list[bytes] = []
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                print("[closed by reader]", flush=True)
                break
            chunks.append(chunk)
            print(make_readable(chunk), end="", flush=True)

    data = b"".join(chunks)
    raw_path.write_bytes(data)
    txt_path.write_text(
        f"# host={host} port={port} send={send!r} duration={duration}s bytes={len(data)}\n"
        + make_readable(data),
        encoding="utf-8",
    )
    print(f"\n[saved] {raw_path} ({len(data)} bytes)\n[saved] {txt_path}", flush=True)
    return raw_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True, help="리더기 IP")
    ap.add_argument("--port", type=int, required=True, help="데이터(또는 명령) 포트")
    ap.add_argument("--duration", type=float, default=30.0, help="수집 시간(초), 기본 30")
    ap.add_argument("--send", default=None, help='접속 직후 보낼 문자열 (예: "LON\\r")')
    ap.add_argument("--tag", default="capture", help="파일명 태그 (full / partial / empty / rotated / dup 등)")
    args = ap.parse_args(argv)
    try:
        capture(args.host, args.port, args.duration, args.send, args.tag)
    except OSError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
