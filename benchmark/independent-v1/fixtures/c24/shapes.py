class Circle:
    __match_args__ = ('radius',)
    def __init__(self, radius):
        self.radius = radius

class Rectangle:
    __match_args__ = ('width', 'height')
    def __init__(self, width, height):
        self.width, self.height = width, height

def classify(shape):
    match shape:
        case Circle(r) if r > 0:
            return 'round'
        case Rectangle(w, h) if w == h:
            return 'square'
        case Circle(_) | Rectangle(_, _):
            return 'other'
        case _:
            return 'unknown'
