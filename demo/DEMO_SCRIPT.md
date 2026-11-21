# NagarLens demo video: plan and script (Team 11)

**Deliverable:** one screen recording with voiceover, 2:00 (extended cut 3:00 if the submission allows it).
**Ready for internal review by 14:30, final by 14:45. Recorder and voice: Kshitij.**
Every number in the voiceover is checked against the app by `demo/check_demo.py`. Run it before recording and after every merge. If it prints FAIL, fix the line or the code; never narrate a number it rejects.

## The story in one sentence

> Mumbai billed ₹13.43 Cr for 2025 monsoon road repairs. ₹3.22 Cr of it needs a second look. Recover that money first, then spend it where the risk is highest.

The whole video stays in one ward, **L · Kurla**, so the viewer follows one place from the money to the complaint to the plan. Each beat answers one judging criterion.

## Plan for the next 90 minutes

| When | What | Who |
|---|---|---|
| now | Put `ANTHROPIC_API_KEY` in `.env`, restart the API, open each demo screen once so the Claude answers are cached; commit `data/cache/ai_cache.json` | Kshitij + lead session |
| 13:45 | Run `demo/check_demo.py` and `demo/walkthrough.py --fast`; read the script aloud once against a timer | Kshitij |
| 14:00 | PRs open. Decide which teammate beats are in (table below) | Kshitij |
| 14:15 | Merge cut-off. Re-run both checks on `main` | lead session |
| 14:15–14:30 | Record. Two full takes, keep the better one | Kshitij |
| 14:30–14:45 | Internal review against the checklist at the bottom; one re-take if needed | whole team |
| 14:45 | Export 1080p MP4, upload, paste the link in the submission form | Kshitij |

## Shot list and voiceover: 2:00 cut

Read at a steady pace: about 275 words, which leaves ten seconds of slack. Clicks are in **bold**.

| # | Time | Screen | What you do | Voiceover | Criterion |
|---|---|---|---|---|---|
| 1 | 0:00–0:13 | `/` hero band, ward L | Hold on the dark band: ₹13.43 Cr → ₹3.22 Cr → Next rupee plan | "Every monsoon, Mumbai pays to fix the same roads again. Last season it billed thirteen point four three crore rupees for repairs. NagarLens finds three point two two crore that needs a second look, and shows where to spend it next. The data is synthetic." | The pitch |
| 2 | 0:13–0:30 | `/` money flow and ward map | Scroll to "Follow the rupee". Trace Billed → work type → outcome with the cursor, end on "Paid during warranty" | "Take Kurla. It billed a hundred and ten percent of its budget. Follow the rupee: most repairs held, but thirty-nine point six lakh was billed on roads still under the original contractor's warranty." | Connects the trail |
| 3 | 0:30–0:57 | `/audit` | **What doesn't add up?** → **Possible duplicate bill**. The first lead (AUD-0133) opens with two bills side by side. Point at the `=` marks, then **Hold for evidence** | "Three exact rules, tuned so normal variation is never flagged. Here is one lead. Two bills on LBS Marg: same contractor, same method, same area, three days apart, half a percent different. One has three citizen complaints behind it. The other has none. It's a lead, not an accusation, so the officer decides: hold for evidence." | Audit accuracy |
| 4 | 0:57–1:12 | `/case` | **Follow one case** (WO25-02068 is preselected). Run the cursor along the six steps, then scroll to the complaints | "Every bill traces back to people. Four complaints, one in Marathi, led to this cave-in repair. It was late against a twenty-four hour deadline, failed within thirty days, and sits on a road still under warranty." | Connects the trail |
| 5 | 1:12–1:32 | `/scorecards` | **Who is responsible?** Pause on the blue "System problem" banner, then scroll to the Mahalaxmi card: chips and the 38% vs 23% tile | "Who is responsible? We compare like with like. Twenty-four hour deadlines are missed by almost everyone, so that is a system problem. Durability is where contractors differ: on the same repair methods, this one re-opens thirty-eight percent of fixes where its peers manage twenty-three." | Fair accountability |
| 6 | 1:32–1:52 | `/next-rupee` | **Where should the next rupee go?** Pause on the green banner. Type **500000** in the budget box, then scroll down a little so the tiles (9 funded, 16 deferred, 5 to warranty) and the first ranked cards with their chips are in frame | "Then reinvest. Kurla overspent, so the plan uses money it can recover. Open complaints are ranked by risk: hospital roads, bus routes, flood hotspots. Cut the budget to five lakh and it funds nine, defers sixteen, and never overspends. Five more go back to the warranty contractor at zero cost." | Budget smarts |
| 7 | 1:52–2:00 | `/ask` | **Ask about my complaint** → **Ask** (the Marathi question is prefilled) | "And a citizen can ask, in Marathi, what happened to her complaint, and get the answer in Marathi. NagarLens: recover, then reinvest." | Usable demo |

