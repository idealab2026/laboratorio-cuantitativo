"""Process one Buy The Dip episode into structured strategy evidence.

Audio and transcript text are temporary. Git stores only derived paraphrases and
provenance. YouTube remains the canonical source identity; the official podcast
feed is only a transport fallback for matched long-form episodes.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, re, signal, subprocess, sys, tempfile, urllib.request, urllib.error
from pathlib import Path

PRIORITY={"methodology":0,"portfolio_update":1,"sector_theme":2,"company_or_theme":3,
          "macro_market":4,"guest_interview":5,"short":6}
LLM_REPO="Qwen/Qwen3-4B-GGUF"
LLM_FILE="Qwen3-4B-Q4_K_M.gguf"
ASR_MODEL="small"
# A native SIGILL terminates Python before exceptions can be caught. Keep
# ffmpeg/ASR and llama.cpp in separate processes, using only /tmp for verbatim.
NATIVE_STAGES = ("asr", "analysis")


def stage_trace(stage):
    """No transcript, title, audio URL, prompt, or full model path in logs."""
    if stage not in {
        "audio_download_start", "audio_download_complete",
        "asr_before_model", "asr_model_ready", "asr_before_decode", "asr_decode_complete",
        "llm_before_hf_download", "llm_download_complete",
        "llm_before_native_import", "llm_native_import_complete",
        "llm_before_model_init", "llm_model_ready", "analysis_before_inference",
        "analysis_complete", "asr_child_finished", "analysis_child_finished",
        "asr_sigill", "analysis_sigill", "asr_native_failed", "analysis_native_failed",
    }:
        raise ValueError("Unknown native lifecycle stage")
    print("BTD_NATIVE_STAGE=" + stage, file=sys.stderr, flush=True)


def native_subprocess(stage, payload, directory, *, python=None, timeout=9000):
    """Return native-derived data ONLY after a child exits successfully.

    An OS-level illegal instruction does not kill the parent, truncate an
    in-repository ledger, or falsely mark the episode reviewed. No process
    output is captured; logs contain fixed, non-sensitive stage markers only.
    """
    if stage not in NATIVE_STAGES:
        raise ValueError("Unsupported native analysis stage")
    directory = Path(directory)
    source = directory / ("native_" + stage + "_input.json")
    target = directory / ("native_" + stage + "_output.json")
    if target.exists():
        raise ValueError("Refusing to reuse previous native stage output")
    atomic_json(source, payload)
    env = dict(os.environ, PYTHONFAULTHANDLER="1", PYTHONUNBUFFERED="1")
    cmd = [python or sys.executable, str(Path(__file__).resolve()),
           "--native-stage", stage, "--stage-input", str(source),
           "--stage-output", str(target)]
    completed = subprocess.run(cmd, check=False, env=env, timeout=timeout)
    if completed.returncode != 0:
        sigill = completed.returncode in (-signal.SIGILL, 128 + signal.SIGILL)
        stage_trace(stage + ("_sigill" if sigill else "_native_failed"))
        raise RuntimeError("native_" + stage + "_sigill" if sigill
                           else "native_" + stage + "_failed_code_" +
                                str(completed.returncode))
    if not target.is_file():
        raise ValueError("Native stage produced no verified output")
    result = read_json(target)
    if stage == "asr":
        if (not isinstance(result, dict) or
                not isinstance(result.get("transcript"), str) or
                not isinstance(result.get("asr"), dict) or
                len(result["transcript"].split()) < 100):
            raise ValueError("Malformed completed native ASR output")
    elif (not isinstance(result, dict) or
          not isinstance(result.get("analysis"), dict) or
          not isinstance(result.get("evidence"), list)):
        raise ValueError("Malformed completed native LLM output")
    stage_trace(stage + "_child_finished")
    return result


def native_stage_child(stage, input_path, output_path):
    """Native work only; parent owns review/progress publication."""
    if stage not in NATIVE_STAGES:
        raise ValueError("Unsupported native child stage")
    data = read_json(input_path)
    if stage == "asr":
        audio = Path(data["audio_path"])
        if not audio.is_file():
            raise ValueError("Native ASR audio not present in temporary directory")
        transcript, asr = transcribe(audio, data["model_name"])
        result = {"transcript": transcript, "asr": asr}
    else:
        transcript, meta = data["transcript"], data["metadata"]
        if not isinstance(transcript, str) or not isinstance(meta, dict):
            raise ValueError("Invalid temporary semantic input")
        llm = load_llm(os.environ.get("BTD_LLM_REPO", LLM_REPO),
                       os.environ.get("BTD_LLM_FILE", LLM_FILE))
        stage_trace("analysis_before_inference")
        analysis, evidence = analyze_episode(llm, transcript, meta)
        stage_trace("analysis_complete")
        result = {"analysis": analysis, "evidence": evidence}
    atomic_json(output_path, result)

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def atomic_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    os.replace(tmp,path)

def reviewed_ids(root):
    root=Path(root)
    return {p.stem for p in root.glob("*.json")} if root.exists() else set()

def rss_by_video(rss):
    out={}
    for row in rss.get("episodes") or []:
        vid=row.get("youtube_video_id")
        if vid and row.get("match_status")=="matched" and row.get("audio_url"):
            out.setdefault(vid,row)
    return out

def choose_next(queue,rss,reviewed,blocked=()):
    mirror=rss_by_video(rss); candidates=[]
    for row in queue.get("videos") or []:
        vid=row.get("video_id")
        if not vid or vid in reviewed or vid in blocked or vid not in mirror: continue
        candidates.append((PRIORITY.get(row.get("category"),99),
                           -float(row.get("methodology_relevance_score") or 0),
                           vid,row,mirror[vid]))
    if not candidates: return None
    *_,q,r=sorted(candidates,key=lambda x:x[:3])[0]
    return {"queue":q,"rss":r}

def unavailable_ids(path, now=None):
    """Only exclude unavailable transports during bounded retry cooldown."""
    path=Path(path)
    if not path.exists(): return set()
    state=read_json(path)
    if state.get("schema_version")!=1 or not isinstance(state.get("items"),dict):
        raise ValueError("Invalid unavailable-audio state")
    now=now or dt.datetime.now(dt.timezone.utc)
    result=set()
    for vid,entry in state["items"].items():
        if not isinstance(entry,dict): raise ValueError("Invalid unavailable entry")
        retry=dt.datetime.fromisoformat(entry["retry_after_utc"].replace("Z","+00:00"))
        if retry.utcoffset()!=dt.timedelta(0): raise ValueError("Invalid UTC cooldown")
        if retry>now: result.add(vid)
    return result

def record_missing_transport(path,vid,status,now=None):
    """Persist a 48-hour retry guard, never audio, urls, or fake transcription."""
    if status not in (404,410): raise ValueError("Only missing audio may be quarantined")
    now=now or dt.datetime.now(dt.timezone.utc)
    path=Path(path)
    state=read_json(path) if path.is_file() else {"schema_version":1,"items":{}}
    if state.get("schema_version")!=1 or not isinstance(state.get("items"),dict):
        raise ValueError("Invalid unavailable-audio state")
    later=(now+dt.timedelta(hours=48)).isoformat()
    state["items"][vid]={"http_status":status,"detected_at_utc":now.isoformat(),
                         "retry_after_utc":later}
    atomic_json(path,state)
    return later

def download(url,destination,max_bytes=300_000_000):
    req=urllib.request.Request(url,headers={"User-Agent":"MIDAS-BuyTheDip/1.0"})
    total=0
    with urllib.request.urlopen(req,timeout=90) as response, open(destination,"wb") as stream:
        length=response.headers.get("Content-Length")
        if length and int(length)>max_bytes: raise ValueError("audio_too_large")
        while True:
            chunk=response.read(1024*1024)
            if not chunk: break
            total+=len(chunk)
            if total>max_bytes: raise ValueError("audio_too_large")
            stream.write(chunk)
    if total<1024: raise ValueError("audio_download_empty")
    return total

def stamp(seconds):
    seconds=max(0,int(seconds or 0)); h,rem=divmod(seconds,3600); m,s=divmod(rem,60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def transcribe(audio_path,model_name=ASR_MODEL):
    stage_trace("asr_before_model")
    from faster_whisper import WhisperModel
    model=WhisperModel(model_name,device="cpu",compute_type="int8",cpu_threads=4)
    stage_trace("asr_model_ready")
    segments,info=model.transcribe(str(audio_path),language="es",beam_size=3,
                                   vad_filter=True,condition_on_previous_text=True)
    stage_trace("asr_before_decode")
    lines=[]; words=0
    for seg in segments:
        text=re.sub(r"\s+"," ",seg.text or "").strip()
        if not text: continue
        words+=len(text.split()); lines.append(f"[{stamp(seg.start)}] {text}")
    stage_trace("asr_decode_complete")
    if words<100: raise ValueError("transcription_too_short")
    return "\n".join(lines),{
        "language":getattr(info,"language","es"),
        "language_probability":float(getattr(info,"language_probability",0) or 0),
        "duration_seconds":float(getattr(info,"duration",0) or 0),
        "word_count":words,"segment_count":len(lines),"model":model_name}

def chunk_transcript(text,max_chars=11000):
    chunks=[]; current=[]; size=0
    for line in text.splitlines():
        extra=len(line)+1
        if current and size+extra>max_chars:
            chunks.append("\n".join(current)); current=[]; size=0
        current.append(line); size+=extra
    if current: chunks.append("\n".join(current))
    return chunks

def json_object(text):
    text=str(text or "").strip()
    try:
        value=json.loads(text)
        if isinstance(value,dict): return value
    except json.JSONDecodeError: pass
    start=text.find("{"); end=text.rfind("}")
    if start>=0 and end>start:
        value=json.loads(text[start:end+1])
        if isinstance(value,dict): return value
    raise ValueError("llm_invalid_json")

def load_llm(repo_id=LLM_REPO,filename=LLM_FILE):
    stage_trace("llm_before_hf_download")
    from huggingface_hub import hf_hub_download
    path=hf_hub_download(repo_id=repo_id,filename=filename)
    stage_trace("llm_download_complete")
    stage_trace("llm_before_native_import")
    from llama_cpp import Llama
    stage_trace("llm_native_import_complete")
    stage_trace("llm_before_model_init")
    model=Llama(model_path=path,n_ctx=16384,n_threads=4,n_batch=256,verbose=False)
    stage_trace("llm_model_ready")
    return model

def chat_json(llm,system,prompt,max_tokens):
    """Bounded retry for truncated/invalid LLM output; never fabricate evidence."""
    for attempt in range(2):
        brevity = ("\nMantén la salida breve (máximo 5 evidencias). "
                   "Conserva solo hechos sustentados. Cierra todo el JSON."
                   if attempt else "")
        response=llm.create_chat_completion(
            messages=[{"role":"system","content":system+brevity+"\n/no_think"},
                      {"role":"user","content":prompt+"\n/no_think"}],
            temperature=0.1 if attempt == 0 else 0,
            max_tokens=max_tokens,
            response_format={"type":"json_object"})
        try:
            return json_object(response["choices"][0]["message"]["content"])
        except (ValueError,json.JSONDecodeError):
            if attempt == 1:
                raise ValueError("llm_invalid_json_after_retry") from None

def sanitize(value):
    if isinstance(value,dict):
        return {k:sanitize(v) for k,v in value.items()
                if k.lower() not in {"transcript","transcription","verbatim","full_text","quote"}}
    if isinstance(value,list): return [sanitize(x) for x in value[:120]]
    if isinstance(value,str): return re.sub(r"\s+"," ",value).strip()[:1800]
    return value

CHUNK_SYSTEM="""Eres un analista de procesos de inversión. Usa solo el fragmento dado.
No inventes ni uses conocimientos externos. No copies frases largas; parafrasea.
Si no puedes atribuir una idea con seguridad a los hosts, usa scope uncertain_or_guest.
Devuelve solo JSON válido."""

CHUNK_PROMPT="""Extrae evidencia para reconstruir una estrategia. Devuelve:
{"evidence":[{"stage":"idea_generation|quality|balance_sheet|valuation|cycle_macro|entry|sizing|add_hold|exit|risk|technical|management|mistake|other","paraphrase":"máximo 350 caracteres","timestamp":"HH:MM:SS o null","scope":"hosts|uncertain_or_guest","confidence":0.0,"automation_hint":"proxy observable o null"}],"named_examples":[],"chunk_summary":"máximo 700 caracteres"}
FRAGMENTO:
"""

FINAL_SYSTEM="""Eres un analista cuantitativo auditando el método de Buy The Dip.
Usa solo evidencia parafraseada del episodio. Distingue proceso, opinión coyuntural,
ejemplo concreto e idea de invitado. Una sola mención nunca basta para regla canónica.
No cites literalmente. Devuelve solo JSON válido."""

FINAL_TEMPLATE="""Sintetiza el episodio para cruzarlo después con cientos de vídeos. Devuelve:
{"episode_summary":"máximo 1400 caracteres","process":{"idea_generation":[],"quality":[],"balance_sheet":[],"valuation":[],"cycle_macro":[],"entry":[],"sizing":[],"add_hold":[],"exit":[],"risk":[],"technical":[],"management":[],"mistakes":[]},"candidate_rules":[{"rule":"paráfrasis compacta","scope":"hosts|uncertain_or_guest","confidence":0.0,"evidence_timestamps":[],"automation_proxy":"variable/cálculo posible o null","cross_video_confirmation_required":true}],"contradictions_or_uncertainties":[],"named_examples":[],"automation_readiness":"low|medium|high"}
METADATOS:
__META__
EVIDENCIA:
__EVIDENCE__
"""

def analyze_episode(llm,transcript,metadata):
    derived=[]
    for idx,chunk in enumerate(chunk_transcript(transcript),1):
        result=chat_json(llm,CHUNK_SYSTEM,CHUNK_PROMPT+chunk,1600)
        derived.append({"chunk":idx,**sanitize(result)})
    prompt=FINAL_TEMPLATE.replace("__META__",json.dumps(metadata,ensure_ascii=False))
    prompt=prompt.replace("__EVIDENCE__",json.dumps(derived,ensure_ascii=False))
    final=chat_json(llm,FINAL_SYSTEM,prompt,2600)
    return sanitize(final),derived

def update_progress(state_dir,queue,rss):
    reviews=reviewed_ids(Path(state_dir)/"reviews"); mirror=rss_by_video(rss)
    ids=[x.get("video_id") for x in queue.get("videos") or [] if x.get("video_id")]
    eligible=[x for x in ids if x in mirror]
    progress={"schema_version":1,"updated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
              "youtube_catalog_count":len(ids),"official_podcast_matched_count":len(eligible),
              "reviewed_count":len(reviews),
              "temporarily_unavailable_audio_count":len(unavailable_ids(
                  Path(state_dir)/"unavailable_audio.json")),
              "reviewed_official_podcast_count":sum(x in mirror for x in reviews),
              "remaining_official_podcast_count":sum(x not in reviews for x in eligible),
              "coverage_note":"Official-podcast matches use local ASR; YouTube-only items remain queued."}
    atomic_json(Path(state_dir)/"semantic_progress.json",progress); return progress

def run(queue_path,rss_path,state_dir,asr_model=ASR_MODEL):
    queue=read_json(queue_path); rss=read_json(rss_path); state_dir=Path(state_dir)
    unavailable=state_dir/"unavailable_audio.json"
    selected=choose_next(queue,rss,reviewed_ids(state_dir/"reviews"),
                         unavailable_ids(unavailable))
    if selected is None:
        return {"status":"nothing_pending_or_waiting_for_transport",
                "progress":update_progress(state_dir,queue,rss)}
    q=selected["queue"]; ep=selected["rss"]; vid=q["video_id"]
    meta={"video_id":vid,"youtube_url":q.get("url"),"title":q.get("title"),
          "category":q.get("category"),"guest_likely":bool(q.get("guest_likely")),
          "podcast_guid":ep.get("guid"),"published_date":ep.get("published_date"),
          "source":"official_podcast_mirror","match_score":ep.get("match_score")}
    with tempfile.TemporaryDirectory(prefix="btd-analysis-") as tmp:
        audio=Path(tmp)/"episode.mp3"
        try:
            stage_trace("audio_download_start")
            audio_bytes=download(ep["audio_url"],audio)
            stage_trace("audio_download_complete")
        except urllib.error.HTTPError as error:
            if error.code not in (404,410):
                raise
            retry=record_missing_transport(unavailable,vid,error.code)
            # This is a transport failure, NOT a reviewed episode or an
            # inferred investment rule. Next run can select another item.
            return {"status":"audio_transport_unavailable","video_id":vid,
                    "http_status":error.code,"retry_after_utc":retry,
                    "progress":update_progress(state_dir,queue,rss)}
        if os.environ.get("BTD_NATIVE_ISOLATION") == "1":
            asr_done = native_subprocess(
                "asr", {"audio_path": str(audio), "model_name": asr_model}, tmp)
            transcript, asr = asr_done["transcript"], asr_done["asr"]
            reviewed = native_subprocess(
                "analysis", {"transcript": transcript, "metadata": meta}, tmp)
            analysis, evidence = reviewed["analysis"], reviewed["evidence"]
        else:
            # Direct path retained for simple unit tests; production uses
            # isolated native workers so SIGILL cannot hide the failing phase.
            transcript,asr=transcribe(audio,asr_model)
            llm=load_llm(os.environ.get("BTD_LLM_REPO",LLM_REPO),
                         os.environ.get("BTD_LLM_FILE",LLM_FILE))
            analysis,evidence=analyze_episode(llm,transcript,meta)
    review={"schema_version":1,"status":"machine_first_pass",
            "reviewed_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_identity":"Buy The Dip YouTube channel",
            "transport":{"kind":"official_podcast_mirror","provider":rss.get("provider"),
                         "guid":ep.get("guid"),"published_date":ep.get("published_date"),
                         "youtube_video_id":vid,"match_score":ep.get("match_score"),
                         "audio_bytes_processed_transiently":audio_bytes},
            "models":{"asr":asr,"semantic":{"repo":os.environ.get("BTD_LLM_REPO",LLM_REPO),
                                            "file":os.environ.get("BTD_LLM_FILE",LLM_FILE)}},
            "metadata":meta,"analysis":analysis,"chunk_evidence":evidence,
            "copyright_note":"No audio or verbatim transcript is persisted; only derived paraphrases."}
    atomic_json(state_dir/"reviews"/f"{vid}.json",review)
    return {"status":"reviewed","video_id":vid,"title":q.get("title"),
            "category":q.get("category"),"progress":update_progress(state_dir,queue,rss)}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--queue")
    p.add_argument("--rss")
    p.add_argument("--state")
    p.add_argument("--asr-model",default=os.environ.get("BTD_ASR_MODEL",ASR_MODEL))
    p.add_argument("--native-stage",choices=NATIVE_STAGES)
    p.add_argument("--stage-input")
    p.add_argument("--stage-output")
    a=p.parse_args(argv)
    if a.native_stage:
        if not a.stage_input or not a.stage_output or any((
                a.queue,a.rss,a.state)):
            p.error("An isolated native child requires only stage input and output")
        native_stage_child(a.native_stage,a.stage_input,a.stage_output)
        return
    if not a.queue or not a.rss or not a.state or a.stage_input or a.stage_output:
        p.error("--queue, --rss and --state are mandatory for an episode run")
    print(json.dumps(run(a.queue,a.rss,a.state,a.asr_model),
                     indent=2,ensure_ascii=False))

if __name__=="__main__": main()
