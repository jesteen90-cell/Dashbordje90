"""Convert premium-structure backtest evidence into a bounded decision prior.

This never promotes a named player. It only allows a small position/price-band
prior after enough fully evaluated frozen windows. The prior is deliberately too
small to rescue a materially bad transfer; it is intended to break close calls.
"""
from __future__ import annotations
import json
from pathlib import Path

SCORE=Path('backtest/premium_structure_scorecard.json')
OUT=Path('backtest/premium_structure_params.json')
MIN_WINDOWS=6
MIN_WIN_SHARE=.50
MAX_MEAN_REGRET=2.5
BIAS=.16

def main():
 data={}
 if SCORE.exists():
  try:data=json.loads(SCORE.read_text(encoding='utf-8'))
  except Exception:data={}
 n=int(data.get('evaluated_windows') or 0);wins=data.get('winner_counts') or {}
 total=max(1,sum(int(v or 0) for v in wins.values()))
 shares={k:float(v or 0)/total for k,v in wins.items()}
 accuracy=data.get('verdict_accuracy');regret=data.get('mean_regret')
 promoted='none';reason='insufficient evaluated windows'
 if n>=MIN_WINDOWS:
  ranked=sorted((('premium_forward',shares.get('premium_forward',0)),('premium_midfielder',shares.get('premium_midfielder',0)),('current_structure',shares.get('current_structure',0))),key=lambda x:x[1],reverse=True)
  best,share=ranked[0];second=ranked[1][1]
  stable=share>=MIN_WIN_SHARE and share-second>=.12 and (regret is None or float(regret)<=MAX_MEAN_REGRET)
  if stable and best in ('premium_forward','premium_midfielder'):
   promoted=best;reason=f'{best} has stable realized edge across frozen windows'
  else:reason='no premium structure has a stable realized edge'
 payload={'version':'1.0','evaluated_windows':n,'winner_shares':shares,'verdict_accuracy':accuracy,'mean_regret':regret,'promoted_structure':promoted,'enabled':promoted!='none','candidate_bias':BIAS if promoted!='none' else 0.0,'min_windows':MIN_WINDOWS,'reason':reason}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');print('Premium feedback',promoted,'n=',n,shares)
if __name__=='__main__':main()
