#!/usr/bin/env python3
"""Публикатор Telegram-канала Operation Zero.

Читает посты из tgbot/queue/*.json, публикует те, чьё время наступило,
и записывает отправленные в tgbot/sent.json. Токен бота берётся только из
переменной окружения TG_BOT_TOKEN (GitHub Secret) и никогда не печатается.

Формат поста (JSON):
{
  "id": "zombie3-anons",                 # уникальный, по нему не публикуем дважды
  "at": "2026-11-03 19:00",               # время по Екатеринбургу (UTC+5); нет поля = сразу
  "type": "text" | "photo" | "poll",
  "text": "HTML-текст поста",             # для photo — подпись
  "photo": "tgbot/img/x.jpg" или "https://...",
  "buttons": [["Смотреть", "https://youtube.com/shorts/..."], ["Играть", "https://t.me/..."]],
  "question": "...", "options": ["А — ...", "Б — ..."],   # для poll
  "pin": false, "silent": false
}
"""
import datetime as dt
import glob
import json
import mimetypes
import os
import sys
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.abspath(__file__))
TZ = dt.timezone(dt.timedelta(hours=5))  # Екатеринбург
TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL = os.environ.get("TG_CHANNEL", "")
DRY = os.environ.get("DRY_RUN") == "1"


def api(method, data=None, files=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in (data or {}).items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        for k, path in files.items():
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as fh:
                content = fh.read()
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{os.path.basename(path)}\"\r\n"
                     f"Content-Type: {mime}\r\n\r\n").encode() + content + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, urllib.parse.urlencode(data or {}).encode())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        res = json.load(e)
    if not res.get("ok"):
        raise RuntimeError(f"{method}: {res.get('description', 'ошибка Telegram API')}")
    return res["result"]


def due(post, now):
    if not post.get("at"):
        return True
    at = dt.datetime.strptime(post["at"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    return at <= now


def markup(post):
    rows = [[{"text": t, "url": u}] for t, u in post.get("buttons", [])]
    return json.dumps({"inline_keyboard": rows}, ensure_ascii=False) if rows else None


def publish(post):
    base = {"chat_id": CHANNEL, "disable_notification": str(bool(post.get("silent"))).lower()}
    kb = markup(post)
    if kb:
        base["reply_markup"] = kb
    kind = post.get("type", "text")
    if kind == "poll":
        msg = api("sendPoll", {**base, "question": post["question"], "options": json.dumps(post["options"], ensure_ascii=False),
                               "is_anonymous": "true"})
    elif kind == "photo":
        data = {**base, "caption": post.get("text", ""), "parse_mode": "HTML"}
        ph = post["photo"]
        if ph.startswith("http"):
            msg = api("sendPhoto", {**data, "photo": ph})
        else:
            msg = api("sendPhoto", data, files={"photo": os.path.join(os.path.dirname(ROOT), ph)})
    else:
        msg = api("sendMessage", {**base, "text": post["text"], "parse_mode": "HTML", "link_preview_options": json.dumps({"is_disabled": not post.get("preview", True)})})
    if post.get("pin"):
        api("pinChatMessage", {"chat_id": CHANNEL, "message_id": msg["message_id"], "disable_notification": "true"})
    return msg["message_id"]


def main():
    if not TOKEN or not CHANNEL:
        print("Нет TG_BOT_TOKEN или TG_CHANNEL — добавьте секрет и переменную в настройках репозитория.")
        return 1
    now = dt.datetime.now(TZ)
    sent_path = os.path.join(ROOT, "sent.json")
    sent = json.load(open(sent_path, encoding="utf-8")) if os.path.exists(sent_path) else {}
    changed = False
    for f in sorted(glob.glob(os.path.join(ROOT, "queue", "*.json"))):
        post = json.load(open(f, encoding="utf-8"))
        pid = post["id"]
        if pid in sent or not due(post, now):
            continue
        if DRY:
            print(f"[dry] опубликовал бы {pid}")
            continue
        try:
            mid = publish(post)
            sent[pid] = {"message_id": mid, "at": now.strftime("%Y-%m-%d %H:%M")}
            changed = True
            print(f"опубликовано: {pid} (message {mid})")
        except Exception as e:  # не роняем остальные посты
            print(f"ошибка в {pid}: {e}")
    # статистика канала
    try:
        n = api("getChatMemberCount", {"chat_id": CHANNEL})
        stats_path = os.path.join(ROOT, "stats.json")
        stats = json.load(open(stats_path, encoding="utf-8")) if os.path.exists(stats_path) else {}
        day = now.strftime("%Y-%m-%d")
        if stats.get(day) != n:
            stats[day] = n
            json.dump(stats, open(stats_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            changed = True
        print(f"подписчиков: {n}")
    except Exception as e:
        print(f"статистика недоступна: {e}")
    if changed:
        json.dump(sent, open(sent_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
