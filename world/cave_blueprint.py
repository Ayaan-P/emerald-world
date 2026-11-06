#!/usr/bin/env python3
"""Compile a small, inert room-and-link blueprint into cave proposal JSON.

This is deterministic geometry, not an LLM client. Its output may be checked
and exported with export_generated_cave.py for offline or shared cave use.
"""
import argparse
import json
import hashlib
from pathlib import Path
import sys

MAX_INPUT = 16384


def proposal_from_blueprint(doc, *, side=31):
    if type(side) is not int or side not in (31, 63, 127):
        raise ValueError('unsupported cave size')
    keys = {'rooms', 'links', 'entrance_room', 'exit_room'}
    if type(doc) is not dict or not keys <= set(doc) or set(doc) - keys - {'style', 'seed', 'corridor_width'}:
        raise ValueError('invalid blueprint keys')
    style, seed, width = doc.get('style', 'rooms'), doc.get('seed', 0), doc.get('corridor_width', 1)
    if type(style) is not str or style not in ('rooms', 'rounded', 'organic', 'maze'):
        raise ValueError('invalid style')
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if type(width) is not int or width not in (1, 2, 3):
        raise ValueError('corridor_width must be 1, 2 or 3')
    rooms, links = doc['rooms'], doc['links']
    if type(rooms) is not list or not 1 <= len(rooms) <= 24:
        raise ValueError('rooms must contain 1 to 24 rectangles')
    if type(links) is not list or len(links) > 64:
        raise ValueError('links must be a list of at most 64 pairs')
    centers = []
    grid = [['#'] * side for _ in range(side)]
    for room_id, room in enumerate(rooms):
        if (type(room) is not list or len(room) != 4
                or any(type(v) is not int for v in room)):
            raise ValueError('each room must be [x,y,width,height] integers')
        x, y, w, h = room
        if w < 2 or h < 2 or x < 1 or y < 1 or x + w > side - 1 or y + h > side - 1:
            raise ValueError('room rectangle must fit inside the perimeter')
        cx, cy = x + (w - 1) // 2, y + (h - 1) // 2
        centers.append((cx, cy))
        if style == 'maze':
            # Stable across Python versions and independent of process RNG.
            step = 0
            start = (x, y)
            stack, visited = [start], {start}
            grid[y][x] = '.'
            while stack:
                px, py = stack[-1]
                choices = [(px + dx, py + dy) for dx, dy in ((0,-2),(2,0),(0,2),(-2,0))
                           if x <= px + dx < x + w and y <= py + dy < y + h
                           and (px + dx, py + dy) not in visited]
                if not choices:
                    stack.pop()
                    continue
                digest = hashlib.sha256(f'{seed}:{room_id}:{step}:{px}:{py}'.encode('ascii')).digest()
                step += 1
                nx, ny = choices[int.from_bytes(digest[:4], 'big') % len(choices)]
                grid[(py + ny)//2][(px + nx)//2] = '.'
                grid[ny][nx] = '.'
                visited.add((nx, ny))
                stack.append((nx, ny))
            for xx in range(x, cx + 1): grid[y][xx] = '.'
            for yy in range(y, cy + 1): grid[yy][cx] = '.'
        else:
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    if style == 'rooms':
                        grid[yy][xx] = '.'
                        continue
                    dx, dy = 2 * (xx - x) + 1 - w, 2 * (yy - y) + 1 - h
                    radius = dx * dx * h * h + dy * dy * w * w
                    if radius > w * w * h * h:
                        continue
                    if style == 'organic' and xx != cx and yy != cy and radius * 2 > w * w * h * h:
                        token = f'{seed}:{room_id}:{xx}:{yy}'.encode('ascii')
                        if hashlib.sha256(token).digest()[0] < 80:
                            continue
                    grid[yy][xx] = '.'
            grid[cy][cx] = '.'
    def room_index(value):
        if type(value) is not int or not 0 <= value < len(rooms):
            raise ValueError('room index out of range')
        return value
    entrance = room_index(doc['entrance_room'])
    exit_room = room_index(doc['exit_room'])
    graph = [set() for _ in rooms]
    def corridor(a, b):
        x, y = a
        tx, ty = b
        def brush(px, py):
            for oy in range(-(width // 2), (width + 1) // 2):
                for ox in range(-(width // 2), (width + 1) // 2):
                    if 1 <= px + ox <= side - 2 and 1 <= py + oy <= side - 2:
                        grid[py + oy][px + ox] = '.'
        while x != tx:
            brush(x, y)
            x += 1 if tx > x else -1
        while y != ty:
            brush(x, y)
            y += 1 if ty > y else -1
        brush(x, y)
    for link in links:
        if type(link) is not list or len(link) != 2:
            raise ValueError('each link must contain two room indices')
        a, b = map(room_index, link)
        if a == b:
            raise ValueError('a link must connect different rooms')
        graph[a].add(b)
        graph[b].add(a)
        corridor(centers[a], centers[b])
    reachable = {entrance}
    stack = [entrance]
    while stack:
        for neighbor in graph[stack.pop()]:
            if neighbor not in reachable:
                reachable.add(neighbor)
                stack.append(neighbor)
    if len(reachable) != len(rooms):
        raise ValueError('all rooms must be connected by links')
    corridor((1, 1), centers[entrance])
    corridor(centers[exit_room], (side - 2, side - 3))
    grid[side - 2][side - 2] = '.'
    # Remove isolated pixels caused by the organic edge, without changing the
    # connected room graph or the required entrance and exit.
    seen, stack = {(1, 1)}, [(1, 1)]
    while stack:
        px, py = stack.pop()
        for nx, ny in ((px,py-1),(px+1,py),(px,py+1),(px-1,py)):
            if 0 <= nx < side and 0 <= ny < side and grid[ny][nx] == '.' and (nx,ny) not in seen:
                seen.add((nx,ny)); stack.append((nx,ny))
    for yy in range(side):
        for xx in range(side):
            if grid[yy][xx] == '.' and (xx,yy) not in seen:
                grid[yy][xx] = '#'
    return {'rows': [''.join(row) for row in grid], 'spawn': [1, 1], 'exit': [side - 2, side - 2]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('blueprint', type=Path)
    args = parser.parse_args()
    try:
        with args.blueprint.open('rb') as stream:
            raw = stream.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError('blueprint exceeds size limit')
        result = proposal_from_blueprint(json.loads(raw))
        json.dump(result, sys.stdout, separators=(',', ':'))
        print()
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(1, f'Cannot compile blueprint: {error}\n')

if __name__ == '__main__':
    main()
