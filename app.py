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
#   queued    -> waiting for a free kitchen slot (not yet being made)
#   preparing -> new incoming order / bestelling (shown ONLY on input col 1)
#   pending   -> being made (shown on kitchen + display + input col 2)
#   done      -> ready for pickup (shown on display + input col 3)
#   picked_up -> removed by staff on the input page
order_data = {
    "orders": {},             # {order_number: order_object}
    "order_queue": [],        # FIFO list of order_numbers
    "kitchen_capacity": 8,    # max orders shown on the kitchen display at once
    "pos_connected": False,
    "display_theme": "dark"   # Default global display theme state
}

# Gedetailleerde actiehistorie voor de Undo-functionaliteit per ordernummer
action_history = []

VALID_STATUSES = ('queued', 'preparing', 'pending', 'done', 'picked_up')


def record_action(order, from_status, to_status):
    """Record a status transition for the global undo feature."""
    global action_history
    # Don't record new-order creation for undo
    if from_status is None and to_status == 'preparing':
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


def fill_pending():
    """Promote queued orders to pending while kitchen slots are free."""
    capacity = order_data['kitchen_capacity']
    for n in order_data['order_queue']:
        if count_in_state('pending') >= capacity:
            break
        if order_data['orders'][n].get('status') == 'queued':
            order_data['orders'][n]['status'] = 'pending'
            order_data['orders'][n]['updated_at'] = datetime.now().isoformat()


def enforce_capacity():
    """Demote pending orders back to queued if capacity is exceeded."""
    capacity = order_data['kitchen_capacity']
    while count_in_state('pending') > capacity:
        demoted = None
        for n in reversed(order_data['order_queue']):
            if order_data['orders'][n].get('status') == 'pending':
                demoted = n
                break
        if demoted is None:
            break
        order_data['orders'][demoted]['status'] = 'queued'
        order_data['orders'][demoted]['updated_at'] = datetime.now().isoformat()


def get_current_state():
    """Build the current state response for API."""
    return {
        'preparing': orders_in_state('preparing'),
        'pending': orders_in_state('pending'),
        'done': orders_in_state('done'),
        'queued': orders_in_state('queued'),
        'picked_up': orders_in_state('picked_up'),
        'kitchen_capacity': order_data['kitchen_capacity'],
        'pos_connected': order_data['pos_connected'],
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
        status = data.get('status', 'preparing')
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
                # Determine the initial status. New orders always start as
                # 'preparing' (bestelling) and only become 'pending' (being made)
                # when the input page promotes them.
                if status in ('ready', 'done'):
                    new_status = 'done'
                elif status == 'pending':
                    new_status = 'pending'
                else:
                    new_status = 'preparing'

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


@app.route('/api/orders/<order>/pending', methods=['PUT'])
def move_to_pending(order):
    """Move an order to pending (being made). Used by the input page col 1 -> col 2."""
    order = order.upper()
    if order in order_data['orders']:
        old = order_data['orders'][order]['status']
        record_action(order, old, 'pending')
        order_data['orders'][order]['status'] = 'pending'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        # If it was queued, fill any remaining kitchen slots
        fill_pending()
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
        # Freeing a slot lets the next queued order move to pending
        if old in ('pending', 'queued'):
            fill_pending()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>/done', methods=['PUT'])
def mark_done(order):
    """Kitchen tap: pending -> done."""
    order = order.upper()
    if order in order_data['orders'] and order_data['orders'][order]['status'] == 'pending':
        record_action(order, 'pending', 'done')
        order_data['orders'][order]['status'] = 'done'
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        # Freeing a slot lets the next queued order move to pending
        fill_pending()
        save_orders()
    return jsonify(get_current_state())


@app.route('/api/orders/<order>/undo', methods=['PUT'])
def undo_done(order):
    """Undo a done order within the kitchen 5s grace period: move it back to pending."""
    order = order.upper()
    if order in order_data['orders'] and order_data['orders'][order]['status'] == 'done':
        record_action(order, 'done', 'pending')
        order_data['orders'][order]['status'] = 'pending'
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
    # Removing a pending order frees a slot for the next queued order
    fill_pending()
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

    # Block rule: don't undo pending -> preparing
    if from_status == 'pending' and to_status == 'preparing':
        action_history.append(last_action)
        return jsonify(get_current_state())

    if to_status == 'deleted':
        target = from_status if from_status in VALID_STATUSES else 'done'
    else:
        target = from_status if from_status in VALID_STATUSES else 'preparing'

    if order in order_data['orders']:
        order_data['orders'][order]['status'] = target
        order_data['orders'][order]['updated_at'] = datetime.now().isoformat()
        if target == 'pending':
            enforce_capacity()
        else:
            fill_pending()
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
    fill_pending()
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