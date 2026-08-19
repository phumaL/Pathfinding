"""
main.py — Entry point for Smart Delivery simulation.
Initialises pygame, builds the world, and runs the game loop.
"""

import pygame
import pygame.freetype
import random

from grid import GridEnvironment
from entities import Restaurant, Customer
from agent import DeliveryAgent

# ── constants ──────────────────────────────────────────────────────────────
GRID_COLS = 20
GRID_ROWS = 20
CELL_SIZE = 36          # pixels per cell
SIDEBAR_W = 220         # pixels for the right-hand info panel
FPS     = 5             # default simulation ticks per second
FPS_MIN = 1             # slowest allowed speed
FPS_MAX = 20            # fastest allowed speed
BLOCK_FRACTION = 0.15   # fraction of cells randomly blocked at startup
MAX_AGENTS    = 6       # upper limit on the number of agents (and restaurants)
MIN_AGENTS    = 1       # can't remove the last agent
MAX_CUSTOMERS = 12      # upper limit on the number of customers
MIN_CUSTOMERS = 1       # can't remove the last customer

WINDOW_W = GRID_COLS * CELL_SIZE + SIDEBAR_W
WINDOW_H = GRID_ROWS * CELL_SIZE

# Colours (R, G, B)
C_WHITE      = (255, 255, 255)
C_BLOCKED    = ( 60,  60,  60)
C_RESTAURANT = ( 34, 177,  76)   # green
C_CUSTOMER   = ( 63, 122, 231)   # blue
C_AGENT      = (220,  50,  50)   # red
C_PATH       = (255, 230,  50)   # yellow
C_GRID_LINE  = (200, 200, 200)
C_SIDEBAR_BG = ( 30,  30,  30)
C_TEXT       = (230, 230, 230)
C_CANCELLED  = (255, 100,  50)   # orange — cancelled order flash

# Fixed positions so restaurants/customers never overlap
RESTAURANT_POSITIONS = [(3, 3), (16, 3), (10, 16)]
CUSTOMER_POSITIONS   = [(1, 16), (6, 10), (13, 6),
                        (18, 14), (5, 18), (15, 18)]
AGENT_STARTS         = [(3, 4),  (16, 4), (10, 15)]  # near each restaurant


# ── world setup ────────────────────────────────────────────────────────────

def build_world():
    """Create the grid, restaurants, customers, and agents."""
    env = GridEnvironment(GRID_COLS, GRID_ROWS)

    restaurants = [Restaurant(env.get_cell(x, y)) for x, y in RESTAURANT_POSITIONS]
    customers   = [Customer(env.get_cell(x, y))   for x, y in CUSTOMER_POSITIONS]

    # Protect all special positions from being randomly blocked
    protected = (RESTAURANT_POSITIONS + CUSTOMER_POSITIONS + AGENT_STARTS)
    env.randomly_block(BLOCK_FRACTION, protected)

    agents = []
    for i, (ax, ay) in enumerate(AGENT_STARTS):
        agent = DeliveryAgent(env.get_cell(ax, ay), restaurants[i], env, i)
        env.register_agent(agent)
        agents.append(agent)

    return env, restaurants, customers, agents


# ── order scheduling ────────────────────────────────────────────────────────

def maybe_place_orders(customers, restaurants, tick):
    """
    Every 10 ticks, give each customer without an active order a
    random chance to place one at a random restaurant.
    """
    if tick % 10 != 0:
        return
    for customer in customers:
        if customer.active_order is None:
            if random.random() < 0.5:
                restaurant = random.choice(restaurants)
                customer.place_order(restaurant)


def maybe_cancel_orders(customers, tick):
    """
    Every 25 ticks, give each customer a small chance to cancel
    their active order (simulates a change of mind).
    """
    if tick % 25 != 0:
        return
    for customer in customers:
        if customer.active_order and customer.active_order.status == "pending":
            if random.random() < 0.2:
                customer.cancel_order()


# ── drawing helpers ─────────────────────────────────────────────────────────

