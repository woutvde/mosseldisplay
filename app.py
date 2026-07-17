from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# In-memory database tracking order states and theme configurations
order_data = {
    "preparing": [],
    "ready": [],
    "pos_connected": False,
    "display_theme": "dark"  # Default global display theme state
}

@app.route('/')
@app.route('/input')
def input_page():
    return render_template('input.html')

@app.route('/display')
def display_page():
    return render_template('display.html')

# --- API Endpoints ---

@app.route('/api/orders', methods=['GET', 'POST'])
def handle_orders():
    global order_data
    if request.method == 'POST':
        data = request.get_json() or {}
        # Normalize order numbers to uppercase to ensure POS letters and keypad letters match perfectly
        order = str(data.get('order', '')).strip().upper()
        status = data.get('status', 'preparing')
        source = data.get('source', '')
        
        if source == 'pos':
            order_data['pos_connected'] = True
            
        # Changed .isdigit() to .isalnum() to support formats like a493, b39, c39
        if order and order.isalnum():
            if order in order_data['preparing']:
                order_data['preparing'].remove(order)
            if order in order_data['ready']:
                order_data['ready'].remove(order)
                
            if status == 'ready':
                order_data['ready'].append(order)
            else:
                order_data['preparing'].append(order)
                
        return jsonify(order_data)
        
    return jsonify(order_data)

@app.route('/api/orders/<order>/ready', methods=['PUT'])
def move_to_ready(order):
    global order_data
    order = order.upper()  # Enforce case safety
    if order in order_data['preparing']:
        order_data['preparing'].remove(order)
        if order not in order_data['ready']:
            order_data['ready'].append(order)
    return jsonify(order_data)

@app.route('/api/orders/<order>', methods=['DELETE'])
def delete_order(order):
    global order_data
    order = order.upper()  # Enforce case safety
    if order in order_data['preparing']:
        order_data['preparing'].remove(order)
    if order in order_data['ready']:
        order_data['ready'].remove(order)
    return jsonify(order_data)

@app.route('/api/theme', methods=['POST'])
def update_theme():
    global order_data
    data = request.get_json() or {}
    theme = data.get('theme', 'dark')
    if theme in ['dark', 'light']:
        order_data['display_theme'] = theme
    return jsonify(order_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)