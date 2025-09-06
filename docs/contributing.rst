Contributing
============

Thank you for your interest in contributing to TwitchAdAvoider! 

This page provides a quick overview of the contribution process. For detailed guidelines,
please see the complete :doc:`CONTRIBUTING` guide in the repository root.

Getting Started
---------------

1. **Fork and clone the repository**
2. **Set up development environment**::

    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate on Windows
    pip install -e .[dev]

3. **Run tests to verify setup**::

    python -m pytest tests/
    black --check .
    flake8 .

Development Workflow
--------------------

1. **Create a feature branch**::

    git checkout -b feature/your-feature-name

2. **Make your changes**
    * Follow code style guidelines
    * Include comprehensive tests
    * Update documentation as needed
    * Ensure security best practices

3. **Test your changes**::

    python -m pytest tests/
    black .
    flake8 .

4. **Commit with clear messages**::

    git commit -m "Add channel name validation with security controls"

5. **Push and create pull request**

Code Standards
--------------

* **Python 3.8+** minimum version
* **PEP 8** style with 100-character line limit
* **Type hints** for all function parameters and returns
* **Docstrings** using Google style for all public functions
* **Security-first** approach with comprehensive input validation

Testing Requirements
--------------------

All contributions must include:

* **Unit tests** for new functionality
* **Security tests** for input validation
* **Integration tests** for component interactions
* **Minimum 90% test coverage** for new code

Documentation
-------------

Update relevant documentation:

* **API documentation** (auto-generated from docstrings)
* **User guides** for new features
* **Configuration documentation** for new settings
* **Security documentation** for security-related changes

Security Guidelines
-------------------

* Always use existing validation functions from ``src/validators.py``
* Never concatenate user input into shell commands
* Use subprocess with argument lists instead of shell=True
* Validate all file paths for traversal attacks
* Include security test cases for all new validation

For complete details, see :doc:`CONTRIBUTING` and :doc:`security`.