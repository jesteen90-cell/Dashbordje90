import json
from pathlib import Path
SRC=Path('premium_structure_shadow.json');DIR=Path('premium_structure_snapshots')
def main():
 if not SRC.exists():return
 d=json.loads(SRC.read_text());gw=int(d['gw']);DIR.mkdir(exist_ok=True);p=DIR/f'gw{gw:02d}.json'
 if p.exists():print('Premium structure snapshot already frozen',p);return
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('Frozen',p)
if __name__=='__main__':main()
