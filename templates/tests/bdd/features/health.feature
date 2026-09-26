Feature: Service health
  Scenario: Service is healthy
    When the client requests the health endpoint
    Then the response status is 200
