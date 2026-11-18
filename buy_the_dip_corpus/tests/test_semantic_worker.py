import sys
import unittest
import json
import tempfile
import datetime as dt
import os
import signal
import subprocess
import urllib.error
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import semantic_worker as worker

class SemanticWorkerTests(unittest.TestCase):
    def test_methodology_is_processed_before_portfolio(self):
        queue={"videos":[
            {"video_id":"P","category":"portfolio_update","methodology_relevance_score":9},
            {"video_id":"M","category":"methodology","methodology_relevance_score":1},
        ]}
        rss={"episodes":[
            {"youtube_video_id":"P","match_status":"matched","audio_url":"https://example/p.mp3"},
            {"youtube_video_id":"M","match_status":"matched","audio_url":"https://example/m.mp3"},
        ]}
        selected=worker.choose_next(queue,rss,set())
        self.assertEqual(selected["queue"]["video_id"],"M")

    def test_reviewed_episode_is_skipped(self):
        queue={"videos":[
            {"video_id":"A","category":"methodology","methodology_relevance_score":10},
            {"video_id":"B","category":"methodology","methodology_relevance_score":9},
        ]}
        rss={"episodes":[
            {"youtube_video_id":"A","match_status":"matched","audio_url":"https://example/a.mp3"},
            {"youtube_video_id":"B","match_status":"matched","audio_url":"https://example/b.mp3"},
        ]}
        selected=worker.choose_next(queue,rss,{"A"})
        self.assertEqual(selected["queue"]["video_id"],"B")

    def test_unmatched_audio_is_never_selected(self):
        queue={"videos":[{"video_id":"A","category":"methodology","methodology_relevance_score":10}]}
        rss={"episodes":[{"youtube_video_id":"A","match_status":"unmatched_or_ambiguous","audio_url":"https://example/a.mp3"}]}
        self.assertIsNone(worker.choose_next(queue,rss,set()))

    def test_missing_audio_is_quarantined_not_falsely_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            queue={"videos":[
                {"video_id":"A","category":"methodology","methodology_relevance_score":10},
                {"video_id":"B","category":"methodology","methodology_relevance_score":9},
            ]}
            rss={"provider":"test","episodes":[
                {"youtube_video_id":"A","match_status":"matched",
                 "audio_url":"https://example.test/a.mp3"},
                {"youtube_video_id":"B","match_status":"matched",
                 "audio_url":"https://example.test/b.mp3"},
            ]}
            (root/"queue.json").write_text(json.dumps(queue))
            (root/"rss.json").write_text(json.dumps(rss))
            error=urllib.error.HTTPError("https://example.test/a.mp3",
                                        404,"Not Found",{},None)
            with (patch.object(worker,"download",side_effect=error),
                  patch.object(worker,"transcribe") as transcribe,
                  patch.object(worker,"load_llm") as llm):
                result=worker.run(root/"queue.json",root/"rss.json",root)
            self.assertEqual(result["status"],"audio_transport_unavailable")
            self.assertEqual(result["http_status"],404)
            self.assertEqual(result["video_id"],"A")
            transcribe.assert_not_called()
            llm.assert_not_called()
            self.assertEqual(list((root/"reviews").glob("*.json")),[])
            self.assertFalse((root/"unavailable_audio.json").read_text().find(
                "https://example.test/a.mp3")>=0)
            blocked=worker.unavailable_ids(root/"unavailable_audio.json")
            self.assertIn("A",blocked)
            selected=worker.choose_next(queue,rss,set(),blocked)
            self.assertEqual(selected["queue"]["video_id"],"B")

    def test_missing_audio_cooldown_expires_and_server_errors_still_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"unavailable_audio.json"
            then=dt.datetime(2026,10,31,12,tzinfo=dt.timezone.utc)
            worker.record_missing_transport(path,"A",410,now=then)
            self.assertEqual(worker.unavailable_ids(path,now=then),{"A"})
            self.assertEqual(worker.unavailable_ids(
                path,now=then+dt.timedelta(hours=49)),set())
            with self.assertRaises(ValueError):
                worker.record_missing_transport(path,"B",503,now=then)

    def test_chunking_preserves_all_lines(self):
        text="\n".join(f"[00:00:{i:02d}] palabra {i}" for i in range(30))
        chunks=worker.chunk_transcript(text,max_chars=100)
        self.assertGreater(len(chunks),1)
        self.assertEqual("\n".join(chunks),text)

    def test_semantic_json_uses_grammar_and_recovers_one_invalid_completion(self):
        class Stub:
            def __init__(self):
                self.kwargs = []
            def create_chat_completion(self, **kwargs):
                self.kwargs.append(kwargs)
                body = '{"evidence": [' if len(self.kwargs) == 1 else '{"evidence":[],"chunk_summary":"Validado"}'
                return {"choices":[{"message":{"content":body}}]}
        llm=Stub()
        result=worker.chat_json(llm,"Extrae solo evidencia","Texto fuente",1600)
        self.assertEqual(result["evidence"],[])
        self.assertEqual(len(llm.kwargs),2)
        self.assertTrue(all(call["response_format"] == {"type":"json_object"} for call in llm.kwargs))
        self.assertEqual(llm.kwargs[1]["temperature"],0)

    def test_semantic_json_rejects_twice_invalid_without_partial_evidence(self):
        class Broken:
            def create_chat_completion(self, **kwargs):
                return {"choices":[{"message":{"content":'{"evidence": ['}}]}
        with self.assertRaisesRegex(ValueError,"llm_invalid_json_after_retry"):
            worker.chat_json(Broken(),"Solo la fuente","Datos",1600)


    def test_sigill_is_classified_without_claiming_a_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(worker.subprocess, "run",
                              return_value=subprocess.CompletedProcess([], -signal.SIGILL)):
                with self.assertRaisesRegex(RuntimeError, "native_asr_sigill"):
                    worker.native_subprocess("asr", {"audio_path": "/tmp/temporary.mp3",
                                                      "model_name": "small"}, tmp)
            self.assertTrue((Path(tmp)/"native_asr_input.json").is_file())
            self.assertFalse((Path(tmp)/"native_asr_output.json").exists())
            self.assertEqual(list(Path(tmp).glob("*.mp3")), [])

    def test_native_child_output_requires_exact_success_and_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            def completed(command, **kwargs):
                output=Path(command[command.index("--stage-output")+1])
                worker.atomic_json(output, {"transcript":"texto " * 110,
                                             "asr":{"word_count":110}})
                self.assertEqual(kwargs["env"]["PYTHONFAULTHANDLER"], "1")
                self.assertEqual(kwargs["env"]["PYTHONUNBUFFERED"], "1")
                self.assertNotIn("shell", kwargs)
                return subprocess.CompletedProcess(command, 0)
            with patch.object(worker.subprocess, "run", side_effect=completed) as invoke:
                output=worker.native_subprocess(
                    "asr",{"audio_path":"/tmp/temporary.mp3","model_name":"small"},tmp)
            self.assertEqual(output["asr"]["word_count"],110)
            self.assertEqual(invoke.call_count,1)
            with self.assertRaisesRegex(ValueError,"reuse previous"):
                worker.native_subprocess(
                    "asr",{"audio_path":"/tmp/temporary.mp3","model_name":"small"},tmp)

    def test_semantic_sigill_keeps_queue_pending_no_false_progress_or_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            queue={"videos":[{"video_id":"SAFE","category":"methodology",
                                "methodology_relevance_score":9}]}
            rss={"provider":"synthetic","episodes":[{
                 "youtube_video_id":"SAFE","match_status":"matched",
                 "audio_url":"https://example.test/episode.mp3",
                 "guid":"synthetic"}]}
            (root/"queue.json").write_text(json.dumps(queue))
            (root/"rss.json").write_text(json.dumps(rss))
            def download_stub(_url,target):
                Path(target).write_bytes(b"temporary" * 256)
                return Path(target).stat().st_size
            calls=[]
            def native_stub(stage, _payload, _directory):
                calls.append(stage)
                if stage == "asr":
                    return {"transcript":"texto "*120,"asr":{"word_count":120}}
                raise RuntimeError("native_analysis_sigill")
            with patch.dict(os.environ,{"BTD_NATIVE_ISOLATION":"1"}), \
                 patch.object(worker,"download",side_effect=download_stub), \
                 patch.object(worker,"native_subprocess",side_effect=native_stub):
                with self.assertRaisesRegex(RuntimeError,"native_analysis_sigill"):
                    worker.run(root/"queue.json",root/"rss.json",root)
            self.assertEqual(calls,["asr","analysis"])
            self.assertFalse((root/"reviews").exists())
            self.assertFalse((root/"semantic_progress.json").exists())
            self.assertFalse(list(root.glob("native_*")))
            self.assertFalse(list(root.glob("*.mp3")))

    def test_cli_child_mode_does_not_process_episode_queue(self):
        with patch.object(worker,"native_stage_child") as child, \
             patch.object(worker,"run") as full:
            worker.main(["--native-stage","asr","--stage-input","/tmp/in",
                         "--stage-output","/tmp/out"])
            child.assert_called_once_with("asr","/tmp/in","/tmp/out")
            full.assert_not_called()

    def test_publisher_configures_identity_before_rebase(self):
        workflow = (ROOT.parent / ".github/workflows/buy_the_dip_semantic.yml").read_text()
        publisher = workflow.split("- name: Commit semantic evidence", 1)[1]
        self.assertLess(publisher.index("git config user.name"), publisher.index("\n            git commit -m"))
        self.assertLess(publisher.index("git config user.email"), publisher.index("git pull --rebase"))
        self.assertLess(publisher.index("\n            git commit -m"), publisher.index("git pull --rebase"))
        self.assertIn("git push", publisher)

    def test_sanitizer_removes_verbatim_fields(self):
        value={"summary":"ok","transcript":"secret","nested":{"quote":"literal","rule":"keep"}}
        clean=worker.sanitize(value)
        self.assertNotIn("transcript",clean)
        self.assertNotIn("quote",clean["nested"])
        self.assertEqual(clean["nested"]["rule"],"keep")

if __name__=="__main__":
    unittest.main()
