"""
entities.py — Restaurant, Customer, and Order.
These are the things on the map that agents interact with.
"""

import itertools

# A module-level counter so every order gets a unique ID.
_order_id_counter = itertools.count(1)


class Order:
    """
    Represents a single delivery request.
    status moves through: "pending" → "collected" → "delivered"
                      or: any stage  → "cancelled"
    """

    def __init__(self, customer, restaurant):
        self.order_id = next(_order_id_counter)
        self.customer = customer        # Customer object
        self.restaurant = restaurant    # Restaurant object
        self.status = "pending"
        self.wait_ticks = 0            # how many ticks this order has waited

    def tick(self):
        """Increment wait time every simulation tick if still pending."""
        if self.status == "pending":
            self.wait_ticks += 1

    def __repr__(self):
        return f"Order#{self.order_id}({self.status})"


class Restaurant:
    """
    A fixed location that holds a queue of orders waiting to be picked up.
    """

    def __init__(self, cell):
        self.cell = cell               # GridCell where this restaurant sits
        self.order_queue = []          # list of Order objects

    def add_order(self, order):
        """Put a new order at the back of the queue."""
        self.order_queue.append(order)

    def get_next_order(self):
        """
        Remove and return the order that has waited the longest.
        Returns None if there are no orders.
        """
        if not self.order_queue:
            return None
        # The one with the highest wait_ticks goes first.
        self.order_queue.sort(key=lambda o: o.wait_ticks, reverse=True)
        return self.order_queue.pop(0)

    def remove_order(self, order):
        """Remove a specific order from the queue (e.g. if cancelled)."""
        if order in self.order_queue:
            self.order_queue.remove(order)

    def __repr__(self):
        return f"Restaurant@({self.cell.x},{self.cell.y})"


class Customer:
    """
    A fixed location that can place and cancel one order at a time.
    """

    def __init__(self, cell):
        self.cell = cell               # GridCell where this customer lives
        self.active_order = None       # the current Order, or None

    def place_order(self, restaurant):
        """
        Create a new order aimed at the given restaurant.
        Returns the Order so it can be added to the restaurant's queue.
        """
        order = Order(self, restaurant)
        self.active_order = order
        restaurant.add_order(order)
        return order

    def cancel_order(self):
        """
        Mark the current order as cancelled.
        Returns the cancelled Order, or None if there was no order.
        """
        if self.active_order and self.active_order.status != "delivered":
            self.active_order.status = "cancelled"
            cancelled = self.active_order
            self.active_order = None
            return cancelled
        return None

    def receive_delivery(self):
        """Mark the active order as delivered and clear it."""
        if self.active_order:
            self.active_order.status = "delivered"
            self.active_order = None

    def __repr__(self):
        return f"Customer@({self.cell.x},{self.cell.y})"
