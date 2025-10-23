from pathlib import Path
import re, json, tempfile, subprocess, sys
from typing import Optional

def hhmmss(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    t = int(seconds)
    h = t // 3600
    m = (t % 3600) // 60
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def ensure_module(mod, pip_name=None):
    try:
        __import__(mod)
    except ImportError:
        name = pip_name or mod
        subprocess.check_call([sys.executable, "-m", "pip", "install", name])

def run_cmd(cmd):
    print("[cmd]", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)

VTT_BLOCK = re.compile(r"(\\d{2}:\\d{2}:\\d{2}\\.\\d{3})\\s+-->\\s+(\\d{2}:\\d{2}:\\d{2}\\.\\d{3})\\s*(?:.*)?\\n([\\s\\S]*?)(?=\\n\\n|\\Z)", re.MULTILINE)

def parse_vtt(vtt_path: Path):
    txt = vtt_path.read_text("utf-8", errors="ignore")
    segs = []
    for m in VTT_BLOCK.finditer(txt):
        start, end, text = m.group(1), m.group(2), m.group(3)
        text = re.sub(r"<[^>]+>", "", text).replace("\\r","").strip().replace("\\n"," ")
        if not text: 
            continue
        def to_sec(ts):
            h, mi, s = ts.split(":")
            return int(h)*3600 + int(mi)*60 + float(s)
        segs.append({"start": to_sec(start), "end": to_sec(end), "text": text})
    return segs

def try_download_subtitles(url: str, outdir: Path, lang: Optional[str]):
    ensure_module("yt_dlp","yt-dlp")
    outtpl = str(outdir / "%(id)s.%(ext)s")
    for subs_flag in [["--write-subs"], ["--write-auto-subs"]]:
        cmd = [sys.executable,"-m","yt_dlp","--skip-download","--sub-langs", (lang or "all"),
               "--sub-format","vtt","-o",outtpl,*subs_flag,url]
        try:
            run_cmd(cmd)
            vtts = list(outdir.glob("*.vtt"))
            if vtts:
                return vtts[0]
        except subprocess.CalledProcessError:
            pass
    return None

def download_audio(url: str, outdir: Path):
    ensure_module("yt_dlp","yt-dlp")
    outtpl = str(outdir / "%(title)s-%(id)s.%(ext)s")
    cmd = [sys.executable,"-m","yt_dlp","-x","--audio-format","m4a","-o",outtpl,url]
    run_cmd(cmd)
    cand = sorted(outdir.glob("*.m4a"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cand:
        raise RuntimeError("音声DLに失敗")
    return cand[0]

def transcribe_with_whisper(audio_path: Path, lang: Optional[str], model_size="small"):
    # faster-whisper 優先
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio_path), language=lang or None)
        return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
    except Exception as e:
        print("[warn] faster-whisper failed:", e)
        ensure_module("whisper","openai-whisper")
        import whisper
        model = whisper.load_model(model_size)
        result = model.transcribe(str(audio_path), language=lang or None)
        return [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in result["segments"]]

def extract_video_id(url: str) -> Optional[str]:
    m = re.search(r"v=([\\w-]{6,})", url)
    if m: return m.group(1)
    m = re.search(r"youtu\\.be/([\\w-]{6,})", url)
    if m: return m.group(1)
    return None

def prepare_from_url(url: str, lang: Optional[str] = "ja", model_size="small", prefer_subs=True):
    out = Path("data"); out.mkdir(parents=True, exist_ok=True)
    video_id = extract_video_id(url)
    # 字幕があれば使う
    segments = None
    source = None
    if prefer_subs:
        try:
            with tempfile.TemporaryDirectory() as td:
                vtt = try_download_subtitles(url, Path(td), lang)
                if vtt:
                    segments = parse_vtt(Path(vtt))
                    source = "captions"
        except Exception as e:
            print("[warn] 字幕取得失敗:", e)
    # ない場合は音声DL→ASR
    if not segments:
        audio = download_audio(url, out)
        segments = transcribe_with_whisper(audio, lang, model_size=model_size)
        source = "asr"
    # 保存
    (out/"transcript.json").write_text(json.dumps({"source":source,"segments":segments}, ensure_ascii=False, indent=2), "utf-8")
    return {"segments": segments, "source": source, "video_id": video_id}

def search_in_transcript(segments, keywords_csv: str, case_sensitive=False, context_window=40):
    if not segments: return []
    keywords = [k.strip() for k in keywords_csv.split(",") if k.strip()]
    if not keywords: return []
    def norm(s): return s if case_sensitive else s.lower()
    kws = [norm(k) for k in keywords]
    hits = []
    for seg in segments:
        t = seg["text"]
        tn = norm(t)
        for kw_orig, kw in zip(keywords, kws):
            pos = tn.find(kw)
            if pos != -1:
                # 周辺文脈
                start = max(0, pos - context_window)
                end = min(len(t), pos + len(kw) + context_window)
                ctx = t[start:end]
                hits.append({
                    "start": float(seg["start"]),
                    "end": float(seg["end"]),
                    "keyword": kw_orig,
                    "context": ctx,
                    "text": t,
                })
    # 重複除去 & 並び替え
    uniq = {}
    for h in hits:
        key = (round(h["start"],2), h["keyword"])
        if key not in uniq:
            uniq[key] = h
    return sorted(uniq.values(), key=lambda x: x["start"])
