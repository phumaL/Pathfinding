"""
grid.py — Defines cells and the grid environment.
Each cell knows its position and whether it is blocked.
The environment is a 2D list of cells and handles toggling blocked cells.
"""

import random


class GridCell:
    """One square on the grid."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.is_blocked = False
        self.weight = 1.0  # cost to enter this cell

    def __repr__(self):
        return f"Cell({self.x},{self.y},blocked={self.is_blocked})"


class GridEnvironment:
    """
    Holds all cells in a 2D list.
    Knows which positions are occupied by restaurants/customers/agents
    so it never blocks those cells at startup.
    """

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        # Build a 2D list: grid[x][y]
        self.grid = [
            [GridCell(x, y) for y in range(rows)]
            for x in range(cols)
        ]
        self._agents = []  # registered DeliveryAgent objects

    def get_cell(self, x, y):
        """Return the cell at (x, y), or None if out of bounds."""
        if 0 <= x < self.cols and 0 <= y < self.rows:
            return self.grid[x][y]
        return None

    def register_agent(self, agent):
        """Let the environment track an agent so it can notify it of changes."""
        self._agents.append(agent)

    def deregister_agent(self, agent):
        """Stop tracking an agent (called when the agent is removed from the world)."""
        if agent in self._agents:
            self._agents.remove(agent)

    def randomly_block(self, fraction, protected_positions):
        """
        Block roughly 'fraction' of all cells at random.
        Cells whose (x, y) appear in 'protected_positions' are never blocked.
        """
        protected = set(protected_positions)
        for x in range(self.cols):
            for y in range(self.rows):
                if (x, y) in protected:
                    continue
                if random.random() < fraction:
                    self.grid[x][y].is_blocked = True

    def toggle_cell(self, x, y):
        """
        Flip a cell between blocked and unblocked.
        Afterwards, tell every agent the map changed so they can replan.
        """
        cell = self.get_cell(x, y)
        if cell is None:
            return
        cell.is_blocked = not cell.is_blocked
        for agent in self._agents:
            agent.on_map_changed(cell)

    def get_passable_neighbours(self, x, y):
        """
        Return a list of unblocked cells that are directly adjacent
        (up, down, left, right — no diagonals) to (x, y).
        """
        neighbours = []
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy
            cell = self.get_cell(nx, ny)
            if cell and not cell.is_blocked:
                neighbours.append(cell)
        return neighbours

    def is_blocked(self, x, y):
        """Return True if the cell is out of bounds or marked as blocked."""
        cell = self.get_cell(x, y)
        return cell is None or cell.is_blocked
