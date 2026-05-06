"""
HITL CLI — revisar interacciones del log y registrar feedback humano.

Uso:
  python review_tool.py                 # lista pendientes
  python review_tool.py --id <uuid>     # muestra detalle y pregunta feedback
  python review_tool.py --all           # itera todas las pendientes
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
LOG_PATH = ROOT / "interaction_log.jsonl"


def read_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    out = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def append_log(record: dict) -> None:
    record.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def pending_chats(records: list[dict]) -> list[dict]:
    feedbacks = {r["interaction_id"] for r in records if r.get("type") == "feedback"}
    return [
        r for r in records
        if r.get("type") == "chat" and r.get("interaction_id") not in feedbacks
    ]


def review_one(chat: dict) -> None:
    print("=" * 80)
    print(f"interaction_id : {chat['interaction_id']}")
    print(f"ts             : {chat.get('ts')}")
    print(f"intencion      : {chat.get('intencion')}")
    print(f"iteraciones    : {chat.get('iterations')}  elapsed_ms={chat.get('elapsed_ms')}")
    print(f"\nUSUARIO:\n  {chat.get('user_message')}")
    print(f"\nTOOLS USADAS:")
    for t in chat.get("tools_used", []):
        print(f"  - {t['name']}({json.dumps(t['input'], ensure_ascii=False)})")
    print(f"\nRESPUESTA:\n  {chat.get('response')}")
    print("-" * 80)
    ans = input("Util? [y/n/skip] ").strip().lower()
    if ans in ("s", "skip", ""):
        print("(saltado)")
        return
    helpful = ans.startswith("y")
    comment = input("Comentario (opcional): ").strip() or None
    append_log({
        "type": "feedback",
        "interaction_id": chat["interaction_id"],
        "helpful": helpful,
        "comment": comment,
        "source": "review_tool",
    })
    print("Feedback guardado.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="interaction_id especifico")
    parser.add_argument("--all", action="store_true", help="iterar todas las pendientes")
    args = parser.parse_args()

    records = read_log()
    if args.id:
        chat = next(
            (r for r in records if r.get("type") == "chat" and r["interaction_id"] == args.id),
            None,
        )
        if not chat:
            print(f"no encontrado: {args.id}")
            return
        review_one(chat)
        return

    pending = pending_chats(records)
    print(f"{len(pending)} interaccion(es) pendientes de feedback")
    if not pending:
        return
    if not args.all:
        for c in pending[:20]:
            print(
                f"  {c['interaction_id']}  {c.get('ts','')[:19]}  "
                f"[{c.get('intencion','-')}]  {(c.get('user_message') or '')[:60]}"
            )
        print("\nUsar --id <uuid> o --all para revisar.")
        return
    for c in pending:
        review_one(c)


if __name__ == "__main__":
    main()
