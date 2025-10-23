import streamlit as st
from modules.pipeline import prepare_from_url, search_in_transcript, hhmmss
from pathlib import Path
import json

st.set_page_config(page_title="YouTube Transcribe & Search", layout="wide")
st.title("YouTube 文字起こし & キーワード検索（Codex 初期コード）")

# --- 1. ユーザーは URL を指定 ---
url = st.text_input("YouTube の動画URLを入力", placeholder="https://www.youtube.com/watch?v=XXXXXXXXXXX")
lang = st.selectbox("言語ヒント", ["ja", "en", "auto"], index=0)
model = st.selectbox("Whisper モデル", ["tiny", "base", "small", "medium"], index=2)
use_auto_subs = st.checkbox("字幕があれば優先使用（高速）", value=True)

if "prep_done" not in st.session_state:
    st.session_state.prep_done = False
if "transcript" not in st.session_state:
    st.session_state.transcript = None
if "video_id" not in st.session_state:
    st.session_state.video_id = None

col1, col2 = st.columns([1,2])
with col1:
    # --- 2 & 3: ダウンロード & 文字起こし 実行 ---
    if st.button("準備開始（DL & 文字起こし）", disabled=not url):
        with st.spinner("準備中...（字幕取得 or 音声DL → 文字起こし）"):
            prep = prepare_from_url(url=url, lang=None if lang=="auto" else lang, model_size=model, prefer_subs=use_auto_subs)
        if prep.get("error"):
            st.error(prep["error"])
            st.session_state.prep_done = False
        else:
            st.session_state.transcript = prep["segments"]
            st.session_state.video_id = prep.get("video_id")
            st.session_state.prep_done = True

with col2:
    # --- 4. 準備完了ステータス表示 ---
    if st.session_state.prep_done:
        st.success("準備完了！下でキーワード検索できます。")
        st.caption(f"セグメント数: {len(st.session_state.transcript)}  | ソース: {prep.get('source','unknown')}")
    else:
        st.info("URL を入力して『準備開始』を押してください。")

st.markdown("---")

# --- 5. 検索キーワード入力 ---
kw = st.text_input("検索したい文字（カンマ区切りで複数指定可）", placeholder="サウナ, 整う")
case = st.checkbox("大文字小文字を区別する", value=False)

# --- 6. 検索実行 ---
if st.session_state.prep_done and st.button("検索実行", disabled=not kw.strip()):
    hits = search_in_transcript(st.session_state.transcript, kw, case_sensitive=case)
    if not hits:
        st.warning("ヒットなし")
    else:
        st.success(f"{len(hits)} 件ヒット")
        # --- 7. タイムスタンプ：検索文字付近の文章 表示 ---
        import pandas as pd
        def ytb_ts_link(video_id, sec):
            if not video_id:
                return ""
            return f"https://youtu.be/{video_id}?t={int(sec)}"
        rows = []
        for h in hits:
            rows.append({
                "timestamp_hhmmss": hhmmss(h["start"]),
                "timestamp_sec": round(h["start"], 2),
                "keyword": h["keyword"],
                "text": h["context"],
                "link": ytb_ts_link(st.session_state.video_id, h["start"]),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        # 保存
        outdir = Path("data")
        outdir.mkdir(exist_ok=True, parents=True)
        with open(outdir/"matches.json", "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        st.download_button("検索結果（matches.json）をダウンロード", data=json.dumps(rows, ensure_ascii=False, indent=2), file_name="matches.json", mime="application/json")
