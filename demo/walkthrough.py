"""Build the demo video: the app walked through beat by beat, with narration in sync.

How the sync works: each beat has one narration clip. The time a beat stays on screen is the length of its
clip plus a short pause, and the clicks inside a beat happen at fixed fractions of that clip. The clips are
then laid onto one audio track at the moment each beat actually started, and merged with the screen recording.
So the voice cannot drift from the picture, whatever voice is used.

Narration source, in this order:
  1. Your own voice: put demo/narration/beat1.wav ... beat7.wav (any length) and they are used as they are.
     Record them with any recorder while reading NARRATION below. This is the recommended final version.
  2. --tts sapi (default): the offline Windows voice. No network. A clear guide track, robotic.
  3. --tts edge: a neural Indian-English voice through the `edge-tts` package. This SENDS THE NARRATION TEXT
     to Microsoft's online speech service, so only use it if that is acceptable.

Run from the repo root with both servers up (API :8000, web app :3000) and Google Chrome installed:

    uv pip install --python .venv playwright imageio-ffmpeg
    .venv/Scripts/python demo/walkthrough.py            # narrated video -> demo/out/nagarlens_demo.mp4
    .venv/Scripts/python demo/walkthrough.py --fast     # click-path check only, a few seconds, no video
    .venv/Scripts/python demo/walkthrough.py --silent   # video without narration, 2:00 timings
    .venv/Scripts/python demo/walkthrough.py --url http://localhost:3100   # record another copy of the app

Record against a production build (`cd frontend && npm run build && npm run start`) while nobody is editing
the frontend: a half-saved file shows up in a dev-server recording as an error overlay.

The only data it changes is one officer decision on lead AUD-0133 in the local SQLite file: it clears it before
the take and sets it to "hold for evidence" during the take. Pass --api if the API is not on localhost:8000.
The narration below must stay word for word the same as the voiceover column in demo/DEMO_SCRIPT.md.
"""
import shutil
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "http://localhost:3000"
API = sys.argv[sys.argv.index("--api") + 1] if "--api" in sys.argv else "http://localhost:8000"
HERE = Path(__file__).resolve().parent
OUT, VOICE_DIR = HERE / "out", HERE / "narration"
FAST, SILENT = "--fast" in sys.argv, "--silent" in sys.argv
TTS = sys.argv[sys.argv.index("--tts") + 1] if "--tts" in sys.argv else "sapi"
QUESTION = "माझी तक्रार BMC25-001690 चं काय झालं?"
PAUSE = 0.7                      # silence after each clip before the next beat starts
RATE, SAMPLE_WIDTH = 44100, 2    # audio track format: 44.1 kHz, 16-bit, mono

# name, fallback seconds when silent, narration
NARRATION = [
    ("hero", 13, "Every monsoon, Mumbai pays to fix the same roads again. Last season it billed thirteen point four three "
                 "crore rupees for repairs. NagarLens finds three point two two crore that needs a second look, and shows "
                 "where to spend it next. The data is synthetic."),
    ("ward_money_flow", 17, "Take Kurla. It billed a hundred and ten percent of its budget. Follow the rupee: most repairs "
                            "held, but thirty-nine point six lakh was billed on roads still under the original contractor's warranty."),
    ("audit_duplicate", 27, "Three exact rules, tuned so normal variation is never flagged. Here is one lead. Two bills on "
                            "LBS Marg: same contractor, same method, same area, three days apart, half a percent different. "
                            "One has three citizen complaints behind it. The other has none. It's a lead, not an accusation, "
                            "so the officer decides: hold for evidence."),
    ("case", 15, "Every bill traces back to people. Four complaints, one in Marathi, led to this cave-in repair. It was late "
                 "against a twenty-four hour deadline, failed within thirty days, and sits on a road still under warranty."),
    ("scorecards", 20, "Who is responsible? We compare like with like. Twenty-four hour deadlines are missed by almost "
                       "everyone, so that is a system problem. Durability is where contractors differ: on the same repair "
                       "methods, this one re-opens thirty-eight percent of fixes where its peers manage twenty-three."),
    ("next_rupee", 20, "Then reinvest. Kurla overspent, so the plan uses money it can recover. Open complaints are ranked by "
                       "risk: hospital roads, bus routes, flood hotspots. Cut the budget to five lakh and it funds nine, "
                       "defers sixteen, and never overspends. Five more go back to the warranty contractor at zero cost."),
    ("ask", 8, "And a citizen can ask, in Marathi, what happened to her complaint, and get the answer in Marathi. "
               "NagarLens: recover, then reinvest."),
]
# Spellings that help a synthetic voice; the words spoken are the same.
SAY_AS = {"NagarLens": "Nagar Lens", "LBS Marg": "L B S Marg", "lakh": "laakh", "re-opens": "reopens"}