def draw_grid(surface, env, restaurants, customers, agents, selected_agent):
    """Draw every cell, then overlay special entities on top."""
    # Collect sets of special positions for fast lookup
    rest_positions  = {(r.cell.x, r.cell.y) for r in restaurants}
    cust_positions  = {(c.cell.x, c.cell.y) for c in customers}
    agent_positions = {(a.cell.x, a.cell.y) for a in agents}

    # Active path of the selected agent (if any)
    path_set = set()
    if selected_agent is not None:
        path_set = set(selected_agent.path)

    for x in range(env.cols):
        for y in range(env.rows):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE,
                               CELL_SIZE - 1, CELL_SIZE - 1)
            cell = env.get_cell(x, y)
            pos = (x, y)

            # Choose fill colour based on what is at this cell
            if cell.is_blocked:
                colour = C_BLOCKED
            elif pos in path_set:
                colour = C_PATH
            elif pos in rest_positions:
                colour = C_RESTAURANT
            elif pos in cust_positions:
                colour = C_CUSTOMER
            elif pos in agent_positions:
                colour = C_AGENT
            else:
                colour = C_WHITE

            pygame.draw.rect(surface, colour, rect)

    # Grid lines
    for x in range(env.cols + 1):
        pygame.draw.line(surface, C_GRID_LINE,
                         (x * CELL_SIZE, 0),
                         (x * CELL_SIZE, GRID_ROWS * CELL_SIZE))
    for y in range(env.rows + 1):
        pygame.draw.line(surface, C_GRID_LINE,
                         (0, y * CELL_SIZE),
                         (GRID_COLS * CELL_SIZE, y * CELL_SIZE))


C_ADD_BG  = ( 30,  70,  30)   # green tint for add buttons
C_ADD_BDR = ( 70, 160,  70)
C_REM_BG  = ( 70,  25,  25)   # red tint for remove buttons
C_REM_BDR = (160,  60,  60)
C_DIS_BG  = ( 40,  40,  40)   # greyed-out when disabled
C_DIS_BDR = ( 75,  75,  75)
C_BTN_BG     = ( 50,  45,  65)   # dark button background
C_BTN_BORDER = (120, 100, 160)   # button outline
C_BTN_TEXT   = (200, 180, 240)   # button label
C_ROW_SEL    = ( 55,  55,  90)   # selected agent row background
C_ROW_NORM   = ( 40,  40,  40)   # normal agent row background


def draw_world_controls(surface, small_font, agents, customers, sx, y):
    """
    Draw two rows of +/- buttons for adding and removing agents and customers.
    Buttons that would violate capacity limits are drawn greyed out and are
    not added to the hit list.
    Returns (hits, new_y).
    """
    hits = []
    BW = (SIDEBAR_W - 26) // 2   # width of each button
    BH = 21                       # button height
    left_x  = sx + 10
    right_x = sx + 10 + BW + 6

    def _btn(label, action, bg, bdr, bx, by, disabled):
        """Draw one button and, if enabled, append its rect to hits."""
        real_bg  = C_DIS_BG  if disabled else bg
        real_bdr = C_DIS_BDR if disabled else bdr
        txt_col  = (80, 80, 80) if disabled else (220, 220, 220)
        r = pygame.Rect(bx, by, BW, BH)
        pygame.draw.rect(surface, real_bg, r)
        pygame.draw.rect(surface, real_bdr, r, 1)
        surf, _ = small_font.render(label, txt_col)
        surface.blit(surf, (r.x + 5, r.y + 4))
        if not disabled:
            hits.append({'rect': r, 'kind': 'world_action', 'action': action})

    row1 = y
    row2 = y + BH + 4

    _btn('+Agent', 'add_agent',       C_ADD_BG, C_ADD_BDR, left_x,  row1, len(agents)    >= MAX_AGENTS)
    _btn('-Agent', 'remove_agent',    C_REM_BG, C_REM_BDR, right_x, row1, len(agents)    <= MIN_AGENTS)
    _btn('+Cust',  'add_customer',    C_ADD_BG, C_ADD_BDR, left_x,  row2, len(customers) >= MAX_CUSTOMERS)
    _btn('-Cust',  'remove_customer', C_REM_BG, C_REM_BDR, right_x, row2, len(customers) <= MIN_CUSTOMERS)

    return hits, row2 + BH + 8


