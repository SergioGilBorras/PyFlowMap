"""No filesystem or external context access."""
class StaticContextAdapter:
    def get_context(self, name):
        return {"name": name, "synthetic": True}
