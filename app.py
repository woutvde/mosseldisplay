from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# In-memory storage for active orders. 
# Note: For this to work reliably behind Nginx with Gunicorn, 
# you must run Gunicorn with a single worker (--workers 1).
ready_orders = []

@app.route('/')
def index():
    return render_template('input.html')

@app.route('/input')
def input_page():
    return render_template('input.html')

@app.route('/display')
def display_page():
    return render_template('display.html')

# --- API Endpoints ---

@app.route('/api/orders', methods=['GET', 'POST'])
def handle_orders():
    if request.method == 'POST':
        data = request.json
        order = str(data.get('order')).strip()
        
        # Add order if valid and not already in the list
        if order and order.isdigit() and order not in ready_orders:
            ready_orders.append(order)
            
        return jsonify(ready_orders)
    
    # GET request returns the current list
    return jsonify(ready_orders)

@app.route('/api/orders/<order>', methods=['DELETE'])
def delete_order(order):
    if order in ready_orders:
        ready_orders.remove(order)
    return jsonify(ready_orders)

if __name__ == '__main__':
    # Run accessible on local network
    app.run(host='0.0.0.0', port=5000)