def draw_agent_panel(surface, small_font, agents, selected_agent, sx, y):
    """
    Draw a clickable agent list inside the sidebar.
    Each row shows the agent's colour, ID, and status.
    Clicking a row selects the agent; the selected agent expands to
    show position, current order destination, a 'Cancel delivery' button
    (when carrying an order), and a 'Return to base' button.

    Returns (hits, new_y) where hits is a list of dicts that describe
    every clickable region:
        {'rect': Rect, 'kind': 'select_agent', 'agent': agent}
        {'rect': Rect, 'kind': 'action', 'agent': agent, 'action': str}
    """
    hits = []

    for agent in agents:
        is_sel = agent is selected_agent

        # ── agent header row ──────────────────────────────────────────────
        bg   = C_ROW_SEL if is_sel else C_ROW_NORM
        row  = pygame.Rect(sx + 4, y, SIDEBAR_W - 8, 22)
        pygame.draw.rect(surface, bg, row)
        pygame.draw.rect(surface, C_AGENT, pygame.Rect(sx + 8, y + 5, 12, 12))
        col  = (255, 230, 80) if is_sel else C_TEXT
        surf, _ = small_font.render(f" A{agent.agent_id}  {agent.status_label}", col)
        surface.blit(surf, (sx + 22, y + 4))
        hits.append({'rect': row, 'kind': 'select_agent', 'agent': agent})
        y += 24

        if not is_sel:
            continue

        # ── expanded detail (only for selected agent) ─────────────────────
        y = _sidebar_text(surface, small_font,
                          f"  pos:  ({agent.cell.x}, {agent.cell.y})",
                          C_TEXT, sx + 10, y)
        # List every destination in the current batch
        for order in agent.order_batch:
            cx = order.customer.cell.x
            cy = order.customer.cell.y
            y = _sidebar_text(surface, small_font,
                              f"  order → ({cx}, {cy})",
                              C_TEXT, sx + 10, y)
        y = _sidebar_text(surface, small_font,
                          f"  done:  {agent.deliveries_done}",
                          C_TEXT, sx + 10, y)
        y += 4

        # ── action buttons ────────────────────────────────────────────────
        actions = []
        if agent.order_batch:
            actions.append(('cancel_order', 'Cancel all orders'))
        actions.append(('force_return', 'Return to base'))

        for action_id, label in actions:
            btn = pygame.Rect(sx + 12, y, SIDEBAR_W - 24, 20)
            pygame.draw.rect(surface, C_BTN_BG, btn)
            pygame.draw.rect(surface, C_BTN_BORDER, btn, 1)
            surf, _ = small_font.render(label, C_BTN_TEXT)
            surface.blit(surf, (sx + 16, y + 3))
            hits.append({'rect': btn, 'kind': 'action',
                         'agent': agent, 'action': action_id})
            y += 24

        y += 6

    return hits, y


def _sidebar_text(surface, f, text, colour, x, y):
    """Render one line of text in the sidebar; return the new y position."""
    surf, rect = f.render(text, colour)
    surface.blit(surf, (x, y))
    return y + rect.height + 4


def _legend_row(surface, colour, label, small_font, sx, y):
    """Draw a small coloured square followed by a label; return new y."""
    pygame.draw.rect(surface, colour, pygame.Rect(sx + 10, y + 1, 11, 11))
    surf, rect = small_font.render(label, C_TEXT)
    surface.blit(surf, (sx + 26, y))
    return y + rect.height + 4