## Extended cut (3:00): optional beats

Use these only if the submission allows three minutes. Each is 10 to 15 seconds and slots in after the beat named.

| After beat | Screen and action | Voiceover |
|---|---|---|
| 2 | `/` ward map: hover two wards, click another, click back to L | "Every ward is on the map, shaded by rupees to review. Click one and every page follows." |
| 3 | `/audit`: **Above rate card**, open the first lead, show the three bars | "The rate-card rule only fires above one point four times the standard cost. Normal jobs sit between point seven five and one point three, and they are never flagged." |
| 5 | `/scorecards`: **wards**, find Ward L | "Kurla finishes thirty-two percent of repairs on time. That looks bad, but wards with the same deadlines and flood risk manage thirty-four, so Kurla is in line. We don't blame a ward for its rain." |
| 6 | `/next-rupee`: drag **Hospitals & schools** to 0, then back | "Every weight is adjustable. Seven of the top ten issues differ from simply counting complaints." |
| 7 | `/ask`: scroll to the tiles under the answer | "The answer comes from the linked records: the work order, the contractor, the bill, and whether the fix held." |

## Teammate features: add a beat only if merged by 14:15

| Feature (owner) | Where it goes | Line to add | If not merged |
|---|---|---|---|
| Recommended verdict + fair hearing (Harsh) | Beat 3, before the decision click | "NagarLens recommends a verdict and shows both sides: the auditor's case and the fair explanation." | Keep beat 3 as written |
| Evidence-request letter (Shariyan) | Beat 3, after the decision click | "One click drafts a request for evidence. Not a legal notice." | Skip |
| Rain and flood context on scorecards (Shariyan) | Beat 5 | "Each card shows the heavy-rain weeks the work was done in." | Keep beat 5 as written |
| Strategy comparison (Aditya) | Beat 6, after typing the budget | "The same five lakh spent three ways. The risk plan covers more hospital roads and flood spots than chasing complaint counts." (say only numbers on screen) | Keep beat 6 as written |
| Road history page (Deven) | Beat 4, click the road name | "One page per road: every repair, every rupee, every repeat failure." | Use the road table on `/case` |

Adding a beat means cutting something. In the 2:00 cut, drop beat 4's second sentence first, then the last sentence of beat 6.

## Honesty rules for the voiceover

- Say "the data is synthetic" once (beat 1). The "Synthetic (organizer)" badge is on every page.
- Say "billed", never "paid" or "spent by BMC": the dataset has bills, not payments.
- Flags are "leads" or "needs a second look". Never fraud, scam, overcharging or cheating.
- Only say "Claude wrote this" when the badge on screen reads "Written by Claude". Without the API key the badges read "Template (Claude offline)"; in that case describe what the text is, not who wrote it.
- Name the fictional contractor only in beat 5, and only with its numbers next to it.

## Before you record

1. Start both servers from the repo root:
   `.venv/Scripts/python -m uvicorn backend.main:app --port 8000` and `cd frontend && npm run dev`.
2. `.venv/Scripts/python demo/check_demo.py` → must end with `ALL CLAIMS MATCH THE APP`. Its last line also tells you whether Claude is live.
3. `.venv/Scripts/python demo/walkthrough.py --fast` → every beat prints `ok` and `page errors: none`. This proves each click in the shot list works.
4. Browser: one clean window at 1440×900, 100% zoom, bookmarks bar hidden, notifications off. Ward **L · Kurla** selected. Hide the round Next.js dev badge (bottom left) by recording a production build: `cd frontend && npm run build && npm run start`.
5. If the audit page already shows a saved decision on AUD-0133 from a rehearsal, that is fine: clicking **Hold for evidence** again re-saves it.
6. Record with OBS or the Windows Game Bar (Win+Alt+R), mic close, room quiet. Read from this file on a second screen.

## Backup take

`.venv/Scripts/python demo/walkthrough.py` drives the browser through the seven beats on the timings above and saves `demo/out/walkthrough.webm` (silent, 1440×900) plus one still per beat. If a live take goes wrong, record the voiceover on its own and lay it over that file. `demo/out/` is ignored by git.

Last resort, if the web app itself is broken: the Streamlit fallback (`.venv/Scripts/python -m streamlit run app.py`) tells the same story in tabs. The figures are the same; the clicks differ.

## Review checklist (14:30–14:45)

- [ ] Under the time limit, and the first ten seconds state the problem and the headline number.
- [ ] Every number spoken is visible on screen at that moment.
- [ ] Each of the five judging criteria has its beat: audit accuracy (3), fair accountability (5), budget smarts (6), connects the trail (2, 4), usable demo (7).
- [ ] "Synthetic" is said once and no blame word is spoken or shown.
- [ ] No loading spinner, error box, dev badge, or personal tab/notification on screen.
- [ ] Audio is clear from start to finish; no clipped first word.
- [ ] The repo link in the submission opens the README with the two start commands.
