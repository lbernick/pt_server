# Workflow
- When making changes that affect the project structure, build/test scripts, or environment variables, make sure to update the README.md file.
- When adding or changing an endpoint, update the README.md file with example usage.
- After making code changes, run tests and lint/formatting and make sure they pass.
If you need to ignore a lint rule, give an explanation why it's necessary.
- Where possible, practice test driven development; i.e. write tests for features first, then make sure the tests pass once the feature is implemented.

# Migrations
- Any migrations added should be written to be reversible if possible.
For example, foreign key constraints should be named so that they can be dropped.
- When the database schema is modified, update scripts/populate_db accordingly.