def draw_sidebar(surface, font, small_font, agents, customers,
                 deliveries_done, fps, paused, selected_agent):
    """
    Draw the full right-hand panel and return a list of clickable hit-rects.
    Every interactive element (agent rows and action buttons) adds an entry
    to the hits list so the event loop can respond to sidebar clicks.
    """
    sx = GRID_COLS * CELL_SIZE
    pygame.draw.rect(surface, C_SIDEBAR_BG, pygame.Rect(sx, 0, SIDEBAR_W, WINDOW_H))

    active_orders = sum(
        1 for c in customers
        if c.active_order and c.active_order.status in ("pending", "collected")
    )
    status_text   = "|| PAUSED" if paused else f"|>  {fps} tps"
    status_colour = (255, 200, 50) if paused else (100, 220, 100)

    y = 12
    y = _sidebar_text(surface, font, "Smart Delivery", C_TEXT, sx + 10, y)
    y = _sidebar_text(surface, font, status_text, status_colour, sx + 10, y)
    y += 4
    y = _sidebar_text(surface, small_font, f"Active orders: {active_orders}",  C_TEXT, sx + 10, y)
    y = _sidebar_text(surface, small_font, f"Delivered:     {deliveries_done}", C_TEXT, sx + 10, y)

    y += 8
    y = _sidebar_text(surface, font, "-- World --", C_TEXT, sx + 10, y)
    y += 2
    world_hits, y = draw_world_controls(surface, small_font, agents, customers, sx, y)

    y = _sidebar_text(surface, font, "-- Agents --", C_TEXT, sx + 10, y)
    y += 4
    agent_hits, y = draw_agent_panel(surface, small_font, agents, selected_agent, sx, y)
    hits = world_hits + agent_hits

    y += 6
    y = _sidebar_text(surface, font, "-- Legend --", C_TEXT, sx + 10, y)
    y = _legend_row(surface, C_RESTAURANT, "Restaurant",  small_font, sx, y)
    y = _legend_row(surface, C_CUSTOMER,   "Customer",    small_font, sx, y)
    y = _legend_row(surface, C_AGENT,      "Agent",       small_font, sx, y)
    y = _legend_row(surface, C_PATH,       "Active path", small_font, sx, y)
    y = _legend_row(surface, C_BLOCKED,    "Blocked",     small_font, sx, y)

    y += 6
    y = _sidebar_text(surface, font, "-- Keys --", C_TEXT, sx + 10, y)
    for hint in ("SPACE  pause/resume",
                 "UP/DN  speed",
                 "C  clear walls",
                 "R  reset world",
                 "L-click grid agent: select",
                 "L-click cust: order",
                 "L-drag: paint wall",
                 "R-click: deselect",
                 "ESC  quit"):
        y = _sidebar_text(surface, small_font, hint, C_TEXT, sx + 10, y)

    return hits


def count_deliveries(agents):
    """Sum up all completed deliveries across all agents."""
    return sum(a.deliveries_done for a in agents)


# ── click / interaction helpers ─────────────────────────────────────────────

def grid_pos(mouse_x, mouse_y):
    """Convert pixel coordinates to grid (col, row)."""
    return mouse_x // CELL_SIZE, mouse_y // CELL_SIZE


def find_agent_at(agents, mouse_x, mouse_y):
    """Return the agent standing on the clicked cell, or None."""
    gx, gy = grid_pos(mouse_x, mouse_y)
    for agent in agents:
        if agent.cell.x == gx and agent.cell.y == gy:
            return agent
    return None


def find_customer_at(customers, mouse_x, mouse_y):
    """Return the customer living on the clicked cell, or None."""
    gx, gy = grid_pos(mouse_x, mouse_y)
    for customer in customers:
        if customer.cell.x == gx and customer.cell.y == gy:
            return customer
    return None


def is_special_cell(gx, gy, agents, restaurants, customers):
    """Return True if this cell holds an agent, restaurant, or customer."""
    for a in agents:
        if a.cell.x == gx and a.cell.y == gy:
            return True
    for r in restaurants:
        if r.cell.x == gx and r.cell.y == gy:
            return True
    for c in customers:
        if c.cell.x == gx and c.cell.y == gy:
            return True
    return False


