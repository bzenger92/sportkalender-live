from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from icalendar import Calendar, Event
ROOT = Path(__file__).parent
NOW = datetime.now(timezone.utc)
cal = Calendar()
for key, val in [('prodid','-//BZ Sportkalender Live//DE'),('version','2.0'),('calscale','GREGORIAN'),('method','PUBLISH'),('X-WR-CALNAME','Sportkalender Live | Real Madrid | Ski | Dallas Cowboys'),('X-WR-TIMEZONE','Europe/Zurich')]:
    cal.add(key,val)
def add(summary,dt,uid,duration=timedelta(hours=3),description=''):
    e=Event()
    for k,v in [('uid',uid),('summary',summary),('dtstart',dt),('dtend',dt+duration),('dtstamp',NOW),('description',description)]:
        e.add(k,v)
    cal.add_component(e)
for line in (ROOT/'ski.txt').read_text(encoding='utf-8').splitlines():
    date, discipline, venue = line.split('|',2)
    d=datetime.strptime(date,'%Y%m%d').date()
    # Swiss viewing times: confirmed for Soelden, explicitly provisional otherwise.
    confirmed = (date == '20261025' and venue == 'Sölden')
    if confirmed:
        start_hour, start_minute, duration = 10, 0, timedelta(hours=4)
    elif venue in ('Schladming', 'Madonna di Campiglio'):
        start_hour, start_minute, duration = 17, 30, timedelta(hours=4)
    elif discipline in ('Abfahrt', 'Super-G'):
        start_hour, start_minute, duration = 11, 0, timedelta(hours=2)
    else:
        start_hour, start_minute, duration = 10, 0, timedelta(hours=4)
    dt = datetime(d.year,d.month,d.day,start_hour,start_minute,tzinfo=ZoneInfo('Europe/Zurich'))
    description = ('Bestätigt: 1. Lauf 10:00, 2. Lauf 13:00. Quelle: soelden.com.' if confirmed else
        'PROVISORISCHES Zeitfenster, KEINE bestätigte Startzeit! Bitte vor dem Rennen die FIS-Startliste prüfen. Zeitangabe in Europe/Zurich.')
    prefix = '' if confirmed else '[Zeit vorläufig] '
    add('⛷ '+prefix+'Ski Männer: '+discipline+' – '+venue,dt,'ski-'+date+'-'+discipline.replace(' ','-')+'@bzenger92',duration,description)
def fetch(url):
    try:
        r=requests.get(url,timeout=20,headers={'User-Agent':'Sportkalender/1.0'})
        r.raise_for_status()
        return r.json().get('events',[])
    except Exception as exc:
        print('Abruf fehlgeschlagen',str(exc))
        return []
def add_games(items,category,seen):
    for game in items:
        try:
            dt=datetime.fromisoformat(game['date'].replace('Z','+00:00'))
            if dt < NOW-timedelta(days=2): continue
            comp=game['competitions'][0]['competitors']
            home=next(x for x in comp if x['homeAway']=='home')['team']['displayName']
            away=next(x for x in comp if x['homeAway']=='away')['team']['displayName']
            ident=str(game['id'])
            if ident in seen:continue
            seen.add(ident)
            add(('⚽ ' if category=='real' else '🏈 ')+home+' – '+away,dt,category+'-'+ident+'@bzenger92',timedelta(hours=3,minutes=30) if category=='nfl' else timedelta(hours=2,minutes=15),'Spielplan automatisch von ESPN abgefragt. Zeitangaben in Outlook auf Europe/Zurich umgerechnet.')
        except (KeyError,StopIteration,ValueError,TypeError) as ex:
            print('Skip event',str(ex))
# Public Real Madrid fixture subscription: independent of ESPN's truncated team API.
REAL_FEED = 'https://www.google.com/calendar/ical/strl8p7aja3asegdktmb62h4f4%40group.calendar.google.com/public/basic.ics'
try:
    response=requests.get(REAL_FEED,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    madrid_calendar=Calendar.from_ical(response.content)
    count=0
    for event in madrid_calendar.walk('VEVENT'):
        begin=event.decoded('dtstart')
        end=event.decoded('dtend') if event.get('dtend') else None
        if isinstance(begin,datetime):
            begin=begin.replace(tzinfo=ZoneInfo('Europe/Zurich')) if begin.tzinfo is None else begin
            if begin < NOW-timedelta(days=2): continue
        else:
            if begin < NOW.date()-timedelta(days=2): continue
        duration=(end-begin) if end is not None else (timedelta(hours=2,minutes=15) if isinstance(begin,datetime) else timedelta(days=1))
        if duration <= timedelta(0): duration=timedelta(hours=2,minutes=15)
        uid='real-feed-'+str(event.get('uid','')).replace('@','-at-')+'@bzenger92'
        desc='Real Madrid – externer abonnierter Spielplan. Nicht endgültig terminierte Spiele können vorläufige Uhrzeiten haben.'
        add('⚽ '+str(event.get('summary','Real Madrid')),begin,uid,duration,desc)
        count+=1
    print('Real Madrid Feed:',count,'Termine')
except Exception as exc:
    print('Real Madrid Kalenderabruf fehlgeschlagen:',str(exc))
nfl=fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule?season=2026')
add_games(nfl,'nfl',set())
# Keep latest known football fixtures if upstream temporarily fails
target=ROOT/'sportkalender.ics'
if target.exists():
    old=Calendar.from_ical(target.read_bytes())
    current={str(e.get('uid')) for e in cal.walk('VEVENT')}
    present={('real' if str(e.get('uid')).startswith('real-') else 'nfl') for e in cal.walk('VEVENT')}
    for e in old.walk('VEVENT'):
        uid=str(e.get('uid',''))
        if uid in current or not (uid.startswith('real-') or uid.startswith('nfl-')): continue
        kind='real' if uid.startswith('real-') else 'nfl'
        if kind not in present:cal.add_component(e)
target.write_bytes(cal.to_ical())
print('Geschrieben:',target,'Anzahl',len(cal.walk('VEVENT')))
