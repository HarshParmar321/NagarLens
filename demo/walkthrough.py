"""Drive the web app through the demo shot list, on the script's timings.

Two uses:
  1. Rehearsal: proves every click in demo/DEMO_SCRIPT.md works before you record.
  2. Backup take: saves a silent screen recording (demo/out/walkthrough.webm) and one still per beat.
     If a live take goes wrong, lay the voiceover over this file.

Needs both servers running (API on :8000, web app on :3000), Google Chrome, and Playwright:

    uv pip install --python .venv playwright
    .venv/Scripts/python demo/walkthrough.py            # 2:00 cut, records video
    .venv/Scripts/python demo/walkthrough.py --fast     # quick click-path check, no waiting

It only clicks and types; it changes no data except one officer decision on lead AUD-0133 in the local SQLite file.
"""
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:3000"
OUT = Path(__file__).resolve().parent / "out"
FAST = "--fast" in sys.argv
QUESTION = "माझी तक्रार BMC25-001690 चं काय झालं?"


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless="--show" not in sys.argv)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                  **({} if FAST else {"record_video_dir": str(OUT), "record_video_size": {"width": 1440, "height": 900}}))
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))

        def hold(seconds: float):
            page.wait_for_timeout(300 if FAST else int(seconds * 1000))

        def beat(n: int, name: str):
            page.screenshot(path=str(OUT / f"beat{n}_{name}.png"))
            print(f"beat {n}: {name} ok")

        def scroll_to(text: str, offset: int = -110):
            page.get_by_text(text, exact=False).first.evaluate(
                "(el, off) => window.scrollTo({top: el.getBoundingClientRect().top + window.scrollY + off, behavior: 'smooth'})", offset)

        def nav(label: str):
            page.get_by_role("link", name=label).click()
            page.wait_for_load_state("networkidle")

        # ---- warm-up: load every page once so nothing spins on camera (not part of the timed take) ----
        for path in ["/", "/audit", "/case", "/scorecards", "/next-rupee", "/ask"]:
            page.goto(URL + path, wait_until="networkidle")
        page.goto(URL + "/", wait_until="networkidle")
        page.get_by_text("Where did Kurla", exact=False).wait_for()
        page.wait_for_timeout(1500)

        # ---- 1. 0:00-0:13 hero ----
        beat(1, "hero")
        hold(13)

        # ---- 2. 0:13-0:30 ward L: money flow and map ----
        scroll_to("Follow the rupee: what it was spent on")
        hold(2)
        beat(2, "ward_money_flow")
        hold(15)

        # ---- 3. 0:30-0:57 audit: duplicate bill, side by side, officer decision ----
        nav("What doesn't add up?")
        hold(4)
        page.get_by_role("button", name="Possible duplicate bill", exact=True).click()
        page.get_by_text("This bill (flagged)").wait_for()
        scroll_to("Only ward L", -20)
        hold(15)
        beat(3, "audit_duplicate")
        page.get_by_role("button", name="Hold for evidence", exact=True).click()
        page.get_by_text("saved", exact=False).first.wait_for()
        hold(8)
        beat(3, "audit_decision")

        # ---- 4. 0:57-1:12 one case end to end ----
        nav("Follow one case")
        page.get_by_text("1 · Reported", exact=False).first.wait_for()
        hold(6)
        beat(4, "case_steps")
        scroll_to("Complaints behind this job")
        hold(9)
        beat(4, "case_complaints")

        # ---- 5. 1:12-1:32 scorecards ----
        nav("Who is responsible?")
        page.get_by_text("System problem, not a contractor problem", exact=False).wait_for()
        hold(7)
        scroll_to("Mahalaxmi Civil Contractors", -160)
        hold(13)
        beat(5, "scorecard_mahalaxmi")

        # ---- 6. 1:32-1:52 next rupee: default plan, then a tight budget ----
        nav("Where should the next rupee go?")
        page.get_by_text("Recover first", exact=False).first.wait_for()
        hold(7)
        beat(6, "plan_default")
        budget = page.locator('input[type="number"]').first
        budget.fill("500000")
        page.get_by_text("16 deferred", exact=False).first.wait_for()
        hold(4)
        scroll_to("Budget and risk weights", -24)      # bring the KPI tiles and the first ranked cards into frame
        hold(9)
        beat(6, "plan_5_lakh")

        # ---- 7. 1:52-2:00 ask in Marathi ----
        nav("Ask about my complaint")
        page.get_by_text("What happened to my complaint?", exact=False).first.wait_for()
        box = page.locator('main input').first
        box.fill(QUESTION)
        page.locator('main button[type="submit"]').first.click()
        page.get_by_text("WO25-00646", exact=False).first.wait_for()
        hold(8)
        beat(7, "ask_marathi")

        video = page.video
        ctx.close()
        browser.close()
        if video and not FAST:
            target = OUT / "walkthrough.webm"
            shutil.move(video.path(), target)
            print(f"video: {target}")
        print("page errors:", errors or "none")
        return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
