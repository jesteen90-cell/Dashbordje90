from __future__ import annotations
"""Select production captain model from frozen backtest evidence.
Safe fallback: v3 stays production until v4/v4.1 promotion gates pass.
"""
import json
from pathlib import Path
SCORE=Path('backtest/captain_v4_scorecard.json')
SHADOW=Path('captain_v4_shadow.json')
DATA=Path('data.json')

def main():
 d=json.loads(DATA.read_text())
 shadow=json.loads(SHADOW.read_text()) if SHADOW.exists() else {}
 score=json.loads(SCORE.read_text()) if SCORE.exists() else {}
 model='v3'; reason='insufficient backtest evidence'
 if score.get('v41_promote') is True:
  model='v4.1'; reason='haul-aware model passed promotion gate'
 elif score.get('v4_promote') is True or score.get('promote') is True:
  model='v4'; reason='persistent-elite model passed promotion gate'
 pick=(shadow.get({'v3':'v3_pick','v4':'v4_pick','v4.1':'v41_pick'}[model]) or {})
 # Production remains unchanged if selected shadow pick is missing.
 if not pick.get('id'):
  model='v3'; reason='selected model missing valid pick; fallback to v3'; pick=shadow.get('v3_pick') or {}
 d['captain_model_selection']={'version':'1.0','production_model':model,'reason':reason,'evaluated_gws':int(score.get('evaluated_gws') or 0),'selected_pick':pick,'promotion_flags':{'v4':bool(score.get('v4_promote') or score.get('promote')),'v41':bool(score.get('v41_promote'))}}
 # Do not mutate lineup captain flags yet; this selector is promotion-ready metadata only.
 DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 print('Captain production selector:',model,pick.get('name'),reason)
if __name__=='__main__':main()
