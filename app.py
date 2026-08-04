from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

# File path for persistent order storage
ORDERS_FILE = os.path.join(os.path.dirname(__file__), 'orders.json')

# In-memory database tracking order states and theme configurations.
# Orders are keyed by their order number (e.g. "001", "A493").
#
# Order lifecycle:
#   queued    -> bestelling / new incoming order (shown ONLY on input col 1).
#                Also where orders wait when the kitchen is full.
#   preparing -> being made in the kitchen (shown on kitchen + display + input col 2)
#   done      -> ready for pickup (shown on display + input col 3)
#   picked_up -> removed by staff on the input page (shown nowhere)
order_data = {
    "orders": {},             # {order_number: order_object}
    "order_queue": [],        # FIFO list of order_numbers
    "kitchen_capacity": 8,    # max orders shown on the kitchen display at once
    "pos_connected": False,
    "auto_mode": False,       # when on, incoming orders auto-enter the kitchen queue
    "display_theme": "dark"   # Default global display theme state
}

# Gedetailleerde actiehistorie voor de Undo-functionaliteit per ordernummer
action_history = []

VALID_STATUSES = ('queued', 'preparing', 'done', 'picked_up')


def record_action(order, from_status, to_status):
    """Record a status transition for the global undo feature."""
    global action_history
    # Don't record new-order creation for undo
    if from_status is None and to_status == 'queued':
        return
    action_history.append({
        "order": order.upper(),
        "from_status": from_status,
        "to_status": to_status
    })
    if len(action_history) > 20:
        action_history.pop(0)


def load_orders():
    """Load orders from JSON file on startup."""
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, 'r') as f:
                data = json.load(f)
                order_data['orders'] = data.get('orders', {})
                order_data['order_queue'] = data.get('order_queue', [])
                order_data['kitchen_capacity'] = data.get('kitchen_capacity', 8)
                order_data['display_theme'] = data.get('display_theme', 'dark')
                order_data['pos_connected'] = data.get('pos_connected', False)
                order_data['auto_mode'] = data.get('auto_mode', False)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load orders file: {e}")


def save_orders():
    """Save orders to JSON file."""
    try:
        with open(ORDERS_FILE, 'w') as f:
            json.dump(order_data, f, indent=2)
    except OSError as e:
        print(f"Error saving orders: {e}")


def orders_in_state(state):
    """Return full order objects for a state, maintaining FIFO order."""
    return [order_data['orders'][n] for n in order_data['order_queue']
            if order_data['orders'][n].get('status') == state]


def count_in_state(state):
    """Count orders currently in a given state."""
    return sum(1 for n in order_data['order_queue']
               if order_data['orders'][n].get('status') == state)


def fill_preparing():
    """Promote queued (bestelling) orders to preparing while kitchen slots are free."""
    capacity = order_data['kitchen_capacity']
    for n in order_data['order_queue']:
        if count_in_state('preparing') >= capacity:
            break
        if order_data['orders'][n].get('status') == 'queued':
            order_data['orders'][n]['status'] = 'preparing'
            order_data['orders'][n]['updated_at'] = datetime.now().isoformat()


def enforce_capacity():
    """Demote preparing orders back to queued if capacity is exceeded."""
    capacity = order_data['kitchen_capacity']
    while count_in_state('preparing') > capacity:
        demoted = None
        for n in reversed(order_data['order_queue']):
            if order_data['orders'][n].get('status') == 'preparing':
                demoted = n
                break
        if demoted is None:
            break
        order_data['orders'][demoted]['status'] = 'queued'
        order_data['orders'][demoted]['updated_at'] = datetime.now().isoformat()


def get_current_state():
    """Build the current state response for API."""
    return {
        'queued': orders_in_state('queued'),
        'preparing': orders_in_state('preparing'),
        'done': orders_in_state('done'),
        'picked_up': orders_in_state('picked_up'),
        'kitchen_capacity': order_data['kitchen_capacity'],
        'pos_connected': order_data['pos_connected'],
        'auto_mode': order_data['auto_mode'],
        'display_theme': order_data['display_theme']
    }


# Load orders on module import
load_orders()


@app.route('/')
@app.route('/input')
def input_page():
    return render_template('input.html')


@app.route('/display')
def display_page():
    return render_template('display.html')


@app.route('/kitchen')
def kitchen_page():
    return render_template('kitchen.html')


# --- API Endpoints ---

@app.route('/api/orders', methods=['GET', 'POST'])
def handle_orders():
    if request.method == 'POST':
        data = request.get_json() or {}

        # Normalize order number to uppercase
        order_number = str(data.get('order', '')).strip().upper()
        status = data.get('status', 'queued')
        source = data.get('source', '')
        # Full order object with line items, customer info, etc.
        order_details = data.get('order_details', {}) or {}

        if source == 'pos':
            order_data['pos_connected'] = True

        # Validate order number
        if order_number and order_number.isalnum():
            now = datetime.now().isoformat()

            if order_number in order_data['orders']:
                # Update existing order (keep its FIFO position and current status)
                order_data['orders'][order_number].update({
                    'updated_at': now,
                    **order_details
                })
            else:
                # Determine the initial status.
                # In auto mode, incoming orders go straight to the kitchen
                # (preparing if there's space, otherwise queued/bestelling).
                # Otherwise they start as 'queued' (bestelling) and only become
                # 'preparing' when the input page promotes them.
                if status in ('ready', 'done'):
                    new_status = 'done'
                elif status == 'preparing':
                    new_status = 'preparing'
                elif order_data['auto_mode']:
                    if count_in_state('preparing') < order_data['kitchen_capacity']:
                        new_status = 'preparing'
                    else:
                        new_status = 'queued'
                else:
                    new_status = 'queued'

                order_data['orders'][order_number] = {
                    'order': order_number,
                    'status': new_status,
                    'created_at': now,
                    'updated_at': now,
                    'source': source,
                    **order_details
                }
                order_data['order_queue'].append(order_number)

            save_orders()
            return jsonify(get_current_state())

        return jsonify({'error': 'Invalid order number'}), 400

    return jsonify(get_current_state())