# ------------------------------------------------------------------ narration clips
def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def to_track_format(src: Path, dst: Path):
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(RATE),
                    "-sample_fmt", "s16", str(dst)], check=True)


def synthesize(text: str, dst: Path):
    for k, v in SAY_AS.items():
        text = text.replace(k, v)
    if TTS == "edge":
        import asyncio

        import edge_tts
        raw = dst.with_suffix(".mp3")
        asyncio.run(edge_tts.Communicate(text, "en-IN-NeerjaNeural", rate="+4%").save(str(raw)))
    else:  # offline Windows voice
        raw = dst.with_suffix(".raw.wav")
        script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "try { $s.SelectVoice('Microsoft Zira Desktop') } catch {}; $s.Rate = 1; "
                  f"$s.SetOutputToWaveFile('{raw}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", script], input=text.encode("utf-8"), check=True)
    to_track_format(raw, dst)
    raw.unlink(missing_ok=True)


def clip_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def prepare_clips() -> list[Path]:
    """One clip per beat in the track format: your own recording if present, else text-to-speech."""
    clips = []
    for i, (name, _, text) in enumerate(NARRATION, 1):
        dst = OUT / f"narration_beat{i}.wav"
        own = VOICE_DIR / f"beat{i}.wav"
        if own.exists():
            to_track_format(own, dst)
            src = "your recording"
        else:
            synthesize(text, dst)
            src = f"{TTS} voice"
        print(f"narration {i} ({name}): {clip_seconds(dst):.1f}s from {src}")
        clips.append(dst)
    return clips


def build_track(clips: list[Path], starts: list[float], total: float, dst: Path):
    """Lay each clip onto one silent track at the second its beat started on screen."""
    track = bytearray(int(total * RATE) * SAMPLE_WIDTH)
    for clip, start in zip(clips, starts):
        with wave.open(str(clip)) as w:
            data = w.readframes(w.getnframes())
        at = int(start * RATE) * SAMPLE_WIDTH
        data = data[:max(0, len(track) - at)]
        track[at:at + len(data)] = data
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(RATE)
        w.writeframes(bytes(track))


