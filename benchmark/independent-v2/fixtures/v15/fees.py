class Base:
    def rate(self, value):
        return value
class Discount(Base):
    def rate(self, value):
        return super().rate(value) * 0.8
class Surcharge(Base):
    def rate(self, value):
        return super().rate(value) + 2
class Combined(Discount, Surcharge):
    pass
def calculate_fee(value):
    return Combined().rate(value)
