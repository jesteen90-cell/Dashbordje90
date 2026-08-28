from __future__ import annotations

import json
from pathlib import Path

PATH = Path("data.json")
SCORECARD = Path("backtest/scorecard.json")
FT_FLEX_VALUE = 0.45
BASE_DO_THRESHOLD = 1.15
CONSIDER_THRESHOLD = 0.35


def n(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def adaptive_controls():
    controls={"threshold":BASE_DO_THRESHOLD,"minutes_penalty_scale":1.0,"availability_penalty_scale":1.0,"volatility_penalty_scale":1.0};feedback={"enabled":False,"component_enabled":False,"base_threshold":BASE_DO_THRESHOLD,"effective_threshold":BASE_DO_THRESHOLD,"evaluated_gws":0,"reasons":[],"diagnostics":{}}
    if not SCORECARD.exists():return controls,feedback
    try:score=json.loads(SCORECARD.read_text())
    except:return controls,feedback
    samples=int(score.get("evaluated_gws") or 0);feedback["evaluated_gws"]=samples;feedback["diagnostics"]={k:score.get(k) for k in ("xp_mae","xp_bias","minutes_mae","minutes_bias","expected_to_play_zero_rate","captain_hit_rate","mean_captain_regret")};feedback["diagnostics"]["position_diagnostics"]=score.get("position_diagnostics") or {}
    if samples<4 or not score.get("adaptive_feedback_ready"):feedback["reasons"].append("Minst 4 ferdige frozen-snapshot GWs kreves før terskelkalibrering");return controls,feedback
    adj=0.0;bs=int(score.get("bytt_samples") or 0);ks=int(score.get("bank_samples") or 0);bw=score.get("bytt_win_rate");kw=score.get("bank_win_rate");br=n(score.get("bytt_mean_regret"));kr=n(score.get("bank_mean_regret"));coverage=n(score.get("interval_80_coverage"),.8)
    if bs>=2 and bw is not None:
        if n(bw)<.45:adj+=.16;feedback["reasons"].append("Historiske BYTT-beslutninger har vunnet for sjelden")
        elif n(bw)>.70:adj-=.08
        if br>1:adj+=.08
    if ks>=2 and kw is not None:
        if n(kw)<.45 or kr>1:adj-=.12
        elif n(kw)>.75 and kr<=0:adj+=.04
    if coverage<.65:adj+=.07
    controls["threshold"]=max(.90,min(1.45,BASE_DO_THRESHOLD+adj));feedback.update({"enabled":True,"effective_threshold":round(controls["threshold"],2),"adjustment":round(controls["threshold"]-BASE_DO_THRESHOLD,2),"bytt_samples":bs,"bank_samples":ks,"interval_80_coverage":score.get("interval_80_coverage")})
    if samples>=6 and score.get("component_feedback_ready"):
        feedback["component_enabled"]=True;mb=n(score.get("minutes_bias"));zr=n(score.get("expected_to_play_zero_rate"));mm=n(score.get("minutes_mae"))
        if mb<-8:controls["minutes_penalty_scale"]=1.18
        elif mb>8 and mm<24:controls["minutes_penalty_scale"]=.92
        if zr>.07:controls["availability_penalty_scale"]=1.18
        elif zr<.025 and mm<20:controls["availability_penalty_scale"]=.95
        if coverage<.60:controls["volatility_penalty_scale"]=1.12
    feedback["controls"]={k:round(v,3) for k,v in controls.items()};return controls,feedback

def risk_penalty(player,controls):
    availability=max(0,min(1,n(player.get("availability"),1)));xmins=max(0,min(90,n(player.get("expected_minutes"),90)));vol=max(0,n(player.get("volatility"),0));return max(0,.92-availability)*3*controls["availability_penalty_scale"]+max(0,70-xmins)/70*.85*controls["minutes_penalty_scale"]+max(0,vol-1.05)*.30*controls["volatility_penalty_scale"]
def candidate_quality(c,controls):
    pair=(c.get("pairs") or [{}])[0];o,i=pair.get("out") or {},pair.get("in") or {};h,s=n(c.get("horizon_gain")),n(c.get("short_gain"));frag=max(0,risk_penalty(i,controls)-risk_penalty(o,controls));score=h-FT_FLEX_VALUE-frag+max(-.25,min(.35,s*.07));reasons=[]
    if frag>.20:reasons.append("Innkommende spiller har mer usikre minutter/tilgjengelighet")
    if s<0:reasons.append("Byttet taper forventede poeng de neste tre rundene")
    if h<=FT_FLEX_VALUE:reasons.append("Langsiktig gevinst dekker ikke fleksibilitetsverdien")
    if n(i.get("expected_minutes"),90)<65:reasons.append("For lavt forventet minuttgrunnlag")
    if n(i.get("availability"),1)<.85:reasons.append("Tilgjengeligheten er for usikker")
    status="GJØR DET" if score>=controls["threshold"] and not reasons else "VURDERES" if score>=CONSIDER_THRESHOLD else "SVAK";return round(score,2),status,reasons
def reorder_bench(bench):
    out=[p for p in bench if p.get("position")!="GK"];gk=[p for p in bench if p.get("position")=="GK"];out.sort(key=lambda p:(n(p.get("availability"),1),n(p.get("expected_minutes")),n(p.get("xp"))),reverse=True);gk.sort(key=lambda p:n(p.get("xp")),reverse=True);return out+gk
def hard_gate_first_move(data,controls):
    changes=(data.get("comparison") or {}).get("changes") or [];gain=n((data.get("optimizer") or {}).get("weighted_gain"));reasons=[]
    if not changes:return False,["Ingen foreslått overgang i første trekk"]
    for c in changes:
        i=c.get("in") or {}
        if n(i.get("availability"),1)<.85:reasons.append(f"{i.get('name','Spilleren')} har usikker tilgjengelighet")
        if n(i.get("expected_minutes"),90)<65:reasons.append(f"{i.get('name','Spilleren')} har for lavt forventet minuttall")
    if gain<controls["threshold"]:reasons.append(f"Netto modellfordel {gain:.2f} er under beslutningsterskelen {controls['threshold']:.2f}")
    return not reasons,reasons
def choose_safer_vice(lineup):
    cap=next((p for p in lineup if p.get("captain")),None);cand=[p for p in lineup if not p.get("captain")]
    if not cand:return
    best=max(cand,key=lambda p:n(p.get("xp"))*(.72+.18*n(p.get("availability"),1)+.10*n(p.get("expected_minutes"),90)/90))
    for p in lineup:p["vice"]=p is best
    if cap:cap["vice"]=False

def captain_comparison(lineup):
    rows=[]
    for p in lineup:
        xp=n(p.get("xp"));mins=n(p.get("expected_minutes"),90);avail=n(p.get("availability"),1);ceiling=max(xp,n(p.get("xp_high"),xp));score=xp*.70+ceiling*.20+(mins/90)*.06+avail*.04
        # Long-run production fields are passed through for Captain v4 shadow.
        rows.append({"id":p.get("id"),"name":p.get("name"),"team":p.get("team"),"xp":round(xp,2),"ceiling":round(ceiling,2),"expected_minutes":round(mins,0),"availability":round(avail,2),"score":round(score,3),"captain":bool(p.get("captain")),"vice":bool(p.get("vice")),"season_minutes":p.get("season_minutes"),"season_points":p.get("season_points"),"season_xg":p.get("season_xg"),"season_xa":p.get("season_xa"),"season_goals":p.get("season_goals")})
    return sorted(rows,key=lambda x:x["score"],reverse=True)[:5]
def explain_decision(data,approved,blockers,controls):
    cmp=data.get("comparison") or {};changes=cmp.get("changes") or [];gain=n((data.get("optimizer") or {}).get("weighted_gain"));best=(data.get("candidates") or [{}])[0];short,horizon=n(best.get("short_gain")),n(best.get("horizon_gain"));reasons=[]
    if changes:reasons.append("Første trekk modellen vurderer er "+", ".join(f"{(c.get('out') or {}).get('name','?')} → {(c.get('in') or {}).get('name','?')}" for c in changes)+".")
    reasons.append(f"Estimert gevinst: {short:+.2f} xP neste 3 GW og {horizon:+.2f} xP over planhorisonten.");reasons.append(f"Gratisbytte-fleksibilitet verdsettes til {FT_FLEX_VALUE:.2f} xP; robust BYTT-terskel er {controls['threshold']:.2f}.");reasons.extend(blockers[:2] if blockers else ["Ingen harde minutt- eller tilgjengelighetsblokker stopper trekket."]);dist=round(controls["threshold"]-gain,2);trigger="Anbefalingen er robust nok nå." if approved else f"Trenger omtrent {max(0,dist):.2f} mer netto modellfordel, eller at en blokkering forsvinner, før BYTT godkjennes.";return {"decision":"BYTT" if approved else "BANK","why":reasons[:5],"weighted_gain":round(gain,2),"threshold":round(controls["threshold"],2),"distance_to_switch":max(0,dist),"switch_trigger":trigger,"horizon_3gw":round(short,2),"horizon_plan":round(horizon,2)}
def main():
    data=json.loads(PATH.read_text());controls,feedback=adaptive_controls();candidates=data.get("candidates") or []
    for c in candidates:c["edge"],c["status"],c["gate_misses"]=(*candidate_quality(c,controls)[:2],list(dict.fromkeys(candidate_quality(c,controls)[2]+list(c.get("gate_misses") or [])))[:3])
    candidates.sort(key=lambda c:(n(c.get("edge")),n(c.get("horizon_gain"))),reverse=True);strong=[c for c in candidates if c.get("status")!="SVAK"];data["candidates"]=strong[:6] if strong else candidates[:4];data["bench"]=reorder_bench(data.get("bench") or [])
    for lineup in [data.get("lineup") or [],(data.get("comparison") or {}).get("current_xi") or [],(data.get("comparison") or {}).get("transfer_xi") or []]:choose_safer_vice(lineup)
    approved,blockers=hard_gate_first_move(data,controls);comparison=data.get("comparison") or {};comparison["status"]="GJØR DET" if approved else "BANK" if comparison.get("changes") else comparison.get("status");data["comparison"]=comparison;data["headline"]="GJØR BYTTET" if approved else "SPAR BYTTET";data.setdefault("recommendation",{})["transfers"]=(comparison.get("changes") or []) if approved else [];lineup=comparison.get("transfer_xi") if approved else comparison.get("current_xi");lineup=lineup or data.get("lineup") or [];data["captain_comparison"]=captain_comparison(lineup);data["decision_explanation"]=explain_decision(data,approved,blockers,controls);data["decision_layer"]={"version":"4.3-component-adaptive","approved_first_move":approved,"threshold":round(controls["threshold"],2),"base_threshold":BASE_DO_THRESHOLD,"controls":{k:round(v,3) for k,v in controls.items()},"feedback":feedback,"explainability":True,"captain_comparison":True,"backtest_adaptive":True,"component_adaptive":True};PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
