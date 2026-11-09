"""Bounded exact tile witnesses from matched native mount clients.

This validates sequence continuity, not collision honesty or anti-cheat. Never
interpolate between samples: turns and missed writes must not invent visits.
"""
import re


def decode(raw, previous, state, old_mount, mount, fresh):
    if raw not in ('.','!') and not re.fullmatch(r'[0-9]{1,5},[0-9]{1,5}(?:/[0-9]{1,5},[0-9]{1,5}){0,15}',raw):
        raise ValueError('invalid mount trail')
    if not mount[0]:
        if raw!='.':raise ValueError('unmounted trail')
        return [],False
    if raw=='!':return [],True
    points=[] if raw=='.' else [list(map(int,p.split(','))) for p in raw.split('/')]
    if any(any(v>32767 for v in p) for p in points):raise ValueError('invalid trail coordinate')
    continuing=previous is not None and previous[6] and previous[:2]==state[:2] and old_mount==mount and fresh
    if not continuing:
        return [], bool(old_mount==mount and previous is not None or points and points!=[state[2:4]])
    last=previous[2:4]
    for point in points:
        if abs(point[0]-last[0])+abs(point[1]-last[1])!=1:return [],True
        last=point
    if last!=state[2:4]:return [],True
    return [state[:2]+p for p in points],False
