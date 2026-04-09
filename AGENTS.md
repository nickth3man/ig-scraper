
## Shell Requirement

This environment uses **bash** as the execution shell, including on Windows.
Always write and run commands using **bash syntax**, not PowerShell syntax.
For example, use `VAR=value command` or `export VAR=value`, not `$env:VAR='value'`.

### Bash-Only Command Guardrail

- **Never** use PowerShell environment-variable syntax in this repo, even on Windows:
  - Wrong: `$env:CI='true'; git status --short`
  - Wrong: `$env:GIT_PAGER='cat'; git commit -m "message"`
- **Never** prepend a generic "safe command prefix" copied from another shell or project.
- For simple commands, prefer the plain bash command with **no** env prefix at all:
  - Right: `git status --short`
  - Right: `git mv "old" "new"`
  - Right: `git commit -m "message"`
- If environment variables are actually needed, use **bash** forms only:
  - Right: `CI='true' GIT_PAGER='cat' git status --short`
  - Right: `export CI='true' GIT_PAGER='cat'` then run the command
- Before running any command on Windows, quickly sanity-check that every token is valid **bash** syntax.

## Search Tooling

When beginning any search for files or specific code in the codebase, **always** use the following tools:

### 1. `tree` - Visual Directory Structure

Use `tree` to understand the project layout before diving into specific files:

```bash
# Show entire project structure
tree

# Show specific directory
tree src/

# Limit depth
tree -L 2
```

### 2. `rg` (ripgrep) - Fast Code Search

Use `rg` (ripgrep) for fast, recursive code searching across the entire codebase:

```bash
# Search for a pattern in all files
rg "pattern"

# Search in specific file types
rg "pattern" --type py

# Search with context lines
rg -C 3 "pattern"

# Search only in src/
rg "pattern" src/
```

**Why these tools?**
- `tree` gives instant visual context of project structure
- `rg` is faster than grep, respects .gitignore, and has better defaults
- Both are cross-platform and available in this environment

Start with `tree` to orient yourself, then use `rg` to find specific code patterns.

## Post-Edit Workflow

After making any file changes, **ALWAYS** run the all-in-one check script:

```bash
uv run python scripts/check_all.py
```

This runs all checks in order: ruff lint, ruff format check, mypy, pytest, file length.
It stops on the first failure. Fix the issue and re-run until all checks pass.

**NEVER use `--no-verify` to bypass these checks.** The pre-commit hook exists to catch issues before they reach CI. Bypassing it with `--no-verify` defeats this protection and can introduce bugs or style violations into the codebase.

Alternatively, run individual checks:

### 1. Run the Linter

```bash
uv run ruff check .
```

### 2. Run the Formatter

```bash
uv run ruff format .
```

### 3. Run Type Checkers

```bash
uv run mypy src/
```

### 4. Run All Tests

```bash
uv run pytest
```

### 5. Check File Lengths

```bash
uv run python scripts/check_file_length.py
```

## Project Tooling Reference

| Tool | Purpose | Command |
| ------ | --------- | --------- |
| ruff | Linting | `uv run ruff check .` |
| ruff | Formatting | `uv run ruff format .` |
| mypy | Type checking | `uv run mypy src/` |
| pytest | Testing | `uv run pytest` |
| pytest + coverage | Test coverage | `uv run pytest --cov` |
| check_all.py | All checks | `uv run python scripts/check_all.py` |

## Pre-Commit Hooks

This project has pre-commit hooks configured. On every commit the following runs:

1. **Standard hooks** (trailing whitespace, end-of-file fixer, YAML validation, merge conflict detection)
2. **check_all.py** — unified runner that executes in order:
   - ruff check (lint)
   - ruff format (check only)
   - mypy (type checking)
   - mypy (type checking)
   - pytest (all tests)
   - file length check (200 line limit)

   Stops on the first failure.

To run pre-commit hooks manually:

```bash
uv run pre-commit run --all-files
```

## External Search Workflows

When searching externally on the internet, use these comprehensive workflows to maximize search effectiveness. Always run tools in parallel within each phase.

### Workflow 1: Quick Fact Check / Q&A

