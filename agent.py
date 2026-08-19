"""
agent.py — DeliveryAgent class.
Each agent is permanently assigned to one restaurant.
It collects a batch of orders (up to BATCH_SIZE at once), delivers them
one by one (longest-waiting customer first), then returns for the next batch.
"""

from jps import jps
from dstar_lite import replan

# How many orders one agent can carry at the same time.
BATCH_SIZE = 3

# Status labels shown in the sidebar.
STATUS_IDLE         = "idle"
STATUS_TO_RESTAURANT = "to restaurant"
STATUS_COLLECTING   = "collecting"
STATUS_DELIVERING   = "delivering"


# ── module-level helpers (keep the class shorter) ───────────────────────────

def _highest_priority(order_batch):
    """Return the order with the longest wait time, or None if batch is empty."""
    return max(order_batch, key=lambda o: o.wait_ticks) if order_batch else None


def _collect_batch(restaurant, order_batch):
    """
    Pull orders from the restaurant queue until the batch is full.
    Skips any order that was cancelled while waiting in the queue.
    """
    while len(order_batch) < BATCH_SIZE:
        order = restaurant.get_next_order()
        if order is None:
            break
        if order.status == "cancelled":
            continue
        order.status = "collected"
        order_batch.append(order)


def _purge_cancelled(order_batch):
    """
    Remove cancelled orders from the batch and free those customers
    so they can place a new order right away.
    """
    for order in order_batch:
        if order.status == "cancelled":
            order.customer.active_order = None
    return [o for o in order_batch if o.status != "cancelled"]


# ── DeliveryAgent ────────────────────────────────────────────────────────────

class DeliveryAgent:
    """One delivery agent on the grid."""

    def __init__(self, start_cell, restaurant, env, agent_id):
        self.agent_id           = agent_id
        self.cell               = start_cell   # current GridCell
        self.restaurant         = restaurant   # permanently assigned restaurant
        self.env                = env
        self.status             = STATUS_IDLE
        self.order_batch        = []           # Orders currently being carried
        self.path               = []           # (x, y) steps left to walk
        self.deliveries_done    = 0
        self._plan_to_restaurant()

    # ── path planning ────────────────────────────────────────────────────────

    def _plan_to_restaurant(self):
        """Use JPS to plan a path from the current position to the restaurant."""
        rx, ry = self.restaurant.cell.x, self.restaurant.cell.y
        self.path = jps(self.env, self.cell.x, self.cell.y, rx, ry)
        self.status = STATUS_TO_RESTAURANT

    def _plan_to_next_customer(self):
        """Plan a path to whichever customer in the batch has waited longest."""
        target = _highest_priority(self.order_batch)
        if target is None:
            return
        cx, cy = target.customer.cell.x, target.customer.cell.y
        self.path = jps(self.env, self.cell.x, self.cell.y, cx, cy)
        self.status = STATUS_DELIVERING

    # ── movement ─────────────────────────────────────────────────────────────

    def _step(self):
        """Advance one cell along the current path."""
        if len(self.path) < 2:
            self.path = []
            return
        nx, ny = self.path[1]
        nxt = self.env.get_cell(nx, ny)
        if nxt and not nxt.is_blocked:
            self.cell = nxt
            self.path.pop(0)

    def _at(self, cell):
        """Return True if the agent is standing on the given cell."""
        return self.cell.x == cell.x and self.cell.y == cell.y

    def on_map_changed(self, _):
        """Called by the environment when a cell is blocked/unblocked.
        Replans the whole current path; D* Lite reuses the unaffected prefix."""
        if not self.path:
            return
        self.path = replan(self.env, (self.cell.x, self.cell.y),
                           self.path, self.path[-1])

    # ── tick (one simulation step) ───────────────────────────────────────────

    def tick(self):
        """Advance the agent by one step following its state machine:
        idle → to_restaurant → collecting → delivering (repeat per order)."""
        self.order_batch = _purge_cancelled(self.order_batch)

        if self.status == STATUS_IDLE:
            self._plan_to_restaurant()

        elif self.status == STATUS_TO_RESTAURANT:
            if self._at(self.restaurant.cell):
                self.status = STATUS_COLLECTING
            else:
                self._step()
                if not self.path:
                    self._plan_to_restaurant()

        elif self.status == STATUS_COLLECTING:
            _collect_batch(self.restaurant, self.order_batch)
            if self.order_batch:
                self._plan_to_next_customer()
            else:
                self.status = STATUS_IDLE

        elif self.status == STATUS_DELIVERING:
            target = _highest_priority(self.order_batch)
            if target is None:
                self.status = STATUS_IDLE
                return
            # Replan whenever the path endpoint no longer matches the target
            target_pos = (target.customer.cell.x, target.customer.cell.y)
            if not self.path or self.path[-1] != target_pos:
                self._plan_to_next_customer()
            elif self._at(target.customer.cell):
                target.customer.receive_delivery()
                self.order_batch.remove(target)
                self.deliveries_done += 1
                if self.order_batch:
                    self._plan_to_next_customer()
                else:
                    self.status = STATUS_IDLE
            else:
                self._step()

    # ── UI commands ──────────────────────────────────────────────────────────

    def cancel_all_orders(self):
        """Drop every order in the current batch and go idle.
        Each affected customer is freed so they can reorder immediately."""
        for order in self.order_batch:
            order.customer.active_order = None
            order.status = "cancelled"
        self.order_batch = []
        self.path = []
        self.status = STATUS_IDLE

    def force_return_to_restaurant(self):
        """Cancel the entire batch and head straight back to the restaurant."""
        for order in self.order_batch:
            order.customer.active_order = None
            order.status = "cancelled"
        self.order_batch = []
        self._plan_to_restaurant()

    @property
    def status_label(self):
        """Return a human-readable status string, including batch size when delivering."""
        if self.status == STATUS_DELIVERING:
            return f"delivering ({len(self.order_batch)})"
        return self.status
