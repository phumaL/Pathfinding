"""
dstar_lite.py — D* Lite incremental path replanner.
When a cell becomes blocked mid-journey, D* Lite repairs only
the part of the path that is affected, reusing the rest.
We store a simple version: when the environment changes, we
find where the old path crosses the changed cell and replan
from that point using A* with the updated grid.
"""

import heapq


def heuristic(ax, ay, bx, by):
    """Manhattan distance — the minimum steps between two points."""
    return abs(ax - bx) + abs(ay - by)


def astar(env, start_x, start_y, goal_x, goal_y):
    """
    Plain A* search from (start_x, start_y) to (goal_x, goal_y).
    Returns a list of (x, y) tuples, or [] if no path exists.
    This is the fallback planner used by D* Lite when a full
    replan is needed.
    """
    if env.is_blocked(goal_x, goal_y):
        return []

    start = (start_x, start_y)
    goal = (goal_x, goal_y)

    open_heap = []
    g_score = {start: 0}
    came_from = {}

    heapq.heappush(open_heap, (heuristic(start_x, start_y, goal_x, goal_y), 0, start))
    closed = set()

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            path = []
            node = goal
            while node != start:
                path.append(node)
                node = came_from[node]
            path.append(start)
            path.reverse()
            return path

        cx, cy = current
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = cx + dx, cy + dy
            if env.is_blocked(nx, ny):
                continue
            neighbour = (nx, ny)
            if neighbour in closed:
                continue
            new_g = g + 1
            if new_g < g_score.get(neighbour, float("inf")):
                g_score[neighbour] = new_g
                came_from[neighbour] = current
                f = new_g + heuristic(nx, ny, goal_x, goal_y)
                heapq.heappush(open_heap, (f, new_g, neighbour))

    return []


def find_first_blocked(path, env):
    """
    Walk along the path and return the index of the first cell
    that is now blocked. Returns -1 if the whole path is clear.
    """
    for i, (x, y) in enumerate(path):
        if env.is_blocked(x, y):
            return i
    return -1


def replan(env, current_pos, old_path, goal):
    """
    D* Lite incremental replan.

    How it works:
    1. Find where the old path first becomes blocked.
    2. Keep the portion of the old path before that blocked cell
       (the agent can still walk that part).
    3. Replan from the last safe position to the goal using A*.
    4. Stitch the two pieces together and return the full updated path.

    If the current position is not on the old path (e.g. the agent
    just started), we replan from current_pos directly.

    Returns a new list of (x, y) tuples, or [] if no route exists.
    """
    goal_x, goal_y = goal

    # Find where the agent is in the old path
    try:
        agent_index = old_path.index(current_pos)
    except ValueError:
        agent_index = 0

    # Only check the part of the path still ahead of the agent
    remaining = old_path[agent_index:]

    blocked_index = find_first_blocked(remaining, env)

    if blocked_index == -1:
        # Nothing is blocked — old path is still fine
        return old_path

    # The safe prefix ends just before the blocked cell
    safe_prefix = remaining[:blocked_index]

    # Replan from the last safe cell (or current pos if no safe prefix)
    if safe_prefix:
        replan_start = safe_prefix[-1]
    else:
        replan_start = current_pos

    sx, sy = replan_start
    new_suffix = astar(env, sx, sy, goal_x, goal_y)

    if not new_suffix:
        return []  # no route found at all

    # Avoid duplicating the join point
    full_path = old_path[:agent_index] + safe_prefix + new_suffix[1:]
    return full_path


def initial_plan(env, start_x, start_y, goal_x, goal_y):
    """
    Build the first path before any changes happen.
    Just delegates to A* since D* Lite and A* give the same result
    on an unchanged grid.
    """
    return astar(env, start_x, start_y, goal_x, goal_y)
