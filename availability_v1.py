"""Gameweek-aware player availability for FPL projections.

FPL's chance_of_playing_next_round is a next-GW signal, not a six-week
forecast. This module keeps the current flag strong for the immediate round
while allowing uncertainty to decay cautiously deeper into the planning
horizon. Permanent/unavailable status stays at zero.
"""
from __future__ import annotations


def clamp(x,a=0.0,b=1.0):
    return max(a,min(b,float(x)))


def next_round_availability(player):
    status=str(player.get('status') or 'a')
    if status=='u':
        return 0.0
    chance=player.get('chance_of_playing_next_round')
    if chance is not None:
        try:
            return clamp(float(chance)/100.0)
        except Exception:
            pass
    if status=='s':
        return 0.0
    if status in ('i','d'):
        return 0.55
    return 1.0


def availability_for_gw(player,target_gw,gw):
    """Return availability in [0,1] for a projected GW.

    Injury/doubt flags recover toward 1 with a conservative 0.70 persistence
    of today's absence each future GW. Suspensions recover faster after the
    immediate round because many are one-match bans, while still retaining
    uncertainty. Players marked unavailable ('u') never auto-recover.
    """
    status=str(player.get('status') or 'a')
    if status=='u':
        return 0.0
    offset=max(0,int(gw)-int(target_gw))
    base=next_round_availability(player)
    if offset==0:
        return base
    if status=='s':
        recovery=(0.65,0.85,0.94,0.98,1.0)
        return recovery[min(offset-1,len(recovery)-1)]
    if base>=0.999:
        return 1.0
    absence=1.0-base
    return clamp(1.0-absence*(0.70**offset))
