"""No HTTP calls: fixed test-only responses."""
class LocalSearchAdapter:
    def search(self, query):
        return [{"title": "synthetic", "query": query}]