# ── world mutation helpers ──────────────────────────────────────────────────

def _occupied(agents, restaurants, customers):
    """Return the set of (x, y) positions currently taken by any entity."""
    pos = set()
    for a in agents:
        pos.add((a.cell.x, a.cell.y))
    for r in restaurants:
        pos.add((r.cell.x, r.cell.y))
    for c in customers:
        pos.add((c.cell.x, c.cell.y))
    return pos


def _free_cell(env, taken):
    """Pick a random unblocked cell not in the 'taken' set, or None if the grid is full."""
    candidates = [
        env.get_cell(x, y)
        for x in range(env.cols) for y in range(env.rows)
        if not env.is_blocked(x, y) and (x, y) not in taken
    ]
    return random.choice(candidates) if candidates else None


def do_add_agent(env, agents, restaurants, customers):
    """Place a new restaurant at a random free cell, then spawn an agent nearby."""
    if len(agents) >= MAX_AGENTS:
        return
    taken   = _occupied(agents, restaurants, customers)
    r_cell  = _free_cell(env, taken)
    if r_cell is None:
        return
    taken.add((r_cell.x, r_cell.y))
    a_cell  = _free_cell(env, taken)
    if a_cell is None:
        return
    rest     = Restaurant(r_cell)
    new_id   = max((a.agent_id for a in agents), default=-1) + 1
    agent    = DeliveryAgent(a_cell, rest, env, new_id)
    restaurants.append(rest)
    env.register_agent(agent)
    agents.append(agent)


def do_remove_agent(env, agents, restaurants, selected_agent):
    """Remove the selected agent (or the last one) and its restaurant.
    Cancels all carried orders and returns the new selected_agent value."""
    if len(agents) <= MIN_AGENTS:
        return selected_agent
    target = selected_agent if selected_agent in agents else agents[-1]
    target.cancel_all_orders()
    env.deregister_agent(target)
    restaurants.remove(target.restaurant)
    agents.remove(target)
    return None


def do_add_customer(env, agents, restaurants, customers):
    """Place a new customer at a random free cell."""
    if len(customers) >= MAX_CUSTOMERS:
        return
    taken  = _occupied(agents, restaurants, customers)
    cell   = _free_cell(env, taken)
    if cell:
        customers.append(Customer(cell))


def do_remove_customer(customers):
    """Remove the last customer and cancel any order they are waiting on."""
    if len(customers) <= MIN_CUSTOMERS:
        return
    cust = customers.pop()
    if cust.active_order:
        cust.active_order.status = "cancelled"
        cust.active_order = None


def clear_walls(env, agents):
    """Unblock every blocked cell on the grid, then tell all agents to replan."""
    for x in range(env.cols):
        for y in range(env.rows):
            cell = env.get_cell(x, y)
            if cell.is_blocked:
                cell.is_blocked = False
                for agent in agents:
                    agent.on_map_changed(cell)


def _do_sidebar_action(hit):
    """Execute the action stored in a sidebar hit-rect dict."""
    agent  = hit['agent']
    action = hit['action']
    if action == 'cancel_order':
        agent.cancel_all_orders()
    elif action == 'force_return':
        agent.force_return_to_restaurant()


