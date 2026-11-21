# NagarLens demo video: 3-minute script (Team 11)

**Target:** recorded and uploaded by 14:30–14:45. **Length:** 2:50–3:00. **Recorder:** Kshitij.
Every number below comes from the app (organizer's synthetic dataset). Verify each on screen before recording. If a teammate's feature isn't merged by 14:00, skip its beat and use the fallback line.

## The story in one sentence

> Mumbai billed ₹13.43 Cr for 2025 monsoon road repairs. ₹3.22 Cr of it needs a second look. Recover that money first, then spend it where the risk is highest.

## Shot list

| Time | Screen (route) | What you do | Voiceover |
|---|---|---|---|
| 0:00–0:15 | `/` hero band | Open on the dark hero: ₹13.43 Cr → ₹3.22 Cr → Next rupee plan | "Every monsoon Mumbai pays to fix the same roads again. NagarLens follows every rupee from a citizen's complaint to a fix that held, or didn't." |
| 0:15–0:40 | `/` with ward **L · Kurla** | Pick Kurla. Point at the budget-to-outcome money flow | "Kurla had ₹1.19 crore and billed ₹1.30 crore, 110% of budget. Follow the money: most of it held, but ₹39.6 lakh went on roads still under the original contractor's warranty, where BMC shouldn't have paid at all." |
| 0:40–1:05 | `/case` preset **WO25-02068** | Walk the six steps left to right, then the map | "One case end to end. Four complaints, a road cave-in on Kurla Andheri Road, ₹1.98 lakh billed. The road was resurfaced in February 2024 and is still under its Defect Liability Period. The verdict is a review lead, not an accusation: claim it from the warranty contractor." |
| 1:05–1:30 | `/audit` | Show the three rule totals, open the duplicate-bill evidence (WO25-02472 next to WO25-00373), then mark it "hold for evidence" | "Three precise rules, tuned to avoid flagging normal variation: ₹2.62 crore paid during warranty, ₹44.7 lakh above the rate card, ₹25.9 lakh in possible duplicate bills. Here, same road, same contractor, two days apart, near-identical bill, and no complaint behind the second one. A reviewer records the decision." |
| 1:30–1:55 | `/scorecards` | Contractors: point at the actual-vs-expected chart, open Mahalaxmi. Switch to Wards and open L | "Fair accountability means comparing like with like. On the same repair methods, three contractors hold up best and three re-open most often. Kurla's 32% on-time rate looks bad, but against wards with the same deadlines and flood risk it's in line, so we don't blame Kurla for the rain." |
| 1:55–2:30 | `/next-rupee`, ward L | Show the "recover, then reinvest" banner, the ranked cards with chips and the map. Drag the flood weight up and watch the order change | "Where should the next rupee go? Kurla's whole open backlog costs about ₹16.5 lakh, well within the ₹41.9 lakh it can recover. So the ranking sets the order crews work in: hospital roads, flood hotspots, bus routes. Five issues go back to the warranty contractor at zero cost to BMC. Seven of the top ten differ from simply counting complaints." |
| 2:30–2:50 | `/ask` | Type in Marathi: `माझी तक्रार BMC25-001690 चं काय झालं?` | "A citizen asks in Marathi and gets the answer in Marathi, straight from the records: patched within a day, but the fix failed within 30 days." |
| 2:50–3:00 | `/` hero | Back to the headline | "NagarLens. Recover, then reinvest. Team 11." |

## Teammate features (add a 5–10 s beat each only if merged by 14:00)

| Feature (owner) | Where it fits | Fallback if not merged |
|---|---|---|
| Three-way verdict, fair hearing, repair receipt (Harsh) | After the case verdict at 1:05 | Skip; the case verdict already covers it |
| Rain/flood-adjusted grades, evidence-request letter (Shariyan) | In the scorecards beat at 1:30–1:55 | Use the "same flood risk" line as written |
| Strategy comparison: same budget three ways (Aditya) | Before the weight drag at 2:10 | Use the "seven of the top ten differ" line |
| Road history page (Deven) | In the case beat, from the road | Use the repair history chart on `/case` |

## Honesty rules for the voiceover

- Say "the dataset is synthetic; contractors are fictional" once, on screen or in the voiceover.
- Only say "Claude wrote this" when the text's badge says Claude. Without an API key, the badges read "Template", so describe what the output is, not who wrote it.
- Call flags "review leads", never fraud or overcharging.

## Recording checklist

1. Start both servers from the repo root: `.venv/Scripts/python -m uvicorn backend.main:app --port 8000`, then `cd frontend && npm run dev`.
2. Click through every page once before recording, so data and AI answers are cached and nothing loads on camera.
3. Browser at 1440×900, light mode, zoom 100–110%, notifications off, one clean tab.
4. Record with OBS or the Windows Game Bar (Win+Alt+R) and the mic close by. Read from this script.
5. Backup if the web app breaks: the same story runs in the Streamlit fallback (`.venv/Scripts/python -m streamlit run app.py`): Ward overview, Follow a case, Recovery ledger, Scorecards, Next rupee, Ask.
6. Export as 1080p MP4 and check the audio before uploading.
