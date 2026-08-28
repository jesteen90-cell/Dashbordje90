"""Run the production generator once and export its in-memory projections.

Keeps premium-structure tests on exactly the same xP surface as production,
without maintaining a second projection model.
"""
import json,runpy
from pathlib import Path
ns=runpy.run_path('generate_dashboard_v3.py')
players=ns['players'];gws=ns['GWS'];weights=ns['weights'];squad=ns['squad'];bank=ns['bank']
rows=[]
for p in players:
 rows.append({'id':int(p['id']),'name':p['web_name'],'team':int(p['team']),'element_type':int(p['element_type']),'now_cost':int(p['now_cost']),'xp':{str(g):round(float(p['_x'].get(g,0)),4) for g in gws}})
out={'version':'1.0','gws':gws,'weights':{str(k):v for k,v in weights.items()},'squad_ids':[int(p['id']) for p in squad],'bank':int(bank),'players':rows}
Path('projection_cache.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('Exported production projection cache',len(rows),'players')
