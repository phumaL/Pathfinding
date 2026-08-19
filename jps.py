"""
jps.py — Jump Point Search on a 4-directional grid.
JPS is A* with an extra step: instead of expanding every cell,
it 'jumps' ahead in a direction until it hits a wall, the goal,
or a cell where a better path can branch off (a jump point).
This skips many cells that A* would expand unnecessarily.
"""

import heapq


def heuristic(ax, ay, bx, by):
    """
    Estimate the distance from (ax,ay) to (bx,by).
    Manhattan distance is exact for 4-directional movement.
    """
    return abs(ax - bx) + abs(ay - by)


def _simple_scan(env, x, y, dx, dy, goal_x, goal_y):
    """
    Scan from (x,y) in direction (dx,dy), one step at a time.
    Return the first interesting cell found (goal or forced neighbour),
    or None if we hit a wall first.
    Used as a short sub-scan inside the main jump function.
    """
    cx, cy = x + dx, y + dy
    while not env.is_blocked(cx, cy):
        if cx == goal_x and cy == goal_y:
            return (cx, cy)
        if dx != 0:  # horizontal sub-scan: look for forced neighbours above/below
            prev_x = cx - dx
            if env.is_blocked(prev_x, cy - 1) and not env.is_blocked(cx, cy - 1):
                return (cx, cy)
            if env.is_blocked(prev_x, cy + 1) and not env.is_blocked(cx, cy + 1):
                return (cx, cy)
        else:  # vertical sub-scan: look for forced neighbours left/right
            prev_y = cy - dy
            if env.is_blocked(cx - 1, prev_y) and not env.is_blocked(cx - 1, cy):
                return (cx, cy)
            if env.is_blocked(cx + 1, prev_y) and not env.is_blocked(cx + 1, cy):
                return (cx, cy)
        cx, cy = cx + dx, cy + dy
    return None


def jump(env, x, y, dx, dy, goal_x, goal_y):
    """
    Walk in direction (dx,dy) starting one step from (x,y).
    Stop and return the current cell when any of these happen:
      - we reach the goal
      - the cell next to us forces a detour (forced neighbour)
      - a perpendicular scan from here reaches the goal or a forced neighbour
    Return None if we hit a wall before finding anything interesting.
    """
    cx, cy = x + dx, y + dy
    while not env.is_blocked(cx, cy):
        if cx == goal_x and cy == goal_y:
            return (cx, cy)

        if dx != 0:  # moving horizontally
            prev_x = cx - dx
            # Forced neighbour: cell diagonal to direction, reachable only via here
            if env.is_blocked(prev_x, cy - 1) and not env.is_blocked(cx, cy - 1):
                return (cx, cy)
            if env.is_blocked(prev_x, cy + 1) and not env.is_blocked(cx, cy + 1):
                return (cx, cy)
            # Perpendicular sub-scan: can we reach goal/forced-cell by going up or down?
            if (_simple_scan(env, cx, cy, 0,  1, goal_x, goal_y) or
                    _simple_scan(env, cx, cy, 0, -1, goal_x, goal_y)):
                return (cx, cy)

        else:  # moving vertically
            prev_y = cy - dy
            if env.is_blocked(cx - 1, prev_y) and not env.is_blocked(cx - 1, cy):
                return (cx, cy)
            if env.is_blocked(cx + 1, prev_y) and not env.is_blocked(cx + 1, cy):
                return (cx, cy)
            # Perpendicular sub-scan left/right
            if (_simple_scan(env, cx, cy,  1, 0, goal_x, goal_y) or
                    _simple_scan(env, cx, cy, -1, 0, goal_x, goal_y)):
                return (cx, cy)

        cx, cy = cx + dx, cy + dy
    return None


def identify_successors(env, x, y, goal_x, goal_y):
    """
    From (x,y), jump in all four cardinal directions and collect
    every jump point found. These are the only nodes we need to
    put on the open list — everything in between can be skipped.
    """
    successors = []
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        jp = jump(env, x, y, dx, dy, goal_x, goal_y)
        if jp is not None:
            successors.append(jp)
    return successors


def fill_path(sparse):
    """
    JPS only stores jump points, but the agent needs every cell.
    Walk between consecutive jump points in a straight line and
    insert all the cells in between.
    """
    if not sparse:
        return []
    full = [sparse[0]]
    for i in range(1, len(sparse)):
        x1, y1 = sparse[i - 1]
        x2, y2 = sparse[i]
        if x1 == x2:  # vertical segment
            step = 1 if y2 > y1 else -1
            for y in range(y1 + step, y2 + step, step):
                full.append((x1, y))
        else:  # horizontal segment
            step = 1 if x2 > x1 else -1
            for x in range(x1 + step, x2 + step, step):
                full.append((x, y1))
    return full


def reconstruct_path(came_from, start, goal):
    """
    Trace back through came_from to build the path from start to goal,
    then reverse it so it reads in the correct order.
    """
    path = []
    current = goal
    while current != start:
        path.append(current)
        current = came_from.get(current)
        if current is None:
            return []
    path.append(start)
    path.reverse()
    return path


def jps(env, start_x, start_y, goal_x, goal_y):
    """
    Run Jump Point Search from (start_x,start_y) to (goal_x,goal_y).
    Returns a list of every (x,y) cell on the path, or [] if no path exists.
    The list includes all intermediate cells, not just jump points.
    """
    if env.is_blocked(goal_x, goal_y):
        return []

    start = (start_x, start_y)
    goal = (goal_x, goal_y)

    open_heap = []
    g_score = {start: 0}
    came_from = {}
    closed = set()

    f0 = heuristic(start_x, start_y, goal_x, goal_y)
    heapq.heappush(open_heap, (f0, 0, start))

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            sparse = reconstruct_path(came_from, start, goal)
            return fill_path(sparse)

        cx, cy = current
        for successor in identify_successors(env, cx, cy, goal_x, goal_y):
            if successor in closed:
                continue
            sx, sy = successor
            new_g = g + heuristic(cx, cy, sx, sy)
            if new_g < g_score.get(successor, float("inf")):
                g_score[successor] = new_g
                came_from[successor] = current
                f = new_g + heuristic(sx, sy, goal_x, goal_y)
                heapq.heappush(open_heap, (f, new_g, successor))

    return []
