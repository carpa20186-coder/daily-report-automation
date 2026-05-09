#!/usr/bin/env python3
import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path


SHEET_ID = "1MgQQnrAKTpFVMZMe4lQKKgD7NE0IXRE_eZhrqdmazEs"
SHEET_GID = "1166465300"
AD_ROW_RE = re.compile(r"(?:ai)?\d+【")


def clean(value):
    value = str(value).strip().replace("¥", "").replace(",", "").replace("%", "").replace("　", "")
    if value in ("", "#DIV/0!", "#REF!", "#N/A", "0", "-"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fy(value):
    return f"¥{int(value):,}" if value is not None else "-"


def fp(value):
    return f"{value:.1f}%" if value is not None else "-"


def fi(value):
    return f"{int(value)}" if value is not None else "-"


def rate(numerator, denominator):
    return f"{numerator / denominator * 100:.0f}%" if denominator else "-"


def fetch_sheet_rows():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
    with urllib.request.urlopen(url) as response:
        return list(csv.reader(io.TextIOWrapper(response, encoding="utf-8")))


def total(cell):
    if isinstance(cell, dict):
        return int(cell.get("total") or 0)
    return 0


def build_lmes_cache(crosslytics_path):
    data = json.loads(Path(crosslytics_path).read_text(encoding="utf-8"))
    rows = data.get("rows", [])

    reg_base = video_tap = seminar_reg = seminar_seat = be_contract = 0
    cr_data = []

    for row in rows:
        label = str(row.get("label", ""))
        cells = row.get("cells", [])
        if len(cells) < 7:
            continue
        n = total(cells[0])
        vtap = total(cells[1])
        sreg = total(cells[2])
        sseat = total(cells[3])
        contract = total(cells[6])

        reg_base += n
        video_tap += vtap
        seminar_reg += sreg
        seminar_seat += sseat
        be_contract += contract
        cr_data.append([label, n, vtap, sreg, sseat, contract, n < 10])

    return {
        "last_updated": datetime.now().strftime("%Y年%-m月%-d日"),
        "reg_base": reg_base,
        "video_tap": video_tap,
        "seminar_reg": seminar_reg,
        "seminar_seat": seminar_seat,
        "be_contract": be_contract,
        "cr_data": cr_data,
    }


def metric_summary(rows, target_cols):
    spend = clicks = imps = reg = purchase = rev = mosikomi = chakuseki = 0
    for row in rows[9:]:
        name = row[0].strip() if row else ""
        if not name or not AD_ROW_RE.match(name):
            continue
        for _, sc in target_cols:
            row_spend = clean(row[sc + 2]) if sc + 2 < len(row) else None
            if not row_spend:
                continue
            spend += row_spend
            clicks += clean(row[sc + 4]) or 0
            imps += clean(row[sc + 3]) or 0
            reg += clean(row[sc + 8]) or 0
            purchase += clean(row[sc + 11]) or 0
            rev += clean(row[sc + 0]) or 0
            mosikomi += clean(row[sc + 20]) or 0
            chakuseki += clean(row[sc + 23]) or 0

    ctr = clicks / imps * 100 if imps else None
    cvr = reg / clicks * 100 if clicks else None
    cpa = spend / reg if reg else None
    roas = rev / spend * 100 if spend and rev else None
    profit = rev - spend if rev else None
    mosikomi_cpo = spend / mosikomi if mosikomi else None
    chakuseki_cpo = spend / chakuseki if chakuseki else None
    return {
        "spend": spend,
        "clicks": clicks,
        "imps": imps,
        "reg": reg,
        "purchase": int(purchase),
        "rev": rev,
        "ctr": ctr,
        "cvr": cvr,
        "cpa": cpa,
        "roas": roas,
        "profit": profit,
        "mosikomi": mosikomi,
        "mosikomi_cpo": mosikomi_cpo,
        "chakuseki": chakuseki,
        "chakuseki_cpo": chakuseki_cpo,
    }


def month_delta(dt, delta):
    y = dt.year + (dt.month - 1 + delta) // 12
    m = (dt.month - 1 + delta) % 12 + 1
    return datetime(y, m, 1)


def build_comment(current, previous, cumulative, lmes):
    lines = []
    cpa = current["cpa"]
    reg_base = lmes["reg_base"]
    video_tap = lmes["video_tap"]
    seminar_reg = lmes["seminar_reg"]
    seminar_seat = lmes["seminar_seat"]
    purchase_n = current["purchase"]

    if cpa:
        if reg_base and reg_base < 10:
            lines.append("まだサンプルが少ないため、CPAは参考値として見たいです。まずは登録後のファネル反応を丁寧に確認していきましょう。")
        elif cpa < 3000:
            lines.append(f"登録CPAは{fy(cpa)}で、獲得効率は良好です。広告から登録を作る流れは十分に見えています。")
        else:
            lines.append(f"登録CPAは{fy(cpa)}です。今後はクリエイティブ別の反応とLINE内の歩留まりを合わせて見たいです。")

    if previous["spend"]:
        lines.append(
            f"前月は消化{fy(previous['spend'])}、登録{fi(previous['reg'])}人、CPA{fy(previous['cpa'])}、"
            f"購入{previous['purchase']}件でした。今月は立ち上がりの数字を見ながら、無理に大きく判断しすぎないのがよさそうです。"
        )

    if cumulative["spend"]:
        lines.append(
            f"直近12ヶ月累計では消化{fy(cumulative['spend'])}、登録{fi(cumulative['reg'])}人、"
            f"平均CPA{fy(cumulative['cpa'])}、購入{cumulative['purchase']}件です。累計では登録獲得の土台があります。"
        )

    if reg_base:
        video_rate = video_tap / reg_base * 100 if reg_base else None
        seminar_rate = seminar_reg / reg_base * 100 if reg_base else None
        seat_rate = seminar_seat / reg_base * 100 if reg_base else None
        lines.append(
            f"LINEシナリオでは、動画タップ率{fp(video_rate)}、セミナー申込率{fp(seminar_rate)}、着席率{fp(seat_rate)}です。"
            "どこで落ちているかを見ながら、次の改善点を絞れます。"
        )

    if current["rev"]:
        lines.append(f"今月売上は{fy(current['rev'])}、ROASは{fp(current['roas'])}です。売上が立っているため、広告効率と着席後の成約導線をセットで見たいです。")
    elif purchase_n:
        lines.append(f"購入は{purchase_n}件確認できています。売上反映のタイミングも見ながら追っていきましょう。")
    else:
        lines.append("現時点では売上はまだ大きく積み上がっていません。まずはセミナー申込と着席の母数を増やす観察フェーズです。")

    return "\n\n".join(lines)


def section(title, body):
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*▼ {title}*\n{body}"}},
        {"type": "divider"},
    ]