@app.route('/api/orders/<order>/preparing', methods=['PUT'])
def move_to_preparing(order):
    """Move an order to preparing (in the kitchen). Used by the input page col 1 -> col 2."""
    order = order.upper()
    if order in order_data['orders']:
        old = order_data['orders'][order]['status']
        record_action(order, old, 'preparing')
        order_data['orders'][order]['status'] = 'preparing'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        # If it was queued, fill any remaining kitchen slots
        fill_preparing()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>/ready', methods=['PUT'])
def move_to_ready(order):
    """Move an order to done (ready for pickup). Used by input page col 2 -> col 3 and as manual override."""
    order = order.upper()
    if order in order_data['orders']:
        old = order_data['orders'][order]['status']
        record_action(order, old, 'ready')
        order_data['orders'][order]['status'] = 'done'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        # Freeing a slot lets the next queued order move to preparing
        if old in ('preparing', 'queued'):
            fill_preparing()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>/done', methods=['PUT'])
def mark_done(order):
    """Kitchen tap: preparing -> done."""
    order = order.upper()
    if order in order_data['orders'] and order_data['orders'][order]['status'] == 'preparing':
        record_action(order, 'preparing', 'done')
        order_data['orders'][order]['status'] = 'done'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        # Freeing a slot lets the next queued order move to preparing
        fill_preparing()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>/undo', methods=['PUT'])
def undo_done(order):
    """Undo a done order: move it back to preparing."""
    order = order.upper()
    if order in order_data['orders'] and order_data['orders'][order]['status'] == 'done':
        record_action(order, 'done', 'preparing')
        order_data['orders'][order]['status'] = 'preparing'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        # A queued order may have been promoted to fill the freed slot; if we now
        # exceed capacity, demote the last promoted order back to queued.
        enforce_capacity()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>/pickup', methods=['PUT'])
def pickup_order(order):
    order = order.upper()
    if order in order_data['orders'] and order_data['orders'][order]['status'] == 'done':
        record_action(order, 'done', 'picked_up')
        order_data['orders'][order]['status'] = 'picked_up'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>', methods=['DELETE'])
def delete_order(order):
    order = order.upper()
    if order in order_data['orders']:
        record_action(order, order_data['orders'][order]['status'], 'deleted')
    if order in order_data['order_queue']:
        order_data['order_queue'].remove(order)
    if order in order_data['orders']:
        del order_data['orders'][order]
    # Removing a preparing order frees a slot for the next queued order
    fill_preparing()
    save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/clear', methods=['DELETE'])
def clear_all_orders():
    """Clear all orders (useful for testing or end of day)."""
    order_data['orders'] = {}
    order_data['order_queue'] = []
    save_orders()
    return jsonify(get_current_state())


@app.route('/api/undo', methods=['POST'])
def undo_action():
    """Global undo of the last recorded action (input page undo button)."""
    global action_history
    if not action_history:
        return jsonify(get_current_state())

    last_action = action_history.pop()
    order = last_action['order']
    from_status = last_action['from_status']
    to_status = last_action['to_status']

    # Block rule: don't undo preparing -> queued
    if from_status == 'preparing' and to_status == 'queued':
        action_history.append(last_action)
        return jsonify(get_current_state())

    if to_status == 'deleted':
        target = from_status if from_status in VALID_STATUSES else 'done'
    else:
        target = from_status if from_status in VALID_STATUSES else 'queued'

    if order in order_data['orders']:
        order_data['orders'][order]['status'] = target
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        if target == 'preparing':
            enforce_capacity()
        else:
            fill_preparing()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/kitchen/capacity', methods=['POST'])
def set_capacity():
    data = request.get_json() or {}
    try:
        cap = int(data.get('capacity', order_data['kitchen_capacity']))
    except (TypeError, ValueError):
        cap = order_data['kitchen_capacity']
    order_data['kitchen_capacity'] = max(1, min(cap, 50))
    # If capacity grew, promote queued orders to fill the new slots.
    fill_preparing()
    # If capacity shrank, demote excess preparing orders back to the queue
    # so they no longer overflow the visible grid.
    enforce_capacity()
    save_orders()
    return jsonify(get_current_state())


@app.route('/api/auto_mode', methods=['POST'])
def set_auto_mode():
    data = request.get_json() or {}
    auto = bool(data.get('auto_mode', False))
    order_data['auto_mode'] = auto
    save_orders()
    return jsonify(get_current_state())


@app.route('/api/theme', methods=['POST'])
def update_theme():
    data = request.get_json() or {}
    theme = data.get('theme', 'dark')
    if theme in ['dark', 'light']:
        order_data['display_theme'] = theme
        save_orders()
    return jsonify(get_current_state())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)