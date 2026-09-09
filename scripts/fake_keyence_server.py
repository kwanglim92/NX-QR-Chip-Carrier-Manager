"""가짜 SR-X300W TCP 서버 — 하드웨어 없이 앱/클라이언트를 시험한다.

실제 캡처 fixture(`tests/fixtures/qr_reader/*.raw`)를 그대로 재생하며, 확정된 프로토콜(설계 §3.2)을 흉내 낸다:
  - 레벨 트리거: ``LON`` 을 받으면 대기, ``LOFF`` 를 받을 때 프레임 출력 (``--immediate`` 면 LON 즉시 출력)
  - ``LON``/``LOFF`` 에는 응답 없음, ``KEYENCE`` → ``OK,KEYENCE,FAKE-SR-X300,1.73,7.244``, 그 외 → ``ER,<cmd>,00``
  - ``--er23``: Navigator 연결 상태처럼 모든 명령에 ``ER,<cmd>,23``
  - ``--fragment``: 프레임을 3조각으로 나눠 10ms 간격 전송 (프레이밍 시험)
  - ``--drop-after N``: 접속 N초 후 연결을 끊음 (재접속 시험)

사용 예:
  python scripts/fake_keyence_server.py                      # 127.0.0.1:9004, 만석 fixture
  python scripts/fake_keyence_server.py --fragment --port 9104
"""
from __future__ import annotations

import argparse
import socket
import threading
import time
from pathlib import Path

DEFAULT_FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "qr_reader" / "20260909_132804_full.raw"

# 실기기(2026-09-09) 확인값 — 설정 조회(RB/RP) 응답 흉내
FAKE_PARAMS = {
    "RB,01100": "05922", "RB,01101": "22", "RB,01010": "1", "RB,01108": "1",
    "RP,101": "0", "RP,103": "4C4F4E", "RP,104": "4C4F4646", "RP,205": "4552524F52", "RP,290": "2",
}


def region_payload(n: int) -> str:
    """RD,nnn 응답 — 규약 배치(카세트 2행×3열, 카세트당 3열×4행)의 영역 좌표. 1~72 외는 미정의."""
    if not 1 <= n <= 72:
        return "0" * 16
    cas, i = (n - 1) // 12, (n - 1) % 12
    cell_w, cell_h, gap = 146, 129, 3
    cas_w, cas_h = 3 * (cell_w + gap) + 60, 4 * (cell_h + gap) + 40
    x0 = 351 + (cas % 3) * cas_w + (i % 3) * (cell_w + gap)
    y0 = 48 + (cas // 3) * cas_h + (i // 3) * (cell_h + gap)
    return f"{x0:04d}{y0:04d}{x0 + cell_w:04d}{y0 + cell_h:04d}"


def load_frame(path: Path) -> bytes:
    data = path.read_bytes()
    return data if data.endswith(b"\r") else data + b"\r"


def send_frame(conn: socket.socket, frame: bytes, fragment: bool) -> None:
    if not fragment:
        conn.sendall(frame)
        return
    third = len(frame) // 3
    for part in (frame[:third], frame[third:third * 2], frame[third * 2:]):
        conn.sendall(part)
        time.sleep(0.01)


def handle_client(conn: socket.socket, addr, args, frame: bytes) -> None:
    print(f"[fake-keyence] client {addr} connected", flush=True)
    buf = b""
    armed = False
    start = time.monotonic()
    conn.settimeout(0.2)
    with conn:
        while True:
            if args.drop_after > 0 and time.monotonic() - start >= args.drop_after:
                print("[fake-keyence] drop-after reached, closing", flush=True)
                return
            try:
                chunk = conn.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                print(f"[fake-keyence] client {addr} closed", flush=True)
                return
            buf += chunk
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                cmd = line.strip(b"\n").decode("ascii", errors="replace")
                if cmd == "":
                    continue
                if args.er23:
                    conn.sendall(f"ER,{cmd},23\r".encode())
                    print(f"[fake-keyence] {cmd} -> ER,{cmd},23", flush=True)
                    continue
                if cmd == "LON":
                    armed = True
                    if args.immediate:
                        armed = False
                        send_frame(conn, frame, args.fragment)
                        print("[fake-keyence] LON -> frame (immediate)", flush=True)
                    else:
                        print("[fake-keyence] LON (armed, waiting for LOFF)", flush=True)
                elif cmd == "LOFF":
                    if armed:
                        armed = False
                        send_frame(conn, frame, args.fragment)
                        print("[fake-keyence] LOFF -> frame", flush=True)
                    else:
                        print("[fake-keyence] LOFF (not armed, no output)", flush=True)
                elif cmd == "KEYENCE":
                    conn.sendall(b"OK,KEYENCE,FAKE-SR-X300,1.73,7.244\r")
                elif cmd == "RLOCK":
                    conn.sendall(b"OK,RLOCK,UNLOCK\r")
                elif cmd.startswith("RD,"):
                    conn.sendall(f"OK,RD,{region_payload(int(cmd[3:] or 0))}\r".encode())
                elif cmd in FAKE_PARAMS:
                    conn.sendall(f"OK,{cmd.split(',')[0]},{FAKE_PARAMS[cmd]}\r".encode())
                elif cmd.startswith(("RB,", "RP,")):
                    conn.sendall(f"ER,{cmd.split(',')[0]},02\r".encode())
                else:
                    conn.sendall(f"ER,{cmd},00\r".encode())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9004)
    ap.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="재생할 .raw 프레임")
    ap.add_argument("--fragment", action="store_true", help="프레임을 3조각으로 나눠 전송")
    ap.add_argument("--immediate", action="store_true", help="LON 즉시 출력 (LOFF 대기 없음)")
    ap.add_argument("--er23", action="store_true", help="모든 명령에 ER,<cmd>,23 응답")
    ap.add_argument("--drop-after", type=float, default=0, help="접속 N초 후 연결 끊기")
    args = ap.parse_args(argv)

    frame = load_frame(args.fixture)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(5)
    print(f"[fake-keyence] listening on {args.host}:{args.port} fixture={args.fixture.name} ({len(frame)} bytes)", flush=True)
    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr, args, frame), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[fake-keyence] shutting down", flush=True)
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
