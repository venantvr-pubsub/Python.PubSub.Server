# Contributing to Python Publisher Subscriber

First off, thank you for considering contributing to Python Publisher Subscriber! It's people like you that make Python Publisher Subscriber such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* Use a clear and descriptive title for the issue to identify the problem.
* Describe the exact steps which reproduce the problem in as many details as possible.
* Provide specific examples to demonstrate the steps.
* Describe the behavior you observed after following the steps and point out what exactly is the problem with that behavior.
* Explain which behavior you expected to see instead and why.
* Include screenshots and animated GIFs if possible.

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* Use a clear and descriptive title for the issue to identify the suggestion.
* Provide a step-by-step description of the suggested enhancement in as many details as possible.
* Provide specific examples to demonstrate the steps.
* Describe the current behavior and explain which behavior you expected to see instead and why.
* Explain why this enhancement would be useful to most Python Publisher Subscriber users.

### Your First Code Contribution

Unsure where to begin contributing? You can start by looking through these `beginner` and `help-wanted` issues:

* **Beginner issues** - issues which should only require a few lines of code.
* **Help wanted issues** - issues which should be a bit more involved than `beginner` issues.

### Pull Requests

1.  Fork the repo and create your branch from `main`.
2.  If you've added code that should be tested, add tests.
3.  If you've changed APIs, update the documentation.
4.  Ensure the test suite passes.
5.  Make sure your code follows the existing style.
6.  Issue that pull request!

## Development Process

1.  **Setup your environment:**
    ```
    git clone [https://github.com/venantvr/Python.Publisher.Subscriber.git](https://github.com/venantvr/Python.Publisher.Subscriber.git)
    cd Python.Publisher.Subscriber
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements-dev.txt
    pip install -e .
    pre-commit install
    ```
2.  **Create a feature branch:**
    ```
    git checkout -b feature/your-feature-name
    ```
3.  **Make your changes:**
    * Write your code
    * Add tests for your changes
    * Update documentation if needed
4.  **Run tests and checks:**
    ```
    make test        # Run tests
    make lint        # Check code style
    make format      # Format code
    ```
5.  **Commit your changes:**
    ```
    git add .
    git commit -m "Add feature: your feature description"
    ```
6.  **Push and create PR:**
    ```
    git push origin feature/your-feature-name
    ```

## Style Guidelines

### Python Style Guide

* Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/).
* Use [Black](https://github.com/psf/black) for code formatting.
* Use [isort](https://github.com/PyCQA/isort) for import sorting.
* Maximum line length is 100 characters.
* Use type hints where possible.

### Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

### Documentation Style Guide

* Use Markdown for documentation.
* Reference functions, classes, and modules in backticks.
* Include code examples where appropriate.

## Testing

* Write tests for all new functionality.
* Write comprehensive tests for new features.
* Run the full test suite before submitting a PR.
* Tests should be deterministic and not rely on external services.

## Additional Notes

### Issue and Pull Request Labels

* `bug` - Something isn't working
* `enhancement` - New feature or request
* `documentation` - Improvements or additions to documentation
* `good first issue` - Good for newcomers
* `help wanted` - Extra attention is needed
* `question` - Further information is requested

## Recognition

Contributors will be recognized in our README and release notes. Thank you for your contributions!
