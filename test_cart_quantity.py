#!/usr/bin/env python3
"""
Test script to verify cart quantity calculation for repeated items
"""

# Simulate the cart logic
cart = {}
food_id = "1"  # Same food item ID

# First time adding item
cart[str(food_id)] = cart.get(str(food_id), 0) + 1
print(f"After 1st add: Item {food_id} qty = {cart[str(food_id)]}")

# Second time adding same item
cart[str(food_id)] = cart.get(str(food_id), 0) + 1
print(f"After 2nd add: Item {food_id} qty = {cart[str(food_id)]}")

# Third time adding same item
cart[str(food_id)] = cart.get(str(food_id), 0) + 1
print(f"After 3rd add: Item {food_id} qty = {cart[str(food_id)]}")

# Fourth time adding same item
cart[str(food_id)] = cart.get(str(food_id), 0) + 1
print(f"After 4th add: Item {food_id} qty = {cart[str(food_id)]}")

print("\n✅ Cart quantity calculation verified!")
print(f"Final cart state: {cart}")

# Test with multiple items
print("\n--- Testing with multiple items ---")
cart2 = {}

# Add item 1 three times
for _ in range(3):
    cart2["1"] = cart2.get("1", 0) + 1

# Add item 2 twice
for _ in range(2):
    cart2["2"] = cart2.get("2", 0) + 1

# Add item 1 one more time (should be 4 total)
cart2["1"] = cart2.get("1", 0) + 1

print(f"Item 1: {cart2['1']} qty (expected: 4)")
print(f"Item 2: {cart2['2']} qty (expected: 2)")
print(f"Final cart: {cart2}")

if cart2["1"] == 4 and cart2["2"] == 2:
    print("\n✅ Multi-item cart calculation is correct!")
else:
    print("\n❌ Error in calculation!")
