import json
from pathlib import Path
SRC=Path('chip_strategy_shadow.json'); ROOT=Path('chip_snapshots')
def main():
 if not SRC.exists():return
 d=json.loads(SRC.read_text()); ROOT.mkdir(exist_ok=True); p=ROOT/f"gw{int(d['gw']):02d}.json"
 if not p.exists():p.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('Frozen chip snapshot',p)
 else:print('Chip snapshot already frozen',p)
if __name__=='__main__':main()
