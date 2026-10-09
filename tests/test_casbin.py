from app.agent import check_abac_policy

print("Testing casbin...")
result = check_abac_policy("bob", "transaction", "refund", 15)
print("Result:", result)
