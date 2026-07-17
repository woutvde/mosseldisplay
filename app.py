from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# In-memory storage for splitting order tracking states
order_data = {
    "preparing": [],
    "ready": [],
    "pos_connected": False
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
        order = str(data.get('order', '')).strip()
        status = data.get('status', 'preparing')  # Default status for new orders
        source = data.get('source', '')
        
        # If order comes from the POS API, lock the numpad out
        if source == 'pos':
            order_data['pos_connected'] = True
            
        if order and order.isdigit():
            # Clean up duplicates across both lists first
            if order in order_data['preparing']:
                order_data['preparing'].remove(order)
            if order in order_data['ready']:
                order_data['ready'].remove(order)
                
            # Place order into the appropriate channel
            if status == 'ready':
                order_data['ready'].append(order)
            else:
                order_data['preparing'].append(order)
                
        return jsonify(order_data)
        
    return jsonify(order_data)

@app.route('/api/orders/<order>/ready', methods=['PUT'])
def move_to_ready(order):
    global order_data
    if order in order_data['preparing']:
        order_data['preparing'].remove(order)
        if order not in order_data['ready']:
            order_data['ready'].append(order)
    return jsonify(order_data)

@app.route('/api/orders/<order>', methods=['DELETE'])
def delete_order(order):
    global order_data
    if order in order_data['preparing']:
        order_data['preparing'].remove(order)
    if order in order_data['ready']:
        order_data['ready'].remove(order)
    return jsonify(order_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)