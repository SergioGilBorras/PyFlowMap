"""No inference is performed by this invented adapter."""
class OfflineTextAdapter:
    def complete(self, prompt):
        return "synthetic"
