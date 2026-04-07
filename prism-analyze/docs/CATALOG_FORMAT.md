# Inflection Point Catalog Format

The catalog is a YAML file containing AI inflection points — dated events that may have caused structural changes in software development metrics.

## Schema

Each entry has these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier (convention: `slug-YYYY-MM`) |
| `date` | date | yes | Event date (`YYYY-MM-DD`) |
| `label` | string | yes | Human-readable event name |
| `category` | string | yes | Must match `categories.yaml` vocabulary |
| `subcategory` | string | no | Finer classification within category |
| `scope` | enum | no | `global`, `platform-specific`, or `org-specific` (default: `global`) |
| `confidence` | enum | no | `high`, `medium`, or `low` (default: `medium`) |
| `evidence_url` | string | no | URL to announcement or evidence |
| `tags` | list[string] | no | Free-form tags for filtering |
| `notes` | string | no | Context or caveats |

## Allowed Categories

Categories are defined in `prism_analyze/catalog/categories.yaml`:

- `ai-coding-assistant` — code completion, generation, review, chat
- `llm-general` — chatbots, API releases, open-weights models
- `ai-image` — image generation and editing
- `ai-code-review` — automated code review tools
- `ai-infrastructure` — compute, training, serving
- `ai-search` — code and web search
- `ai-agents` — coding, general, and browser agents

Using an unlisted category raises a `CatalogError`.

## Example Entry

```yaml
- id: "copilot-ga-2022-06"
  date: "2022-06-21"
  label: "GitHub Copilot General Availability"
  category: "ai-coding-assistant"
  subcategory: "code-completion"
  scope: "global"
  confidence: "high"
  evidence_url: "https://github.blog/..."
  tags: ["copilot", "github", "microsoft"]
  notes: "Paid GA at $10/mo; free tier followed Nov 2022."
```

## Extending the Catalog

### Option 1: Custom catalog file

Pass your own YAML file as the primary catalog:

```python
catalog = load_catalog(path="my_catalog.yaml")
```

### Option 2: Override specific entries

Pass a user overrides file that adds or replaces entries by `id`:

```python
catalog = load_catalog(user_overrides="my_overrides.yaml")
```

Entries in the overrides file with matching `id` replace the default; new `id`s are added.

## File Locations

- **Bundled default:** `prism_analyze/catalog/ai_inflections.yaml` (shipped with the package)
- **User-facing copy:** `catalog/ai_inflections.yaml` (at project root, for easy editing)
