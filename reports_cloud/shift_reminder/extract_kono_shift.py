#!/usr/bin/env python3
import argparse
import random
import re
import sys
from pathlib import Path


DATE_RE = re.compile(r"【\d+月\d+日（[^）]+）】")
RESPONSIBILITY_RE = re.compile(r"＜責任者＞(?P<body>.*?)(?=\n\s*\n|$)", re.S)
SHIFT_LINE_RE = re.compile(r"^(?P<name>[^：\n]+)：(?P<time>\d{4}~\d{4})\s*$")
REST_RE = re.compile(r"休み：.*")

MORNING_TIME = "0930~1730"
NIGHT_TIME = "1500~2300"
MORNING_POST_TIMES = ["09:29", "09:30", "09:31", "09:32"]
NIGHT_POST_TIMES = ["14:58", "14:59", "15:00", "15:01", "15:02"]


def normalize_text(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").replace('"', "")


def split_days(text):
    starts = [match.start() for match in DATE_RE.finditer(text)]
    days = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        days.append(text[start:end].strip(" \n――"))
    return days


def find_responsibility(day_text, target):
    match = RESPONSIBILITY_RE.search(day_text)
    if not match:
        return None

    body = match.group("body")
    for kind in ("朝", "夜"):
        if re.search(rf"{kind}\s*：\s*{re.escape(target)}(?:\s|$)", body):
            return kind
    return None


def extract_shift_lines(day_text, responsibility_kind):
    target_time = MORNING_TIME if responsibility_kind == "朝" else NIGHT_TIME
    lines = []
    for raw_line in day_text.splitlines():
        line = raw_line.strip()
        match = SHIFT_LINE_RE.match(line)
        if not match:
            continue
        if match.group("time") == target_time:
            lines.append(line)
    return lines


def extract_rest_line(day_text):
    matches = REST_RE.findall(day_text)
    return matches[-1].strip() if matches else ""


def post_time_for(kind, rng):
    if kind == "朝":
        return rng.choice(MORNING_POST_TIMES)
    return rng.choice(NIGHT_POST_TIMES)


def build_entry(day_text, target, rng):
    date_match = DATE_RE.search(day_text)
    if not date_match:
        return None

    responsibility_kind = find_responsibility(day_text, target)
    if not responsibility_kind:
        return None

    shift_lines = extract_shift_lines(day_text, responsibility_kind)
    rest_line = extract_rest_line(day_text)
    post_time = post_time_for(responsibility_kind, rng)

    message_parts = [
        date_match.group(0),
        "",
        "＜責任者＞",
        f" {responsibility_kind}：{target}",
        "",
    ]
    message_parts.extend(shift_lines)
    if rest_line:
        message_parts.extend(["", rest_line])

    return {
        "date": date_match.group(0),
        "kind": responsibility_kind,
        "post_time": post_time,
        "message": "\n".join(message_parts).strip(),
    }


def extract_entries(text, target, seed=None):
    rng = random.Random(seed)
    normalized = normalize_text(text)
    entries = []
    for day_text in split_days(normalized):
        entry = build_entry(day_text, target, rng)
        if entry:
            entries.append(entry)
    return entries


def render_entries(entries):
    if not entries:
        return "対象シフトは見つかりませんでした。"

    chunks = []
    for entry in entries:
        chunks.append(
            "\n".join(
                [
                    f"予約目安：{entry['date']} {entry['kind']}勤務 → {entry['post_time']}",
                    "",
                    entry["message"],
                ]
            )
        )
    return "\n\n――\n\n".join(chunks)


def main():
    parser = argparse.ArgumentParser(description="Extract target responsibility shifts for manual Slack scheduling.")
    parser.add_argument("--target", default="河野", help="責任者として抽出する名前")
    parser.add_argument("--input", help="シフト本文ファイル。省略時は標準入力から読む")
    parser.add_argument("--seed", type=int, help="ランダム時刻を固定したい場合のseed")
    args = parser.parse_args()

    if args.input:
        text = Path(args.input).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    entries = extract_entries(text, args.target, args.seed)
    print(render_entries(entries))


if __name__ == "__main__":
    main()
