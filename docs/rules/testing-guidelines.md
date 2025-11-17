---
description: 
globs: tests/
alwaysApply: false
---
# Testing Guidelines for Report AI Project

## 1. Introduction

This document outlines the testing philosophy, strategies, and best practices to be followed for the Report AI project. Adhering to these guidelines will help ensure code correctness, reliability, robustness, and maintainability, aligning with our general coding principles (SOLID, KISS, DRY, etc.).

Effective testing is crucial for iterative development, allowing us to build features confidently and refactor existing code with a safety net.

## 2. Core Testing Principles (Inspired by `@coding-guidelines.mdc`)

*   **Test Thoroughly at Multiple Levels:** (Ref: Development Workflow & Quality Assurance)
    *   We will employ a mix of unit, integration, and end-to-end tests to cover different aspects of the application.
*   **Test Early, Test Often:** (Ref: Development Workflow & Quality Assurance)
    *   Testing should be an integral part of the development lifecycle, not an afterthought. Write tests as you write code, or even before (TDD if applicable).
*   **Focus on Readability and Maintainability:** (Ref: Code Readability and Maintainability)
    *   Tests are code too. They should be clear, concise, and easy to understand. Well-named tests and clear assertion messages are vital.
*   **Tests Should Be Fast and Reliable:**
    *   Unit tests, in particular, should execute quickly to provide rapid feedback.
    *   Avoid flaky tests (tests that pass or fail inconsistently without code changes). Investigate and fix flakiness immediately.
*   **SRP for Tests:**
    *   Each test method should ideally focus on testing one specific aspect, behavior, or condition of the unit under test.
*   **DRY in Tests (Use with Caution):**
    *   While DRY is important, prioritize test readability and isolation. Some repetition in test setup might be acceptable if it makes individual tests clearer. Use helper functions or fixtures for common setup/teardown logic judiciously.

## 3. Types of Tests and Scope

### 3.1. Unit Tests

*   **Goal:** Verify the smallest pieces of code (functions, methods, or classes) in isolation.
*   **Location:** `tests/unit/`
*   **Key Characteristics:**
    *   **Isolation:** Dependencies (other classes, services, network calls, file system) MUST be mocked or stubbed.
    *   **Speed:** Should be very fast to execute.
    *   **Scope:** Focus on a single unit's logic, including edge cases, error conditions, and valid inputs/outputs.
*   **What to Test (Examples for this project):**
    *   Service logic (e.g., `ClarificationService.identify_missing_fields`, methods in `PipelineService`, `LLMService` wrappers).
    *   Helper/utility functions.
    *   Logic within API route handlers (mocking service calls).
    *   Pydantic model validation (though Pydantic handles much of this, test custom validators or complex field interactions).

### 3.2. Integration Tests

