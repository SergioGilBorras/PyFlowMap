class Vehicle:
    def operate(self, minutes):
        if minutes <= 0:
            return 'idle'
        return self.engage(minutes)

    def engage(self, minutes):
        return minutes

class ElectricVan(Vehicle):
    def engage(self, minutes):
        if minutes > 100:
            raise ValueError('battery')
        return minutes // 2

    def operate(self, minutes):
        return super().operate(minutes)
