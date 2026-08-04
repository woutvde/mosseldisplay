#!/bin/bash

# Base URL of your Flask app (adjust if needed)
BASE_URL="http://localhost:5000/api/orders"

# Realistic menu items
MENU_ITEMS=(
    "Mosselen natuur"
    "Mosselen speciaal"
    "Vegetarische snack"
    "Friet groot"
    "Friet klein"
    "Frikandel"
)

# Sample order formats (AXX and BXX, XX being numbers)
ORDERS=("A01" "A02" "A03" "A04" "A05" "B01" "B02" "B03" "B04" "B05")

echo "Generating test orders with menu items..."
echo "=========================================="

for i in "${!ORDERS[@]}"; do
    ORDER=${ORDERS[$i]}

    # Generate 1-3 random items per order
    NUM_ITEMS=$((RANDOM % 3 + 1))
    ITEMS="["
    for j in $(seq 1 $NUM_ITEMS); do
        ITEM_INDEX=$((RANDOM % ${#MENU_ITEMS[@]}))
        ITEM=${MENU_ITEMS[$ITEM_INDEX]}
        QTY=$((RANDOM % 3 + 1))
        PRICE=$((RANDOM % 2000 + 500))

        if (( j > 1 )); then
            ITEMS+=","
        fi
        ITEMS+="{\"name\":\"$ITEM\",\"qty\":$QTY,\"price\":$PRICE}"
    done
    ITEMS+="]"

    # Build the full order payload (status preparing -> kitchen decides)
    PAYLOAD=$(cat <<EOF
{
    "order": "$ORDER",
    "status": "preparing",
    "source": "test",
    "order_details": {
        "ticket": "T$ORDER",
        "items": $ITEMS,
        "customer": "Test Customer $((i+1))",
        "table": "$((RANDOM % 10 + 1))"
    }
}
EOF
    )

    # Send POST request and capture full response
    RESPONSE=$(curl -s -X POST "$BASE_URL" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD")

    if echo "$RESPONSE" | jq -e . >/dev/null 2>&1; then
        PREP_COUNT=$(echo "$RESPONSE" | jq -r '.preparing | length // 0')
        QUEUED_COUNT=$(echo "$RESPONSE" | jq -r '.queued | length // 0')
        echo "[$((i+1))] Order: $ORDER | Items: $NUM_ITEMS | Preparing: $PREP_COUNT | Queued: $QUEUED_COUNT"
    else
        echo "[$((i+1))] Order: $ORDER | Items: $NUM_ITEMS | ERROR: Invalid response"
        echo "  Response: $RESPONSE"
    fi

    sleep 0.3
done

echo ""
echo "=========================================="
echo "Done! Check your kitchen/display pages to see the orders."
echo "Orders file: $(pwd)/orders.json"
echo ""
echo "To mark an order done from the kitchen (frees a slot):"
echo "  curl -X PUT $BASE_URL/<order>/done"
echo ""
echo "To mark an order picked up from the input page:"
echo "  curl -X PUT $BASE_URL/<order>/pickup"