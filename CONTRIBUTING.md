# Contributing

Thank you for contributing to YouTube Content Scraper.

## Getting started

1. Fork the repository and clone your fork.
2. Create and activate a virtual environment.
3. Install runtime and development dependencies:

   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

4. (Optional) enable pre-commit hooks so linting runs automatically:

   ```bash
   pip install pre-commit
   pre-commit install
   ```

5. Make your changes on a focused branch.

## Before opening a pull request

Run the same checks CI runs:

```bash
ruff check .            # lint
ruff format --check .   # formatting
pytest                  # tests
```

Also:

- Test the app locally with `python app.py` and exercise your change in the UI.
- Keep changes focused and update the README/CHANGELOG when behavior or setup
  changes.
- Do not commit `.venv/`, the `output/` directory, `.env`, credentials, or any
  other private data.

## Architecture at a glance

- `scraper.py` holds all browser-dependent logic. The `parse_videos()` function
  is deliberately pure (HTML in, data out) so it can be tested without Selenium.
  If you touch scraping, prefer adding logic there and covering it with a parser
  test over static HTML.
- `jobs.py` runs scrapes on background threads and writes per-job CSVs.
- `app.py` is an application factory; routes are thin and delegate to the job
  manager. Tests inject a fake scrape function, so no test starts a real browser.

When YouTube changes its markup, the selectors in `parse_videos()` and
`resolve_channel_url()` are the most likely things to need updating — add a
sample-HTML test case alongside any such fix.

## Pull requests

Describe what changed and why. Include testing steps and mention any limitations
or changes to scraping behavior. The PR template will prompt you for these.

## Issues

When reporting a problem, include the operating system, Python version,
Chrome/Chromium version, how you're running the app, steps to reproduce, and the
full error message. Do not include personal data or credentials.
