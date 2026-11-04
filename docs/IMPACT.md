# Why Fireline — the problem, with sources

Firefighters die when the people who could help them do not know where they are or
what they just said. Three incidents shaped this build.

## 1. Mungyeong, Korea — 31 Jan 2024 (2 firefighters killed)
A four-person rescue crew entered a burning food factory; when the fire spread,
two members lost contact and were trapped by heat, smoke and a collapsed ceiling.
Their colleagues escaped through a window and could not re-enter. The National Fire
Agency's joint investigation faulted, among other things, **deficient sharing of
on-scene information** (what was burning, when water was started) between crews and
command.
- Kyunghyang (NFA countermeasures, 2024-03-13): https://www.khan.co.kr/article/202403131206001
- MBC (incident report): https://imnews.imbc.com/replay/2024/nwdesk/article/6567855_36515.html

## 2. Pyeongtaek cold-storage construction site, Korea — 6 Jan 2022 (3 firefighters killed)
After a re-flash, three firefighters working on the second floor were cut off;
radio contact was lost around 09:30 and, in zero visibility, they could not find
their way out. They were found hours later.
- MBC: https://imnews.imbc.com/news/2022/society/article/6330441_35673.html
- Kyunghyang (police investigation): https://www.khan.co.kr/article/202203141402001

## 3. Bridgeport, CT, USA — 24 Jul 2010 (2 firefighters killed; NIOSH F2010-18)
NIOSH found the maydays were transmitted but **not heard or acknowledged**: the
incident commander was juggling two radio channels and missed critical traffic. The
department had a mayday procedure but had never tested whether command could
actually catch one in live radio chatter.
- NIOSH summary coverage: https://www.statter911.com/2011/06/30/niosh-says-bridgeport-fd-failed-to-respond-to-mayday-calls-in-double-lodds-many-failures-cited-in-deaths-of-lt-steve-velasquez-ff-michael-baik/
- NIOSH FACE reports index: https://www.cdc.gov/niosh/fire/

## The pattern
1. **Command drowns in voice.** Every transmission is a stream of overlapping, noisy
   speech; the one that says "mayday" sounds like all the others until it is too late.
2. **Nobody holds the picture.** Who is on which floor, which stairwell is blocked,
   where the victim in 404 was heard — this lives in people's heads and on a whiteboard.
3. **The crew inside hears nothing useful.** They get the same undifferentiated channel
   as everyone else; critical intel for *them* ("B stairs are blocked above you") is
   buried.

Fireline attacks exactly these three failures with three Meta models:
Muse Voice Transcribe turns every transmission into text in real time;
Muse Spark 1.3 triages it into a structured, prioritised event and, as an agent, decides
who inside needs to hear what; a pure-Python world model keeps one shared spatial truth
for the command dashboard and every clip-on display; SAM 3.1 turns a helmet-cam frame
into victim candidates on that map.
