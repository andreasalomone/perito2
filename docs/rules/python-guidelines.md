---
description: 
globs: *.py
alwaysApply: false
---
# Python Coding Guidelines

*   **PEP 8 Compliance:**
    *   **Principle:** Adhere to PEP 8, the official style guide for Python code.
    *   **Application:** Ensure code is formatted according to PEP 8 for readability and consistency (e.g., line length, indentation, naming conventions for variables, functions, classes). Use linters and formatters like Black or Flake8.

*   **Type Hinting (PEP 484):**
    *   **Principle:** Use type hints to improve code clarity, catch errors early, and enhance tooling support.
    *   **Application:** Add type hints to function signatures and variable declarations where appropriate. Use the `typing` module for complex types.
    *   **Strict Type Checking:** Enable strict type checking in mypy configuration with the following settings:
        ```
        disallow_untyped_defs = True
        disallow_untyped_calls = True
        ```
        This enforces comprehensive type annotations across the codebase and prevents calling functions without proper type information.

*   **Docstrings (PEP 257):**
    *   **Principle:** Document public modules, functions, classes, and methods using docstrings.
    *   **Application:** Follow a consistent docstring format (e.g., Google style, reStructuredText, NumPy style). Docstrings should explain what the code does, its arguments, what it returns, and any exceptions it might raise.

*   **Modularity and Reusability:**
    *   **Principle:** Design functions and classes to be modular and reusable, adhering to SRP.
    *   **Application:** Break down complex logic into smaller, well-defined functions. Group related functionality into modules and packages. Avoid circular dependencies.

*   **Error Handling:**
    *   **Principle:** Implement robust error handling using specific exceptions.
    *   **Application:** Use `try-except` blocks to handle potential errors gracefully. Catch specific exceptions rather than generic `Exception`. Define custom exceptions for application-specific errors when necessary.

*   **List Comprehensions and Generators:**
    *   **Principle:** Prefer list comprehensions for creating lists and generators for large datasets to improve readability and efficiency.
    *   **Application:** Use list comprehensions for concise list creation from iterables. Use generator expressions or generator functions for memory-efficient iteration over large sequences.

*   **Context Managers (`with` statement):**
    *   **Principle:** Use context managers for resource management (e.g., files, network connections, locks).
    *   **Application:** Employ the `with` statement to ensure resources are properly acquired and released, even if errors occur. Implement custom context managers using `__enter__` and `__exit__` methods if needed.

*   **Immutability:**
    *   **Principle:** Prefer immutable data structures where possible to prevent unintended side effects.
    *   **Application:** Use tuples instead of lists for fixed collections. Be mindful of mutating objects passed as arguments unless that is the explicit intent. 