Use when you need a fast, factual answer.

**Phase 1 (Parallel):**

- `perplexity_perplexity_ask` - Quick AI-powered answer with citations
- `brave-search_brave_web_search` - General web results for verification
- `web-search-prime_web_search_prime` - Summarized results for context

**Phase 2 (If needed):**

- `webfetch` or `web-reader_webReader` - Fetch specific URLs from Phase 1 results for deeper reading

### Workflow 2: Technical Documentation Deep Dive

Use when researching a library, framework, or API.

**Phase 1 (Parallel - Discovery):**

- `context7_resolve-library-id` - Check if official docs available in Context7
- `tavily_tavily-search` (search_depth="advanced") - AI-curated technical results
- `brave-search_brave_web_search` - Broad coverage of official docs and tutorials

**Phase 2 (Parallel - Extraction, depends on Phase 1):**

- `context7_query-docs` - Query official documentation (if library resolved)
- `tavily_tavily-extract` - Deep extraction of promising URLs from Phase 1
- `webfetch` or `web-reader_webReader` - Fetch specific doc pages

**Phase 3 (Optional):**

- `tavily_tavily-crawl` - Crawl documentation site structure if comprehensive reference needed

### Workflow 3: GitHub Code Examples & Patterns

Use when looking for implementation examples or best practices.

**Phase 1 (Parallel):**

- `grep_app_searchGitHub` - Search code patterns across public repos
- `zread_search_doc` - Search issues/commits for context
- `deepwiki_read_wiki_contents` - Read project documentation if known repo

**Phase 2 (Depends on Phase 1):**

- `zread_read_file` - Read specific files from repos found in Phase 1
- `deepwiki_read_wiki_structure` - Explore docs structure of promising repos
- `tavily_tavily-search` - Cross-reference with web discussions

### Workflow 4: Comprehensive Research Investigation

Use when doing deep, multi-source research on a topic.

**Phase 1 (Parallel - Broad Search):**

- `perplexity_perplexity_research` - Deep research with multiple sources
- `tavily_tavily-search` (max_results=20, search_depth="advanced") - Comprehensive AI search
- `websearch_web_search_exa` - Semantic search for nuanced matches

**Phase 2 (Parallel - Extraction):**

- `perplexity_perplexity_search` - Get ranked web results for manual review
- `tavily_tavily-extract` - Extract content from top URLs found
- `brave-search_brave_web_search` (count=20) - Additional coverage

**Phase 3 (Optional Deep Dive):**

- `tavily_tavily-crawl` - Crawl specific domains for comprehensive coverage
- `webfetch` / `web-reader_webReader` - Manual URL fetching for specific articles

### Workflow 5: Library/Package-Specific Reference

Use when working with specific npm/pip/cargo packages.

**Phase 1 (Parallel - Package Discovery):**

- `context7_resolve-library-id` - Find official Context7 documentation
- `tavily_tavily-search` (search_depth="advanced") - Find official docs and best practices
- `grep_app_searchGitHub` - Find real-world usage examples

**Phase 2 (Parallel - Documentation & Examples):**

- `context7_query-docs` - Query official API docs (if available)
- `zread_search_doc` - Search popular repos using the package
- `web-reader_webReader` - Fetch README and Getting Started guides

**Phase 3 (Deep Dive):**

- `zread_read_file` - Read implementation examples from GitHub
- `tavily_tavily-extract` - Extract from tutorial/blog posts

### Key Principles

1. **Always run Phase 1 tools in parallel** - Don't wait for one to finish before starting others
2. **Context7 first for libraries** - Official docs are gold; check Context7 before web search
3. **Tavily for technical depth** - Use advanced search depth for technical topics
4. **Perplexity for reasoning** - Use reason/research modes for complex analysis
5. **GitHub for patterns** - Real code examples are invaluable for implementation questions
6. **Extract after discovery** - Use extraction tools only after identifying valuable URLs
7. **DeepWiki for GitHub docs** - When accessing any GitHub repository documentation, ALWAYS use `deepwiki_read_wiki_contents` before fetching and `deepwiki_read_wiki_structure` after fetching to get AI-generated documentation summaries and explore the full docs structure
