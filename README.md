# YouTube ダウンロード → 文字起こし → キーワード検索（UI付）

VS Code でも Codex でもそのまま動かせる **Streamlit** アプリです。  
要件（1～7）に対応：

1. 画面から YouTube URL 入力
2. 動画（音声のみ）をダウンロード（yt-dlp）
3. 文字起こし（字幕優先。無ければ Whisper）
4. 準備完了ステータス表示
5. キーワード入力
6. 文字起こし内から検索
7. 「タイムスタンプ：周辺文章」を一覧表示（YouTube への秒ジャンプリンク付き）

## セットアップ

```bash
# Python 3.9+ 推奨
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

> 初回の Whisper モデル取得や CTranslate2 のダウンロードで少し時間がかかる場合があります。

## 起動
```bash
streamlit run app.py
```
ブラウザが自動で開きます（開かない場合は表示された URL をコピー）。

## メモ
- Whisper は **faster-whisper** を優先、失敗時は **openai-whisper** へフォールバック。
- 字幕がある動画はダウンロードせずに字幕（VTT）を優先利用（高速）。
- 出力は `data/` 配下に保存されます（音声、字幕、transcript.json、matches.json など）。

作成日: 2025-10-23
