# Test layer selection

Use the cheapest layer that verifies the public requirement.

1. CLI contract -> pytest/subprocess.
2. HTTP behavior -> pytest/httpx or Hurl.
3. API schema robustness -> Schemathesis.
4. Business-readable executable specification -> pytest-bdd.
5. Browser behavior -> Playwright.
6. Accessibility rule automation -> axe + Playwright.
7. Mobile UI -> Appium.
8. gRPC -> grpcio public client.
9. Performance SLO/threshold -> k6.
10. DAST baseline -> OWASP ZAP.

Do not duplicate the same assertion across every layer. Cross-interface tests are valuable only
where multiple public interfaces must observe the same state.
