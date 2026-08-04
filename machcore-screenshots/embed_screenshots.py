# -*- coding: utf-8 -*-
"""
embed_screenshots.py
---------------------------------------------------------------
撮影済みのスクリーンショット(screenshots/ フォルダ内、マニュアル記載のファイル名と
一致するpng)を、マニュアルHTML内の「スクリーンショット挿入エリア」に自動で
<img>タグとして埋め込む。

使い方:
    python3 embed_screenshots.py \
        --html "MachCore_業務オペレーションマニュアル_v2.html" \
        --shots "./screenshots"

- screenshotsフォルダの中身は capture-screenshots.mjs の出力（マニュアル記載どおりの
  ファイル名の .png）をそのまま指定してください。
- 存在しないファイルはプレースホルダのまま残ります（何度実行しても安全＝差分埋め込み）。
- 埋め込み後のHTMLは同じファイルを上書きします（事前にコピーを推奨）。
"""
import argparse
import base64
import re
import sys
from pathlib import Path


def embed(html_path: Path, shots_dir: Path, inline: bool = True):
    html = html_path.read_text(encoding="utf-8")

    pattern = re.compile(
        r'(<span class="shot-filename">)(.*?)(</span>.*?)'
        r'(<div class="shot-placeholder">)(.*?)(</div>)',
        re.S,
    )

    found, embedded, missing = 0, 0, []

    def repl(m):
        nonlocal embedded, found
        found += 1
        filename = m.group(2).strip()
        img_file = shots_dir / filename
        if not img_file.exists():
            missing.append(filename)
            return m.group(0)  # 未撮影はそのまま

        if inline:
            data = base64.b64encode(img_file.read_bytes()).decode("ascii")
            src = f"data:image/png;base64,{data}"
        else:
            # 相対パス埋め込み（HTMLファイルと同階層に screenshots/ を置く運用）
            src = f"screenshots/{filename}"

        img_tag = (
            f'<img src="{src}" alt="{filename}" '
            f'style="width:100%;display:block;border-radius:6px;margin-bottom:8px;'
            f'border:1px solid #e2e8f0;">'
        )
        embedded += 1
        return m.group(1) + m.group(2) + m.group(3) + f'<div class="shot-placeholder shot-filled">{img_tag}</div>'

    new_html = pattern.sub(repl, html)
    html_path.write_text(new_html, encoding="utf-8")

    print(f"対象プレースホルダ: {found}件")
    print(f"埋め込み成功: {embedded}件")
    if missing:
        print(f"未撮影（プレースホルダのまま）: {len(missing)}件")
        for f in missing:
            print("  -", f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True, help="対象のマニュアルHTMLファイルパス")
    ap.add_argument("--shots", required=True, help="撮影済みpngが入っているフォルダ")
    ap.add_argument("--no-inline", action="store_true",
                     help="base64埋め込みではなく相対パス参照(<img src='screenshots/xxx.png'>)にする")
    args = ap.parse_args()

    embed(Path(args.html), Path(args.shots), inline=not args.no_inline)