*   **Goal:** Verify the interaction between several components or services.
*   **Location:** `tests/integration/` (Create if it doesn't exist, or can be part of `tests/e2e/` if the distinction is minor for now).
*   **Key Characteristics:**
    *   May involve real instances of some services but might still mock external systems (e.g., actual LLM APIs, Supabase in a controlled manner).
    *   Slower than unit tests but faster than full E2E tests.
*   **What to Test (Examples for this project):**
    *   API endpoint full flow: Request -> Route Handler -> Service Call -> Response (mocking only the outermost dependencies like LLM provider API calls).
    *   Interaction between `PipelineService` and the services it orchestrates (if applicable).
    *   RAG service integration with embedding models and vector stores (if using a test/local vector store).

### 3.3. End-to-End (E2E) Tests

*   **Goal:** Simulate real user scenarios and test the entire application flow from the UI (if applicable) to the backend and back.
*   **Location:** `tests/e2e/`
*   **Key Characteristics:**
    *   Uses real instances of most services, potentially interacting with live (test/staging) external dependencies or carefully controlled local versions (e.g., local LLM, test database).
    *   Slowest to run but provide the highest confidence in the overall system.
    *   More prone to flakiness due to the number of moving parts.
*   **What to Test (Examples for this project):**
    *   Full report generation via API: Uploading files, triggering `/api/generate`, handling clarification (if any), and verifying the final DOCX (content structure or key elements).
    *   If UI testing tools are used (e.g., Playwright, Selenium): User interaction with the frontend form, submitting, and receiving the report.

## 4. Test Naming and Structure

*   **File Naming:** `test_<module_name>.py` (e.g., `test_clarification_service.py`, `test_routes.py`).
*   **Function/Method Naming:** `test_<condition_or_behavior>_<expected_outcome>()`.
    *   Be descriptive. Examples:
        *   `test_identify_missing_fields_when_critical_field_is_none()`
        *   `test_generate_route_returns_clarification_needed_for_missing_polizza()`
        *   `test_upload_invalid_file_type_returns_400_error()`
*   **Arrange-Act-Assert (AAA) Pattern:** Structure your tests clearly:
    1.  **Arrange:** Set up preconditions, initialize objects, prepare mock data.
    2.  **Act:** Execute the code under test.
    3.  **Assert:** Verify the outcome against expectations.

```python
# Example (Conceptual)
def test_calculate_total_with_positive_numbers():
    # Arrange
    calculator = Calculator()
    num1 = 5
    num2 = 10
    expected_sum = 15

    # Act
    actual_sum = calculator.add(num1, num2)

    # Assert
    assert actual_sum == expected_sum
```

## 5. Best Practices & What to Do

*   **Write Tests for All New Code:** Any new function, class, or significant logic branch should have corresponding tests.
*   **Test for Expected Failures:** Don't just test the "happy path." Test how your code handles errors, invalid input, and edge cases. Use `pytest.raises` for testing exceptions.
*   **Use Mocks/Stubs Appropriately (Unit Tests):**
    *   Mock dependencies to isolate the unit under test.
    *   Use `unittest.mock.patch`, `MagicMock`, `AsyncMock`.
    *   Ensure mocks are configured to simulate realistic behavior of the dependency, including return values and side effects if necessary.
*   **Use Fixtures for Setup/Teardown (`pytest`):**
    *   Use `@pytest.fixture` to create reusable setup code (e.g., service instances, test data, mock objects).
    *   Define fixtures in `conftest.py` for project-wide availability or at the top of test files for local use.
*   **Keep Tests Independent:** Each test should be able to run independently and in any order. Avoid tests that depend on the state set by a previous test.
*   **Test Asynchronously Correctly (`pytest-asyncio`):**
    *   Mark async test functions with `@pytest.mark.asyncio`.
    *   Use `AsyncMock` for mocking async functions/methods.
*   **Aim for High Test Coverage:** While 100% isn't always pragmatic, strive for high coverage (e.g., the project's 80% target) of critical logic. Use coverage tools (`pytest-cov`) to identify untested code paths.
*   **Refactor Tests Too:** As production code evolves, tests may need refactoring to remain clear, maintainable, and relevant.
*   **Run Tests Frequently:** Integrate tests into your local development workflow and CI/CD pipeline.

## 6. What Not to Do

*   **Don't Test Trivial Code:** Avoid testing language features or basic library functions (e.g., simple getters/setters that just return a value without logic).
*   **Don't Write Overly Complex Mocks:** If a mock setup becomes extremely convoluted, it might indicate the unit under test is doing too much (violating SRP) or that an integration test is more appropriate.
*   **Don't Rely on Implementation Details:** Test the public interface/behavior of a unit, not its internal private methods (unless those methods are complex enough to warrant their own unit tests, though this is rarer for truly private methods).
*   **Don't Introduce Flakiness:** Avoid tests that depend on timing, external system availability (for unit tests), or random data without proper control.
*   **Don't Ignore Failing Tests:** A failing test indicates a problem. Fix the code or the test. Don't comment out failing tests to make the suite pass.
*   **Don't Test Multiple Things in One Test Function:** Keep tests focused on a single piece of behavior for clarity on failure.
*   **Don't Forget to Test Error Paths:** Ensure your code handles exceptions and invalid states gracefully.

## 7. Tools and Setup

*   **Framework:** `pytest`
*   **Mocking:** `unittest.mock` (standard library), `pytest-mock` (provides `mocker` fixture)
*   **Asynchronous Testing:** `pytest-asyncio`
*   **Coverage:** `pytest-cov`
*   **Test Client (FastAPI):** `fastapi.testclient.TestClient`

Ensure these are in your `requirements-dev.txt` and your `pytest.ini` is configured for coverage reporting and any other project-specific settings (like markers or asyncio mode).

## 8. Running Tests

*   **Run all tests:**
    ```bash
    # (Activate your virtual environment first: source .venv/bin/activate)
    # (Navigate to the root directory: cd report-ai)
    pytest
    ```
*   **Run tests for a specific file:**
    ```bash
    pytest tests/unit/test_my_module.py
    ```
*   **Run a specific test function:**
    ```bash
    pytest tests/unit/test_my_module.py::test_my_specific_function
    ```
*   **View coverage report (as configured in `pytest.ini`):**
    Coverage will typically be printed to the terminal. An HTML report can also be generated for more detailed analysis (e.g., `pytest --cov-report=html`).

## 9. Pre-commit Hook for Tests

Consider adding a `pre-commit` hook to run tests automatically before commits. This helps catch issues early.

```yaml
# In .pre-commit-config.yaml
-   repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest # Or a script that activates venv and runs pytest
        language: system # Or python, if pytest is in the venv path and pre-commit uses it
        types: [python]
        pass_filenames: false
        # stages: [commit] # Optional: to run only on commit
```
Ensure the `entry` and `language` are configured correctly for your project's environment setup.

---

By following these guidelines, we can build a high-quality, resilient Report AI application.