# ADR-0016: Use localtest.me for local DNS resolution

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** dns, networking, local-dev

## Context

Onboarded applications must be reachable in a browser at a friendly URL, e.g. `http://inventory-api.cnoe.localtest.me`. We need a DNS scheme that:

- Resolves wildcard subdomains to `127.0.0.1` without modifying the developer's `/etc/hosts`.
- Is recognised by all major operating systems and browsers.
- Costs nothing and requires no DNS server administration.

`*.localtest.me` is a publicly-resolved domain that always points to `127.0.0.1`. Combined with idpbuilder's nginx ingress, it gives every app a unique URL with no configuration on the developer's machine.

## Decision Drivers

- Zero developer setup; no `/etc/hosts` edits.
- Wildcard support so we can serve `<any-app>.cnoe.localtest.me` without provisioning per app.
- Compatible with TLS via the self-signed wildcard certificate that idpbuilder installs.
- Cross-OS compatibility (macOS, Linux, Windows/WSL).

## Considered Options

1. **`*.localtest.me`** — public wildcard pointing at `127.0.0.1`.
2. **`*.nip.io`** — encodes IP in the hostname; works for non-127 IPs.
3. **Edit `/etc/hosts`** for each onboarded app.
4. **Run a local DNS server** (dnsmasq, CoreDNS).
5. **Use `.local` mDNS** via Avahi/Bonjour.

## Decision

We will use **`*.cnoe.localtest.me`** as installed by idpbuilder. The ingress controller serves any subdomain under `cnoe.localtest.me` and routes by `Host:` header to the corresponding `Service`. The wildcard TLS certificate is the self-signed CA generated at cluster creation.

The agent does not configure DNS or ingress; it relies on the GitOps template (`cnoe-stacks/nodejs-gitops-template/ingress.yaml`) which uses `{{ appName }}.cnoe.localtest.me` as its host.

## Consequences

### Positive

- Zero per-app configuration on the developer's host.
- Friendly URLs for demos.
- TLS works locally using the idpbuilder-installed CA.

### Negative / Costs

- The `localtest.me` domain is operated by a third party. If the resolver vanishes, we need a fallback (e.g. nip.io).
- Browsers warn on the self-signed CA until the developer trusts it once.
- DNS is *public*; the hostname leaks (low-risk for a local demo, but worth noting).

### Neutral

- Switching to a different wildcard host is a one-line change in `ingress.yaml` and `agent.py` log messages.

## Compliance & Security Considerations

- Because `*.localtest.me` resolves to `127.0.0.1`, no traffic ever leaves the developer's machine. There is no information disclosure beyond DNS query logging at the resolver level.
- Trust the idpbuilder CA only on the developer's local profile. Do not import it into a production browser profile.

## Follow-up Work

- [ ] Add a `--host-suffix` flag (env var `INGRESS_SUFFIX`) so demos can switch to `*.nip.io` if needed.
- [ ] Document the CA-trust step for macOS Keychain and Linux NSS.

## References

- ADR-0002 — idpbuilder configures nginx + TLS for `*.cnoe.localtest.me`.
- ADR-0017 — Namespace strategy (apps live in their own namespaces, ingress hosts are app-named).
- localtest.me: <https://readme.localtest.me/>.
