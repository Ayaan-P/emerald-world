#!/usr/bin/env python3
"""Compile a small, inert room-and-link blueprint into cave proposal JSON.

This is deterministic geometry, not an LLM client. Its output may be checked
and exported with export_generated_cave.py for offline or shared cave use.
"""
import argparse
import json
from pathlib import Path
import sys

MAX_INPUT = 16384


def proposal_from_blueprint(doc):
    keys = {'rooms', 'links', 'entrance_room', 'exit_room'}
    if type(doc) is not dict or set(doc) != keys:
        raise ValueError('expected rooms, links, entrance_room and exit_room')
    rooms, links = doc['rooms'], doc['links']
    if type(rooms) is not list or not 1 <= len(rooms) <= 24:
        raise ValueError('rooms must contain 1 to 24 rectangles')
    if type(links) is not list or len(links) > 64:
        raise ValueError('links must be a list of at most 64 pairs')
    centers = []
    grid = [['#'] * 31 for _ in range(31)]
    for room in rooms:
        if (type(room) is not list or len(room) != 4
                or any(type(v) is not int for v in room)):
            raise ValueError('each room must be [x,y,width,height] integers')
        x, y, w, h = room
        if w < 2 or h < 2 or x < 1 or y < 1 or x + w > 30 or y + h > 30:
            raise ValueError('room rectangle must fit inside the perimeter')
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                grid[yy][xx] = '.'
        centers.append((x + (w - 1) // 2, y + (h - 1) // 2))
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
        while x != tx:
            grid[y][x] = '.'
            x += 1 if tx > x else -1
        while y != ty:
            grid[y][x] = '.'
            y += 1 if ty > y else -1
        grid[y][x] = '.'
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
    corridor(centers[exit_room], (29, 28))
    grid[29][29] = '.'
    return {'rows': [''.join(row) for row in grid], 'spawn': [1, 1], 'exit': [29, 29]}


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