# ------------------------------------------------------------------ the take
def main():
    OUT.mkdir(exist_ok=True)
    # Clear any decision saved by a rehearsal, so the "Hold for evidence" click visibly changes the screen.
    try:
        urllib.request.urlopen(urllib.request.Request(f"{API}/api/findings/AUD-0133/review", method="DELETE"), timeout=10)
    except Exception as e:  # an older API without the endpoint: the take still works, the button just starts selected
        print("could not reset the demo decision:", e)
    narrated = not FAST and not SILENT
    clips = prepare_clips() if narrated else []
    seconds = [clip_seconds(c) + PAUSE for c in clips] if narrated else [s for _, s, _ in NARRATION]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless="--show" not in sys.argv)
        view = {"width": 1440, "height": 900}

        # Warm-up in a throwaway window so nothing compiles or spins on camera.
        warm_ctx = browser.new_context(viewport=view)
        warm = warm_ctx.new_page()
        for path in ["/", "/audit", "/case", "/scorecards", "/next-rupee", "/ask"]:
            warm.goto(URL + path, wait_until="networkidle")
        warm_ctx.close()

        ctx = browser.new_context(viewport=view, **({} if FAST else {"record_video_dir": str(OUT), "record_video_size": view}))
        page = ctx.new_page()
        t_video = time.monotonic()                     # the recording starts when the page is created
        errors, starts = [], []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        beat = {"t0": 0.0, "len": 0.0}

        def start(n: int):
            beat["t0"], beat["len"] = time.monotonic(), seconds[n - 1]
            starts.append(beat["t0"] - t_video)

        def until(fraction: float):
            """Wait until this fraction of the current beat's narration has played."""
            if FAST:
                page.wait_for_timeout(250)
                return
            left = beat["t0"] + fraction * beat["len"] - time.monotonic()
            if left > 0:
                page.wait_for_timeout(int(left * 1000))

        def shot(n: int, name: str):
            page.screenshot(path=str(OUT / f"beat{n}_{name}.png"))
            print(f"beat {n}: {name} ok")

        def scroll_to(text: str, offset: int = -110):
            page.get_by_text(text, exact=False).first.evaluate(
                "(el, off) => window.scrollTo({top: el.getBoundingClientRect().top + window.scrollY + off, behavior: 'smooth'})", offset)

        def click(locator):
            """Ring the control briefly so the viewer sees what is pressed (the recording shows no mouse pointer)."""
            locator.evaluate("el => { el.style.outline = '3px solid #FF9B6A'; el.style.outlineOffset = '3px'; "
                             "setTimeout(() => { el.style.outline = ''; }, 900); }")
            page.wait_for_timeout(50 if FAST else 450)
            locator.click()

        def nav(label: str):
            click(page.get_by_role("link", name=label))
            page.wait_for_load_state("networkidle")

        page.goto(URL + "/", wait_until="networkidle")
        page.get_by_text("Where did Kurla", exact=False).wait_for()
        page.wait_for_timeout(1200)

        # 1. hero
        start(1)
        shot(1, "hero")
        until(1.0)

        # 2. ward L: money flow and map
        start(2)
        scroll_to("Follow the rupee: what it was spent on")
        until(0.5)
        shot(2, "ward_money_flow")
        until(1.0)

        # 3. audit: duplicate bill side by side, then the officer's decision on the last sentence
        start(3)
        nav("What doesn't add up?")
        until(0.12)
        click(page.get_by_role("button", name="Possible duplicate bill", exact=True))
        page.get_by_text("This bill (flagged)").wait_for()
        scroll_to("Only ward L", -20)
        until(0.6)
        shot(3, "audit_duplicate")
        until(0.86)
        click(page.get_by_role("button", name="Hold for evidence", exact=True))
        page.get_by_text("saved", exact=False).first.wait_for()
        shot(3, "audit_decision")
        until(1.0)

        # 4. one case end to end
        start(4)
        nav("Follow one case")
        page.get_by_text("1 · Reported", exact=False).first.wait_for()
        until(0.18)
        shot(4, "case_steps")
        scroll_to("Pick a case", -20)
        until(0.6)
        scroll_to("Complaints behind this job")
        until(0.8)
        shot(4, "case_complaints")
        until(1.0)

        # 5. scorecards: system problem first, then one contractor card
        start(5)
        nav("Who is responsible?")
        page.get_by_text("System problem, not a contractor problem", exact=False).wait_for()
        until(0.45)
        scroll_to("Mahalaxmi Civil Contractors", -160)
        until(0.8)
        shot(5, "scorecard_mahalaxmi")
        until(1.0)

        # 6. next rupee: default plan, then a tight budget
        start(6)
        nav("Where should the next rupee go?")
        page.get_by_text("Recover first", exact=False).first.wait_for()
        until(0.3)
        shot(6, "plan_default")
        scroll_to("Budget and risk weights", -24)
        until(0.52)
        budget = page.locator('input[type="number"]').first
        click(budget)
        budget.fill("500000")
        page.get_by_text("16 deferred", exact=False).first.wait_for()
        until(0.8)
        shot(6, "plan_5_lakh")
        until(1.0)

        # 7. ask in Marathi
        start(7)
        nav("Ask about my complaint")
        page.get_by_text("What happened to my complaint?", exact=False).first.wait_for()
        page.locator("main input").first.fill(QUESTION)
        until(0.25)
        click(page.locator('main button[type="submit"]').first)
        page.get_by_text("WO25-00646", exact=False).first.wait_for()
        until(0.7)
        shot(7, "ask_marathi")
        until(1.0)
        if not FAST:
            page.wait_for_timeout(1200)
        total = time.monotonic() - t_video

        video = page.video
        ctx.close()                                    # the recording is complete once the context closes
        video_path = None if FAST else video.path()
        browser.close()

    print("page errors:", errors or "none")
    if FAST:
        return 1 if errors else 0

    raw = OUT / "screen.webm"
    shutil.move(video_path, raw)
    lead = max(0.0, starts[0] - 0.4)                       # cut the page load before beat 1
    final = OUT / ("nagarlens_demo_silent.mp4" if SILENT else "nagarlens_demo.mp4")
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{lead:.2f}", "-i", str(raw)]
    if narrated:
        track = OUT / "narration.wav"
        build_track(clips, [s - lead + 0.25 for s in starts], total - lead, track)
        cmd += ["-i", str(track), "-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-r", "30", "-movflags", "+faststart", str(final)]
    subprocess.run(cmd, check=True)
    print("beat starts (s):", [round(s - lead, 1) for s in starts])
    print(f"video: {final}  ({total - lead:.0f}s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
