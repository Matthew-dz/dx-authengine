import casbin

enforcer = casbin.Enforcer("casbin_config/model.conf", "casbin_config/policy.csv")

def custom_float(*args):
    if len(args) == 1:
        return float(args[0])
    return float(args[0])

# Just trying built-in float
try:
    enforcer.add_function("float", float)
    print("add_function success with built-in float")
except Exception as e:
    print("Failed with built-in:", e)

class Subject:
    def __init__(self, username, role):
        self.username = username
        self.role = role

class Resource:
    def __init__(self, name, order_days_old):
        self.name = name
        self.order_days_old = order_days_old

res = enforcer.enforce(Subject("bob", "staff_sales"), Resource("transaction", 10.0), "refund")
print("Enforce result 10.0:", res)

res2 = enforcer.enforce(Subject("bob", "staff_sales"), Resource("transaction", 40.0), "refund")
print("Enforce result 40.0:", res2)
