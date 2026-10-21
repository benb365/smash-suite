"""Synthetic control checks. No real process, sampler, model or authorization is started."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

path = Path(__file__).with_name("profile_runs.py")
spec = importlib.util.spec_from_file_location("profile_runs_under_check", path)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class ControlChecks(unittest.TestCase):
    def test_real_request_return_is_observed_without_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            states = [dict(status="running", stage="observation", progress=.1),
                      dict(status="running", stage="observation", progress=.2),
                      dict(status="running", stage="pose", progress=.3)]
            calls = []
            def original(method, url, **kwargs):
                calls.append((method, url, kwargs))
                return states[len(calls)-1]
            observer = control.StageObserver(original, folder)
            for index in range(3):
                result = observer("GET", "http://local/api/sessions/id", headers={"Authorization": "secret-token"})
                self.assertIs(result, states[index])
            current = json.loads((folder / "stage-current.json").read_text())
            events = [json.loads(line) for line in (folder / "stage-events.jsonl").read_text().splitlines()]
            self.assertEqual(len(events), 2)
            self.assertEqual(current["progress"], .3)
            self.assertEqual(set(current), {"monotonic_s", "status", "stage", "progress"})
            self.assertNotIn("secret-token", (folder / "stage-events.jsonl").read_text())
            self.assertFalse((folder / "stage-current.json.tmp").exists())
            post = control.StageObserver(lambda *a, **kw: states[0], folder)
            before = (folder / "stage-current.json").read_text()
            post("POST", "unused")
            self.assertEqual((folder / "stage-current.json").read_text(), before)

    def test_four_seconds_requires_continuous_matching_fresh_state(self):
        gate = control.StageGate("observation")
        def state(now, stage="observation"):
            return dict(monotonic_s=now, status="running", stage=stage, progress=.2)
        self.assertFalse(gate.eligible(state(10), 10))
        self.assertFalse(gate.eligible(state(13.9), 13.9))
        self.assertTrue(gate.eligible(state(14), 14))
        self.assertEqual(gate.first_state["monotonic_s"], 10)
        self.assertFalse(gate.eligible(state(14), 17))  # Stale GET is not confirmation.
        self.assertFalse(gate.eligible(state(18, "other"), 18))
        self.assertFalse(gate.eligible(state(20), 20))
        self.assertFalse(gate.eligible(state(23.9), 23.9))

    def test_window_command_and_phase_change_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            record = control.Recording(folder / "recording.json", dict(native_windows=[], diagnostics=[]))
            state = dict(monotonic_s=4., status="running", stage=control.STAGES["observation"], progress=.1)
            calls = []
            def fake_popen(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(pid=123)
            with patch.object(control.time, "monotonic", return_value=4.1):
                window, _, log = control.start_window("observation", state, 99, folder, record,
                    trigger_state=dict(state, monotonic_s=0.), popen=fake_popen)
            log.close()
            self.assertEqual(calls[0][calls[0].index("--time-limit")+1], "8s")
            self.assertIn("GPU", calls[0])
            self.assertIn("os_signpost", calls[0])
            self.assertEqual(window["trigger_observed_monotonic_s"], 0.)
            window["ready_monotonic_s"] = 5.
            changed = dict(monotonic_s=7., status="running", stage="different", progress=.3)
            control.observe_window(window, changed, 7.1, record)
            self.assertEqual(len(record.snapshot()["diagnostics"]), 1)
            control.observe_window(window, dict(changed, monotonic_s=14.), 14., record)
            self.assertEqual(len(record.snapshot()["diagnostics"]), 1)  # Save time is not capture coverage.

    def test_explicit_case_selection_preserves_a(self):
        with patch.object(control, "run") as run:
            with self.assertRaises(SystemExit):
                control.main([])
            with self.assertRaises(SystemExit):
                control.main(["A-short"])
            self.assertEqual(control.main(["C-short", "D-short"]), 0)
            self.assertEqual([args.args[0] for args in run.call_args_list], ["C-short", "D-short"])

    def test_full_synthetic_controller_c_d_and_missing_stage(self):
        # A synthetic clock and fake Popen exercise sequencing, background saves,
        # real stage files, UID checks and release ordering without any OS spawn.
        for case, missing in [("C-short", False), ("D-short", False), ("C-short", True)]:
            with self.subTest(case=case, missing=missing), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary);runtime=root/"runtime";runtime.mkdir()
                controls=runtime/("profile-control-"+case[0]);profile=runtime/("profile-"+case[0])/case
                clock=SimpleNamespace(now=0.);condition=threading.Condition();processes=[];native=[]
                def publish():
                    if not controls.exists():return
                    stage = "unrelated" if missing else (control.STAGES["observation"] if clock.now < 20 else control.STAGES["pose"])
                    control.save(controls/"stage-current.json", dict(monotonic_s=clock.now,status="running",stage=stage,progress=.3))
                class Process:
                    def __init__(self, kind, end):
                        self.kind,self.end=kind,end;self.pid=100+len(processes);self.returncode=None;processes.append(self)
                    def poll(self):
                        if clock.now>=self.end:self.returncode=0
                        return self.returncode
                    def wait(self,timeout=None):
                        with condition:
                            while self.poll() is None:condition.wait(.05)
                        return self.returncode
                    def send_signal(self,signal):self.returncode=0
                    def terminate(self):self.returncode=-15
                def popen(command, **kwargs):
                    if "--runner" in command:
                        profile.mkdir(parents=True)
                        control.save(profile/"profile-ready.json",dict(pid=2,release_file=str(profile/"release")))
                        publish();return Process("runner",40.)
                    if command[0]=="/usr/bin/osascript":
                        (controls/"py-spy.log").write_text("Sampling process\n")
                        self.assertFalse((profile/"release").exists())
                        return Process("spy",40.)
                    self.assertEqual(command[:3],["xcrun","xctrace","record"])
                    self.assertTrue(all(p.poll() is not None for p in native), "two native recordings overlapped")
                    self.assertTrue((profile/"release").exists(), "native should not hold initial Python release")
                    self.assertEqual(command[command.index("--time-limit")+1],"8s")
                    self.assertGreaterEqual(clock.now,4.)
                    Path(command[command.index("--output")+1]).mkdir()
                    kwargs["stdout"].write("Ctrl-C to stop the recording\n");kwargs["stdout"].flush()
                    process=Process("native",clock.now+11.);native.append(process);return process
                def sleep(seconds):
                    with condition:
                        clock.now+=seconds;publish();condition.notify_all()
                    threading.Event().wait(.0001)
                target=SimpleNamespace(uids=lambda:SimpleNamespace(real=501),is_running=lambda:clock.now<40,
                                       status=lambda:"running" if clock.now<40 else "zombie")
                psutil=SimpleNamespace(Process=lambda pid:target,STATUS_ZOMBIE="zombie",Error=RuntimeError)
                with ExitStack() as stack:
                    for obj,key,value in [(control,"ROOT",root),(control,"RUNTIME",runtime),
                        (control.os,"getuid",lambda:501),(control.subprocess,"Popen",popen),
                        (control.time,"monotonic",lambda:clock.now),(control.time,"time",lambda:1000+clock.now),
                        (control.time,"sleep",sleep)]:stack.enter_context(patch.object(obj,key,value))
                    stack.enter_context(patch.dict("sys.modules",{"psutil":psutil}))
                    if missing:
                        with self.assertRaises(RuntimeError):control.run(case)
                    else:control.run(case)
                data=json.loads((controls/"recording.json").read_text())
                self.assertEqual(data["target_uid"],501)
                self.assertEqual(data["runner_returncode"],0)
                self.assertEqual(data["py_spy_returncode"],0)
                self.assertEqual(data["status"],"failed" if missing else "recorded_pending_TOC_and_sample_validation")
                self.assertEqual(len(native),0 if missing else (2 if case=="D-short" else 1))
                for window in data["native_windows"]:
                    self.assertGreaterEqual(window["attach_requested_monotonic_s"]-window["trigger_observed_monotonic_s"],4.)
                    self.assertIsNotNone(window["ready_monotonic_s"])
                    self.assertIsNotNone(window["completed_monotonic_s"])
                    self.assertEqual(window["trace_returncode"],0)
                    self.assertEqual(window["requested_duration_s"],8)


if __name__=="__main__":
    unittest.main(verbosity=2)
