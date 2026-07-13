import tkinter as tk

class OrderTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Personeel Invoer - Bestellingen Tracker")
        # Scaled up for 1080p
        self.root.geometry("1920x1080") 
        self.root.configure(bg="#f0f0f0")

        # List to store all currently ready orders
        self.ready_orders = []

        # --- 1. Main Layout Frames ---
        # Left side for active orders
        self.left_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=50, pady=50)

        # Right side for input and numpad
        self.right_frame = tk.Frame(self.root, bg="#e8e8e8", bd=2, relief="groove")
        self.right_frame.pack(side="right", fill="y", padx=50, pady=50, ipadx=40)

        # --- 2. Right Side: Entry & Numpad Setup ---
        
        # Validation rule so the entry box ONLY accepts numbers
        vcmd = (self.root.register(self.validate_number), '%P')
        
        tk.Label(self.right_frame, text="Bestelling nummer klaar:", font=("Helvetica", 28, "bold"), 
                 bg="#e8e8e8", fg="#333").pack(pady=(40, 10))

        # Massively increased entry font size
        self.entry = tk.Entry(self.right_frame, font=("Helvetica", 64), justify="center", 
                              validate="key", validatecommand=vcmd, width=8)
        self.entry.pack(pady=20, padx=30)
        self.entry.bind("<Return>", self.add_order)

        # Touchscreen Numpad
        self.numpad_frame = tk.Frame(self.right_frame, bg="#e8e8e8")
        self.numpad_frame.pack(pady=30)

        # Layout for the numpad buttons: (Text, Row, Column)
        numpad_layout = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('C', 3, 0), ('0', 3, 1), ('Enter', 3, 2)
        ]

        for (text, row, col) in numpad_layout:
            if text == 'Enter':
                cmd = self.add_order
                bg_color = "#99ff99" # Light green
            elif text == 'C':
                cmd = self.clear_entry
                bg_color = "#ff9999" # Light red
            else:
                # Use a lambda with a default argument to capture the current number
                cmd = lambda t=text: self.numpad_insert(t)
                bg_color = "#ffffff" # White

            # Increased numpad font size for larger buttons
            btn = tk.Button(self.numpad_frame, text=text, font=("Helvetica", 36, "bold"),
                            bg=bg_color, fg="black", width=4, height=2, cursor="hand2",
                            relief="raised", command=cmd)
            btn.grid(row=row, column=col, padx=12, pady=12)

        # --- 3. Left Side: Active Orders Setup ---
        tk.Label(self.left_frame, text="Klik op een bestelnummer hieronder om het te verwijderen:", 
                 font=("Helvetica", 24, "bold"), bg="#f0f0f0", fg="#333").pack(anchor="w", pady=(0, 30))

        # Container frame for the staff's clickable orders
        self.staff_orders_frame = tk.Frame(self.left_frame, bg="#f0f0f0")
        self.staff_orders_frame.pack(fill="both", expand=True)

        # --- 4. Customer Display Window Setup ---
        self.display_window = tk.Toplevel(self.root)
        self.display_window.title("Klantenscherm - Klaar om op te halen")
        # Scaled customer display to 1080p as well
        self.display_window.geometry("1920x1080")
        self.display_window.configure(bg="black")

        # Header for the customer screen
        tk.Label(self.display_window, text="DEZE BESTELLINGEN ZIJN KLAAR OM OP TE HALEN", 
                 font=("Helvetica", 48, "bold"), bg="black", fg="white").pack(pady=40)

        # Container frame for the big customer order numbers
        self.customer_orders_frame = tk.Frame(self.display_window, bg="black")
        self.customer_orders_frame.pack(fill="both", expand=True, padx=40, pady=40)

    # --- Numpad Helper Functions ---
    def numpad_insert(self, text):
        self.entry.insert(tk.END, text)

    def clear_entry(self):
        self.entry.delete(0, tk.END)

    def validate_number(self, text):
        # Allow backspacing (empty string) or digits only
        if text == "" or text.isdigit():
            return True
        return False

    def add_order(self, event=None):
        order_num = self.entry.get()
        
        # Only add if it's not empty and not already on the screen
        if order_num and order_num not in self.ready_orders:
            self.ready_orders.append(order_num)
            self.refresh_displays()
            
        # Clear the input box ready for the next number
        self.clear_entry()

    def remove_order(self, order_num):
        # Remove the specific order from the list and update the screens
        if order_num in self.ready_orders:
            self.ready_orders.remove(order_num)
            self.refresh_displays()

    def refresh_displays(self):
        # 1. Clear all current widgets in both frames
        for widget in self.staff_orders_frame.winfo_children():
            widget.destroy()
        for widget in self.customer_orders_frame.winfo_children():
            widget.destroy()

        # 2. Rebuild the grids based on the current list of ready orders
        staff_cols = 5      # Show 5 numbers per row on the wider left screen
        customer_cols = 4   # Show 4 numbers per row on the big screen

        for i, order in enumerate(self.ready_orders):
            # Calculate grid position (row and column)
            staff_row, staff_col = i // staff_cols, i % staff_cols
            cust_row, cust_col = i // customer_cols, i % customer_cols

            # Increased font size for the active order buttons on staff screen
            btn = tk.Button(self.staff_orders_frame, text=order, font=("Helvetica", 36, "bold"),
                            bg="#ffcccc", fg="black", cursor="hand2", relief="raised",
                            command=lambda o=order: self.remove_order(o))
            btn.grid(row=staff_row, column=staff_col, padx=15, pady=15, sticky="nsew")

            # Scaled up massive text label for the customer screen
            lbl = tk.Label(self.customer_orders_frame, text=order, font=("Helvetica", 150, "bold"),
                           bg="black", fg="yellow")
            lbl.grid(row=cust_row, column=cust_col, padx=30, pady=30, sticky="nsew")

        # 3. Configure grid weights so the numbers space out evenly
        for c in range(staff_cols):
            self.staff_orders_frame.grid_columnconfigure(c, weight=1)
        for c in range(customer_cols):
            self.customer_orders_frame.grid_columnconfigure(c, weight=1)

if __name__ == "__main__":
    root = tk.Tk()
    app = OrderTrackerApp(root)
    app.entry.focus_set() 
    root.mainloop()