def build_blocks(sheet_rows, lmes):
    now = datetime.now()
    this_month = f"{now.year}年{now.month}月"
    prev_month_dt = month_delta(now, -1)
    prev_month = f"{prev_month_dt.year}年{prev_month_dt.month}月"

    month_row = sheet_rows[3]
    months = [(v, i) for i, v in enumerate(month_row) if "年" in v and "月" in v]
    this_cols = [(m, c) for m, c in months if this_month in m]
    prev_cols = [(m, c) for m, c in months if prev_month in m]
    cumulative_cols = []
    for m, c in months:
        mo = re.search(r"(\d{4})年(\d+)月", m)
        if not mo:
            continue
        month_dt = datetime(int(mo.group(1)), int(mo.group(2)), 1)
        diff = (now.year - month_dt.year) * 12 + (now.month - month_dt.month)
        if 0 <= diff <= 11:
            cumulative_cols.append((m, c))

    current = metric_summary(sheet_rows, this_cols)
    previous = metric_summary(sheet_rows, prev_cols)
    cumulative = metric_summary(sheet_rows, cumulative_cols)

    def summary_text(summary, cumulative_label=False):
        return "\n".join([
            f"消化：{fy(summary['spend'])}",
            f"CTR：{fp(summary['ctr'])}",
            f"CVR：{fp(summary['cvr'])}",
            f"{'平均CPA' if cumulative_label else 'CPA'}：{fy(summary['cpa'])}",
            f"申込CPO：{fy(summary['mosikomi_cpo'])}",
            f"着席CPO：{fy(summary['chakuseki_cpo'])}",
            f"登録：{fi(summary['reg'])}",
            f"購入：{summary['purchase']}",
            f"売上：{fy(summary['rev'])}",
            f"ROAS：{fp(summary['roas'])}",
        ])

    cr_lines = []
    for cr, n, vtap, sreg, sseat, contract, small in lmes["cr_data"]:
        if n == 0:
            continue
        note = " ※参考値" if small else ""
        cr_lines.append(
            f"{cr} n={n}{note}\n"
            f"動画タップ:{rate(vtap, n)} セミナー申込:{rate(sreg, n)} 着席:{rate(sseat, n)} 成約:{rate(contract, n)}"
        )

    line_text = "\n".join([
        f"登録：{lmes['reg_base']}人",
        "↓",
        f"動画タップ：{lmes['video_tap']}人（{rate(lmes['video_tap'], lmes['reg_base'])}）",
        "↓",
        f"セミナー申込：{lmes['seminar_reg']}人（{rate(lmes['seminar_reg'], lmes['reg_base'])}）",
        "↓",
        f"セミナー着席：{lmes['seminar_seat']}人（{rate(lmes['seminar_seat'], lmes['reg_base'])}）",
        "↓",
        f"購入：{current['purchase']}人（{rate(current['purchase'], lmes['reg_base'])}）",
    ])

    comment = build_comment(current, previous, cumulative, lmes)
    action_plan = "\n".join([
        "1. CPAとCVRは引き続き日次で確認し、急な悪化があればCR別に確認する。",
        "2. LINEシナリオは動画タップからセミナー申込までの落ち方を中心に見る。",
        "3. 売上が出るまでは、母数不足による過判断を避けて着席数の積み上がりを追う。",
    ])

    today = now.strftime("%Y年%-m月%-d日")
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*コンテンツビジネス 日次レポート｜{today}*"}},
        {"type": "divider"},
        *section("今月サマリー", summary_text(current)),
        *section("累計サマリー", summary_text(cumulative, cumulative_label=True)),
        *section("CR別ファネル通過率", "\n\n".join(cr_lines) or "対象データなし"),
        *section("LINEシナリオ", line_text),
        *section("数値まとめ・コメント", comment),
        *section("参考アクションプラン", action_plan),
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*本日（{today}）のレポート報告になります。ご確認ください！*\n\nまた、この数値レポートは、AIによる自動出力です。\n\nあくまで補助的な参考情報としてご活用いただき、最終的な判断にあたっては、必ず人の目で内容を確認・解釈・推敲したうえで進めるようにしてくださいね。"}},
    ]


