from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from icalendar import Calendar, Event
ROOT = Path(__file__).parent
NOW = datetime.now(timezone.utc)
cal = Calendar()
for key, val in [('prodid','-//BZ Sportkalender Live//DE'),('version','2.0'),('calscale','GREGORIAN'),('method','PUBLISH'),('X-WR-CALNAME','Sportkalender Live | Real Madrid | Ski | Dallas Cowboys'),('X-WR-TIMEZONE','Europe/Zurich'),('X-PUBLISHED-TTL','PT12H'),('REFRESH-INTERVAL','PT12H')]:
    cal.add(key,val)
def add(summary,dt,uid,duration=timedelta(hours=3),description=''):
    e=Event()
    for k,v in [('uid',uid),('summary',summary),('dtstart',dt),('dtend',dt+duration),('dtstamp',NOW),('description',description)]:
        e.add(k,v)
    cal.add_component(e)
for line in (ROOT/'ski.txt').read_text(encoding='utf-8').splitlines():
    date, discipline, venue = line.split('|',2)
    d=datetime.strptime(date,'%Y%m%d').date()
    add('⛷ Ski Männer: '+discipline+' – '+venue,d,'ski-'+date+'-'+discipline.replace(' ','-')+'@bzenger92',timedelta(days=1),'Weltcupkalender 2026/27: Startzeit noch nicht verifiziert. Verlegungen werden nicht automatisch synchronisiert. Quelle: FIS.')
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
real=[]
for league in ('esp.1','uefa.champions','esp.copa_del_rey'):
    for season in ('2026','2027'):
        real+=fetch('https://site.api.espn.com/apis/site/v2/sports/soccer/'+league+'/teams/86/schedule?season='+season)
nfl=fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/dal/schedule?season=2026')
add_games(real,'real',set())
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
