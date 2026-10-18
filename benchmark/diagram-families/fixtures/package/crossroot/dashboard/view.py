from payments import charge
from catalog import products

def show():
    return charge.pay() + products.find()
