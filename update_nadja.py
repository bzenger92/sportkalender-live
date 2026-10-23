"""Build Nadja's single subscribed calendar from four public feeds/schedules."""
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlencode
import requests
from icalendar import Calendar, Event
ROOT = Path(__file__).parent
TZ = ZoneInfo("Europe/Zurich")
NOW = datetime.now(timezone.utc)
URLS = {
    "FC Lerchenfeld 3. Liga": "https://matchcenter.fvbj-afbj.ch/portaldata/1/nisrd/WebService/verein/calendar.asmx/Team?" + urlencode({"v":"1448","t":"49734","sp":"de","calName":"FC Lerchenfeld - 3. Liga","format":"ics"}),
    "FC Lerchenfeld Senioren 30+": "https://matchcenter.fvbj-afbj.ch/portaldata/1/nisrd/WebService/verein/calendar.asmx/Team?" + urlencode({"v":"1448","t":"37420","sp":"de","calName":"FC Lerchenfeld - Senioren 30+","format":"ics"}),
    "BSC Young Boys": "https://www.google.com/calendar/ical/fsnfah323pa6cch79425pp8ujo%40group.calendar.google.com/private-8f9335f1cf001a807d3de6bdff76c7c1/basic.ics",
}
out = Calendar()
for k,v in [("prodid","-//Nadja Sportkalender//DE"),("version","2.0"),("calscale","GREGORIAN"),("method","PUBLISH"),("X-WR-CALNAME","Nadja Sportkalender: Lerchenfeld, YB, Ski"),("X-WR-TIMEZONE","Europe/Zurich")]:
    out.add(k,v)

def put(summary, start, end, uid, desc="", location=""):
    if not start or not end: return
    e=Event()
    for k,v in [("uid",uid),("summary",summary),("dtstart",start),("dtend",end),("dtstamp",NOW),("description",desc)]:
        e.add(k,v)
    if location: e.add("location",location)
    out.add_component(e)

def read_existing():
    result={}
    dest=ROOT/"nadja.ics"
    if dest.exists():
        try:
            for e in Calendar.from_ical(dest.read_bytes()).walk("VEVENT"):
                uid=str(e.get("uid",""))
                for key in URLS:
                    if uid.startswith("nadja-"+str(list(URLS).index(key))+"-"):
                        result.setdefault(key,[]).append(e)
        except Exception as ex: print("Existing calendar unreadable:",ex)
    return result

backup=read_existing()
for index,(name,url) in enumerate(URLS.items()):
    events_added=0
    try:
        resp=requests.get(url,timeout=35,headers={"User-Agent":"Mozilla/5.0 (Sportkalender subscription)"})
        resp.raise_for_status()
        source=Calendar.from_ical(resp.content)
        evs=list(source.walk("VEVENT"))
        if not evs: raise ValueError("feed contains no VEVENT entries")
        for original in evs:
            try:
                start=original.decoded("dtstart")
                end=original.decoded("dtend") if original.get("dtend") else None
                if isinstance(start,datetime):
                    if start.tzinfo is None: start=start.replace(tzinfo=TZ)
                    if start.astimezone(timezone.utc)<NOW-timedelta(days=14): continue
                    if end is None: end=start+timedelta(hours=2)
                else:
                    if start < NOW.date()-timedelta(days=14): continue
                    if end is None: end=start+timedelta(days=1)
                if isinstance(end,datetime) and end.tzinfo is None: end=end.replace(tzinfo=TZ)
                uid="nadja-"+str(index)+"-"+str(original.get("uid",events_added)).replace("@","-at-")+"@bzenger92"
                summary=str(original.get("summary","Spiel"))
                put(("⚽ "+name+": " if index < 2 else "🟡 YB: ")+summary,start,end,uid,
                    str(original.get("description",""))+"\nQuelle: "+name,
                    str(original.get("location","")))
                events_added+=1
            except Exception as exc: print(name,"skip malformed event",exc)
        if not events_added: raise ValueError("no upcoming events")
        print(name,events_added)
    except Exception as exc:
        print("WARNING",name,exc)
        for e in backup.get(name,[]):
            out.add_component(e)
        print("Retained previous events",len(backup.get(name,[])))

# Ski: all men's disciplines (existing schedule) + only women's slalom.
for line in (ROOT/"ski.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip():continue
    raw, discipline, venue = line.split("|",2)
    d=datetime.strptime(raw,"%Y%m%d").date()
    start=datetime(d.year,d.month,d.day,17 if venue in ("Schladming","Madonna di Campiglio") else 11 if discipline in ("Abfahrt","Super-G") else 10,30 if venue in ("Schladming","Madonna di Campiglio") else 0,tzinfo=TZ)
    duration=timedelta(hours=2 if discipline in ("Abfahrt","Super-G") else 4)
    put("⛷ Ski Männer: "+discipline+" – "+venue+" [Zeit vorläufig]",start,start+duration,
        "nadja-ski-men-"+raw+"-"+discipline.replace(" ","-")+"@bzenger92",
        "Vorläufige Schweizer Zeit, nicht bestätigte Startzeit. Weltcup 2026/27; Terminänderungen bei Ski werden noch nicht automatisch synchronisiert.")
for line in (ROOT/"ski_frauen_slalom.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip():continue
    raw,venue=line.split("|",1)
    d=datetime.strptime(raw,"%Y%m%d").date()
    late=venue=="Flachau"
    start=datetime(d.year,d.month,d.day,17 if late else 10,30 if late else 0,tzinfo=TZ)
    put("⛷ Ski Frauen: Slalom – "+venue+" [Zeit vorläufig]",start,start+timedelta(hours=4),
        "nadja-ski-women-slalom-"+raw+"@bzenger92",
        "Vorläufige Schweizer Zeit, nicht bestätigte Startzeit. Nur Frauen-Slalom. Rennverschiebungen bei Ski werden derzeit noch nicht automatisch synchronisiert.")

dest=ROOT/"nadja.ics"
# Never replace a populated calendar with an empty one.
if len(out.walk("VEVENT")) < 1: raise RuntimeError("calendar has no entries")
dest.write_bytes(out.to_ical())
print("Nadja calendar generated:",len(out.walk("VEVENT")),"events")
