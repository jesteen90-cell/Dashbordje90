#!/usr/bin/env python3
import argparse,json
from datetime import datetime,timezone

def ids(xs):return {int(x.get('id')) for x in (xs or []) if x.get('id') is not None}
def cap(d):
 for p in d.get('lineup',[]):
  if p.get('captain'):return p.get('name')
 return None
def transfers(d):
 out=[]
 for t in d.get('recommendation',{}).get('transfers',[]):out.append(f"{t.get('out',{}).get('name')} -> {t.get('in',{}).get('name')}")
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('production');ap.add_argument('v2');ap.add_argument('--out',default='shadow_v2_report.json');a=ap.parse_args();p=json.load(open(a.production));v=json.load(open(a.v2));px=ids(p.get('lineup'));vx=ids(v.get('lineup'))
 report={'generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'gw':v.get('gw'),'production_model':p.get('model_version','legacy'),'v2_model':v.get('model_version'),'same_headline':p.get('headline')==v.get('headline'),'production_headline':p.get('headline'),'v2_headline':v.get('headline'),'production_transfers':transfers(p),'v2_transfers':transfers(v),'same_captain':cap(p)==cap(v),'production_captain':cap(p),'v2_captain':cap(v),'xi_overlap':len(px&vx),'xi_changes':{'out':sorted(px-vx),'in':sorted(vx-px)},'production_edge':p.get('recommendation',{}).get('edge'),'v2_edge':v.get('recommendation',{}).get('edge'),'deadline_match':p.get('deadline_time')==v.get('deadline_time')}
 json.dump(report,open(a.out,'w'),indent=2,ensure_ascii=False);print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