def post_to_slack(webhook_url, blocks):
    payload = json.dumps({"blocks": blocks}).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return response.read().decode()


def blocks_to_text(blocks):
    lines = []
    for block in blocks:
        if block.get("type") == "divider":
            lines.append("----")
            continue
        text = block.get("text", {}).get("text")
        if text:
            lines.append(text)
    return "\n\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build and optionally send the Contents Business daily report.")
    parser.add_argument("--crosslytics-json", required=True, help="LMES crosslytics JSON from fetch_lmes_crosslytics.mjs")
    parser.add_argument("--mode", choices=["test", "prod"], default="test")
    parser.add_argument("--send", action="store_true", help="Send to Slack. Without this, prints a preview only.")
    parser.add_argument("--out-blocks", help="Optional path to write Slack blocks JSON.")
    args = parser.parse_args()

    sheet_rows = fetch_sheet_rows()
    lmes = build_lmes_cache(args.crosslytics_json)
    blocks = build_blocks(sheet_rows, lmes)

    if args.out_blocks:
        out = Path(args.out_blocks)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(blocks_to_text(blocks))

    if args.send:
        env_name = "CONTENTS_PROD_SLACK_WEBHOOK" if args.mode == "prod" else "CONTENTS_TEST_SLACK_WEBHOOK"
        webhook = os.environ.get(env_name)
        if not webhook:
            raise SystemExit(f"Set {env_name} to send this report.")
        result = post_to_slack(webhook, blocks)
        print(f"Slack response: {result}", file=sys.stderr)


if __name__ == "__main__":
    main()
