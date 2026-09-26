from locust import HttpUser, between, task

class DefaultUser(HttpUser):
    # A small think time models users without maximizing raw RPS by accident.
    wait_time = between(0.5, 1.5)

    @task(10)
    def health(self):
        with self.client.get("/health", name="GET /health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")

    # Add weighted public user journeys here, for example:
    #
    # @task(3)
    # def list_resources(self):
    #     self.client.get("/v1/resources", name="GET /v1/resources")
