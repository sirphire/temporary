import requests


class SheetWebApp:
    def __init__(self, webapp_url: str):
        self.webapp_url = webapp_url.strip()

    def post(self, action: str, payload: dict | None = None):
        if not self.webapp_url:
            raise ValueError("Google Sheet Web App URL missing hai.")

        data = {"action": action}
        if payload:
            data.update(payload)

        response = requests.post(self.webapp_url, json=data, timeout=120)
        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(result.get("error", "Unknown sheet error"))

        return result

    def setup(self):
        return self.post("setup")

    def add_products(self, category_url: str, products: list[dict]):
        return self.post("add_products", {"category_url": category_url, "products": products})

    def claim_batch(self, category_url: str, batch_size: int):
        return self.post("claim_batch", {"category_url": category_url, "batch_size": batch_size})

    def update_results(self, results: list[dict]):
        return self.post("update_results", {"results": results})

    def reset_stuck(self):
        return self.post("reset_stuck")

    def stats(self, category_url: str = ""):
        return self.post("stats", {"category_url": category_url})

    def records(self, category_url: str = "", limit: int = 500):
        return self.post("records", {"category_url": category_url, "limit": limit})