def main():
    """Set up pygame and run the simulation loop."""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Smart Delivery")

    pygame.freetype.init()
    font       = pygame.freetype.SysFont("monospace", 15, bold=True)
    small_font = pygame.freetype.SysFont("monospace", 13)
    clock      = pygame.time.Clock()

    env, restaurants, customers, agents = build_world()

    selected_agent = None   # agent whose path is highlighted in yellow
    paused         = False  # True while the simulation is frozen
    fps            = FPS    # current tick rate (changed by UP/DOWN keys)
    # painting = True  → dragging adds walls
    # painting = False → dragging removes walls
    # painting = None  → mouse button is up, not painting
    painting     = None
    sidebar_hits = []   # clickable rects built by draw_sidebar each frame
    tick = 0
    running = True

    while running:
        # ── events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_UP, pygame.K_EQUALS):
                    fps = min(fps + 1, FPS_MAX)
                elif event.key in (pygame.K_DOWN, pygame.K_MINUS):
                    fps = max(fps - 1, FPS_MIN)
                elif event.key == pygame.K_c:
                    clear_walls(env, agents)
                elif event.key == pygame.K_r:
                    env, restaurants, customers, agents = build_world()
                    selected_agent = None
                    tick = 0

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if mx < GRID_COLS * CELL_SIZE:
                    gx, gy = grid_pos(mx, my)
                    if event.button == 1:
                        hit_agent = find_agent_at(agents, mx, my)
                        hit_cust  = find_customer_at(customers, mx, my)
                        if hit_agent:
                            # Toggle selection: click the same agent again to deselect
                            selected_agent = None if hit_agent is selected_agent else hit_agent
                        elif hit_cust:
                            # Place a new order, or cancel an existing pending one
                            if hit_cust.active_order is None:
                                hit_cust.place_order(random.choice(restaurants))
                            elif hit_cust.active_order.status == "pending":
                                hit_cust.cancel_order()
                        elif not is_special_cell(gx, gy, agents, restaurants, customers):
                            # Start painting: remember whether we're adding or removing walls
                            cell = env.get_cell(gx, gy)
                            painting = not cell.is_blocked
                            env.toggle_cell(gx, gy)
                    elif event.button == 3:
                        selected_agent = None   # right-click deselects
                else:
                    # click was in the sidebar — check hit-rects from last frame
                    if event.button == 1:
                        for hit in sidebar_hits:
                            if hit['rect'].collidepoint(mx, my):
                                if hit['kind'] == 'select_agent':
                                    agent = hit['agent']
                                    selected_agent = None if agent is selected_agent else agent
                                elif hit['kind'] == 'action':
                                    _do_sidebar_action(hit)
                                elif hit['kind'] == 'world_action':
                                    action = hit['action']
                                    if action == 'add_agent':
                                        do_add_agent(env, agents, restaurants, customers)
                                    elif action == 'remove_agent':
                                        selected_agent = do_remove_agent(
                                            env, agents, restaurants, selected_agent)
                                    elif action == 'add_customer':
                                        do_add_customer(env, agents, restaurants, customers)
                                    elif action == 'remove_customer':
                                        do_remove_customer(customers)
                                break

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    painting = None             # stop painting on mouse release

            elif event.type == pygame.MOUSEMOTION:
                # Continue painting while the left button is held
                if painting is not None and pygame.mouse.get_pressed()[0]:
                    mx, my = event.pos
                    if mx < GRID_COLS * CELL_SIZE:
                        gx, gy = grid_pos(mx, my)
                        if not is_special_cell(gx, gy, agents, restaurants, customers):
                            cell = env.get_cell(gx, gy)
                            # Only act if the cell isn't already in the desired state
                            if cell and cell.is_blocked != painting:
                                env.toggle_cell(gx, gy)

        # ── simulation tick (skipped while paused) ────────────────────────
        if not paused:
            maybe_place_orders(customers, restaurants, tick)
            maybe_cancel_orders(customers, tick)
            for order in _all_active_orders(customers):
                order.tick()
            for agent in agents:
                agent.tick()
            tick += 1

        # ── drawing ───────────────────────────────────────────────────────
        screen.fill(C_WHITE)
        draw_grid(screen, env, restaurants, customers, agents, selected_agent)
        sidebar_hits = draw_sidebar(screen, font, small_font, agents, customers,
                                    count_deliveries(agents), fps, paused, selected_agent)
        pygame.display.flip()
        clock.tick(fps)

    pygame.quit()


def _all_active_orders(customers):
    """Yield every order that is currently active (pending or collected)."""
    for customer in customers:
        if customer.active_order:
            yield customer.active_order


if __name__ == "__main__":
    main()
