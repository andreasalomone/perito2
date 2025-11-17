---
description: 
globs: 
alwaysApply: true
---
*   **SOLID Principles:**
    *   **SRP (Single Responsibility Principle):**
        *   Each module, class, or function should have one, and only one, reason to change. This enhances maintainability, testability, and reduces the impact of changes.
        *   New services/modules will handle highly specific tasks (e.g., a `MissingInfoDetectorService` focuses solely on identifying missing information, while a `SectionRevisionService` handles text revisions).
        *   API endpoints will be granular, meaning each endpoint should correspond to a distinct operation or resource (e.g., `/api/detect-missing-info` vs. `/api/revise-section/{section_id}`).
    *   **OCP (Open/Closed Principle):**
        *   Software entities (classes, modules, functions, etc.) should be open for extension but closed for modification. This means you should be able to add new functionality without changing existing, tested code.
        *   Achieve this through mechanisms like strategy patterns, plugin architectures, or configuration-driven features. For instance, new "clarification types" or "AI editing actions" should be implementable by adding new strategy classes or plugins that conform to a defined interface, without altering the core processing logic.
    *   **LSP (Liskov Substitution Principle):** (Added for completeness)
        *   Subtypes must be substitutable for their base types without altering the correctness of the program. If you have a class `BaseLLMProvider` and a subclass `OpenAIProvider`, any code using `BaseLLMProvider` should work correctly if an `OpenAIProvider` instance is passed.
        *   Ensure derived classes honor the contracts of their base classes (e.g., method signatures, exceptions thrown, pre/post-conditions).
    *   **ISP (Interface Segregation Principle):** (Added for completeness)
        *   Clients should not be forced to depend on interfaces they do not use. Create fine-grained interfaces specific to client needs rather than large, general-purpose interfaces.
        *   For example, if a service only needs to *read* data, it should depend on a `ReadableDataStore` interface, not a generic `DataStore` interface that also includes write methods.
    *   **DIP (Dependency Inversion Principle):**
        *   High-level modules should not depend on low-level modules. Both should depend on abstractions (e.g., interfaces). Abstractions should not depend on details. Details (concrete implementations) should depend on abstractions.
        *   Continue to rely on abstractions (interfaces or abstract classes) for LLM interactions (e.g., an `ILLMService` interface) and other external services. This allows for flexibility (e.g., swapping LLM providers) and improves testability by enabling mocking of dependencies.

*   **KISS (Keep It Simple, Stupid):**
    *   Prioritize simplicity in design and implementation. Start with the most straightforward solution that meets the current requirements. Avoid unnecessary complexity and premature optimization.
    *   For "Missing Info" detection, the initial focus should be on explicitly empty, null, or placeholder values returned by the LLM (e.g., "\[TBD]", "\[PENDING]", "\[INFO NEEDED]"). More sophisticated semantic analysis can be added later if required.
    *   For "Preview & Edit" functionality, begin with a simple text area for direct user input and display of LLM-generated content. Advanced AI-driven interactions (e.g., AI-suggested rewrites, grammar correction, style adaptation) can be incrementally introduced.

*   **DRY (Don't Repeat Yourself):**
    *   Every piece of knowledge or logic must have a single, unambiguous, authoritative representation within a system. Aim to reduce redundancy to improve maintainability, reduce the risk of inconsistencies, and make the codebase easier to understand.
    *   Actively reuse existing components, such as LLM call wrappers (e.g., a class encapsulating retry logic, token counting, and error handling for LLM API calls) and document building utilities like `doc_builder.inject`.
    *   Centralize prompt templates, possibly in dedicated configuration files (e.g., YAML, JSON) or a specific module, to ensure consistency and ease of modification.
    *   Common data structures (e.g., DTOs for API requests/responses, internal models representing document sections) should be defined once and reused.
    *   Create utility functions or helper classes for common, repeated tasks (e.g., text sanitization, date formatting).

*   **YAGNI (You Ain't Gonna Need It):**
    *   **Principle:** Only implement functionality when you actually need it, not when you just foresee that you *might* need it. This helps to avoid over-engineering and unnecessary complexity.
    *   **Application:** Resist the urge to add features or abstractions based on speculation about future requirements. Focus on delivering the current needs efficiently. This complements the KISS principle.

*   **Principle of Least Astonishment (POLA) / Principle of Least Surprise:**
    *   **Principle:** A component of a system should behave in a way that most users/programmers will expect it to behave; that is, they should not be surprised by its behavior.
    *   **Application:** Design APIs, function signatures, and naming conventions to be intuitive. The behavior of your code should be predictable to someone reading it or using it for the first time. Avoid side effects that are not obvious.

*   **Write Code That is Easy to Delete (and Replace):**
    *   **Principle:** Strive to write code in such a way that it's modular and decoupled enough that if a feature or component needs to be removed or significantly changed, it can be done with minimal impact on the rest of the system.
    *   **Application:** This encourages good modular design, clear interfaces, and reduced coupling, aligning well with SOLID principles. Think about how a piece of code could be removed or replaced when you are writing it.

*   **Code Readability and Maintainability (General):**
    *   **Principle:** Code is read far more often than it is written. Prioritize clarity and simplicity in your code to make it easier for others (and your future self) to understand, debug, and maintain.
    *   **Application:** Use consistent naming conventions, clear variable and function names, appropriate comments (explaining *why*, not *what* if the code is self-explanatory), and a logical code structure. Break down complex logic into smaller, digestible functions or methods.

* **Development Workflow & Quality Assurance:**
    *   **Incremental Development & Iteration:**
        *   **Principle:** Tackle one small, well-defined step at a time. Break down complex features into smaller, manageable tasks or user stories.
        *   **Application:** Implement and deliver functionality in small, iterative cycles. This allows for earlier feedback, easier debugging, more focused code reviews, and reduces the risk associated with large, monolithic changes.

    *   **Testing Strategies:**
        *   **Principle:** Test thoroughly at multiple levels to ensure code correctness, reliability, and robustness.
        *   **Application:**
            *   **Unit Tests:** Write unit tests for individual functions, methods, or classes, especially for backend logic, business rules, and critical algorithms. Aim for high unit test coverage.
            *   **Integration Tests:** Verify the interactions between different components, modules, or services.
            *   **End-to-End (E2E) Tests:** Simulate real user scenarios to test the entire application flow from the UI to the backend.
            *   **Manual UI/UX Testing:** For frontend development, supplement automated tests with manual testing to verify visual presentation, usability, and overall user experience. This is particularly important for new features or significant UI changes.
            *   **Test Early, Test Often:** Integrate testing throughout the development lifecycle, not just as a final step.

    *   **Version Control (Git):**
        *   **Principle:** Use version control effectively to track changes, collaborate with others, and manage the codebase history.
        *   **Application:**
            *   **Frequent Commits:** Commit changes frequently with clear, concise, and descriptive messages. Each commit should represent a small, logical unit of work.
            *   **Meaningful Commit Messages:** Follow a consistent convention for commit messages (e.g., Conventional Commits: `feat: add user authentication`, `fix: resolve payment processing error`). This improves history readability and can automate changelog generation.
            *   **Branching Strategy:** Employ a sound branching strategy (e.g., GitFlow, GitHub Flow, or a simpler feature-branch workflow). Develop new features and bug fixes in separate branches to keep the main branch stable.
            *   **Pull/Merge Requests & Code Reviews:** Use pull requests (or merge requests) for merging branches. All code should be reviewed by at least one other developer before being merged into the main development branch. Reviews should focus on correctness, clarity, performance, security, and adherence to coding guidelines.
