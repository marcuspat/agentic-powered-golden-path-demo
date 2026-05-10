# ADR-0007: Use Jinja2 to render stack templates

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Agent Engineering, Platform Engineering
- **Tags:** templating, agent, stacks

## Context

`populate_repo_from_stack()` (`agent.py:44`) reads every file in a stack template directory, substitutes per-application variables (`appName`, `description`, namespace, image), and writes the result into the freshly cloned repository. The substitution must:

- Cover `.yaml`, `.json`, `.js`, `Dockerfile`, and Markdown files alike.
- Tolerate files that have no template variables (i.e. behave as identity for static content).
- Be familiar to the platform engineering audience.
- Not collide with Helm or Kustomize syntax already present in some manifests.

Initial drafts in `plan.md` used Go-style `{{.Values.appName}}` placeholders. The agent currently uses Jinja2 expressions (`{{ appName }}`, `{{ description }}`).

## Decision Drivers

- Familiarity (Python ecosystem and Ansible users know Jinja2).
- Avoid clashes with downstream renderers (Helm, Kustomize) inside the same files.
- Filters and conditionals available without bolting on new dependencies.
- Already a transitive dependency via `langchain-community`.

## Considered Options

1. **Jinja2** with `{{ var }}` syntax.
2. **Go text/template** with `{{ .Values.var }}` (matches Helm).
3. **String `.format()`** with `{var}` placeholders.
4. **`envsubst`** at shell level.
5. **Cookiecutter** for project scaffolding.

## Decision

We will use **Jinja2** with the default `{{ var }}` and `{% … %}` delimiters for all template files in `cnoe-stacks/` and `templates/`. Each file is loaded as a Jinja2 `Template` and rendered with the variable bag `{appName, description, …}`. Files that contain no template syntax pass through unchanged.

For files where Jinja2 syntax conflicts with the file's native templating language (e.g. a Helm chart embedded in the stack), we prefix the conflicting block with `{% raw %}…{% endraw %}` and document the convention at the top of the file.

## Consequences

### Positive

- Familiar syntax for Python users.
- Filters (`| lower`, `| replace`) available for normalising names.
- Identity render is safe for binary-ish files such as `Dockerfile` because Jinja2 leaves non-templated text alone.

### Negative / Costs

- Jinja2 will *fail* on un-escaped Helm `{{ .Values.foo }}` blocks if it encounters them. Authors of stack templates must use `{% raw %}` to escape.
- Variable bag is implicit; there is no schema today to validate the variables a template requires.
- Unlike Cookiecutter, we do not have a structured "user prompt" mechanism for missing variables; the agent passes a fixed dict.

### Neutral

- The renderer is a thin wrapper around `jinja2.Template`. Switching to a different engine in the future is a localised change in `populate_repo_from_stack()`.

## Compliance & Security Considerations

- Jinja2 templates are loaded from the project's own `cnoe-stacks/` directory. We do **not** render user-supplied templates; the agent never accepts a remote template URL. This rules out server-side template injection at the agent layer.
- App names flowing into template variables are sanitised by `extract_app_name_from_request()` (lowercase, hyphens only); the same sanitisation must be enforced before any template variable reaches a shell, file path, or Kubernetes resource name.

## Follow-up Work

- [ ] Define a `template-vars.schema.json` per stack that enumerates required and optional variables.
- [ ] Add a CI test that renders every stack template with a fixed dummy variable set to catch syntax errors.
- [ ] Consider a Cookiecutter-style `hooks/` directory for post-render steps (e.g. `npm install`).

## References

- ADR-0004 — Python implementation; Jinja2 is idiomatic.
- ADR-0012 — `cnoe-stacks` template structure.
- Jinja2 docs: <https://jinja.palletsprojects.com/>.
