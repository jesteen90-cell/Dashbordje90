import json
from pathlib import Path
SRC=Path('captain_v4_shadow.json'); DIR=Path('captain_snapshots')
def main():
 if not SRC.exists():return
 d=json.loads(SRC.read_text());gw=int(d['gw']);DIR.mkdir(exist_ok=True);p=DIR/f'gw{gw:02d}.json'
 if p.exists():print('Captain snapshot already frozen',p);return
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('Frozen',p)
if __name__=='__main__':main()
