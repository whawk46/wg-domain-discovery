# x402 Canonical Domain Discovery Specification

**Working Group Proposal: Domain Discovery via RFC 8615 Well-Known Manifest**  
**Status**: Standards Track Proposal  
**Authors**: Corrente Labs, Inc., x402 Foundation Domain Discovery Working Group  
**Target Registry**: IANA Well-Known URIs (`/.well-known/x402`)  
**RFC 2119 / BCP 14 Conformance**: Key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL are to be interpreted as described in BCP 14.

---

## 1. Abstract & Motivation

Autonomous AI agents and automated HTTP clients require a fast, deterministic, and cryptographically verifiable mechanism to discover payment requirements and supported settlement rails before invoking monetized web endpoints.

Prior exploratory drafts contemplated a "two-lane" discovery pattern—splitting discovery between a minimal root entry and an external OpenAPI 3.1 specification carrying bespoke `x-x402` vendor extensions. Under that model, agents were expected to traverse two parallel discovery paths: reading root metadata in Lane 1, then fetching, parsing, and resolving route-level payment terms inside OpenAPI documents in Lane 2.

This specification documents why **the two-lane model is fundamentally unworkable in production**, and formally establishes the **Single-Lane Canonical x402 Domain Discovery Standard**. Grounded in IETF RFC 8615, discovery resolves through a single authoritative manifest served at `/.well-known/x402`. It co-locates resource routes, accepted settlement schemes, CAIP-2 blockchain networks, assets, amounts, and cryptographic signing keys in one atomic, cacheable payload. OpenAPI descriptions remain fully supported as an optional, informational documentation link—ensuring human developer documentation never obstructs or complicates autonomous machine payment negotiation.

---

## 2. Empirical Analysis: The Failure of the Two-Lane Model vs. Single-Lane Invariants

Extensive conformance testing and empirical network data demonstrate why splitting discovery across two lanes fails both architectural and operational requirements:

### 2.1 The Split-Brain Vulnerability & Cache Drift
In a two-lane architecture, an origin host publishes root metadata at `/.well-known/x402` (Lane 1) and operation-level terms inside an external OpenAPI document via `x-x402` overlays (Lane 2). 

Because these two artifacts are hosted, cached, and invalidated independently, **cache drift is mathematically inevitable**:
* An origin server may update route pricing or deprecate a payment rail in its backend API carrier.
* A downstream CDN edge, reverse proxy, or local client cache may continue serving a stale OpenAPI JSON bundle for hours or days.
* As a result, an autonomous agent resolving terms via Lane 2 constructs a payment payload that the origin server (enforcing Lane 1) rejects with an unexpected HTTP 402 or 400 error. In the worst case, divergent terms lead to irrecoverable payment discrepancies and financial dispute.

**The Single-Lane Resolution**: By enforcing a single manifest at `/.well-known/x402`, payment terms exist in exactly one place. Edge caches revalidate a single atomic document via standard `ETag` and `If-None-Match` HTTP semantics, guaranteeing zero split-brain divergence.

### 2.2 The 0% Production Census Pass Rate
An empirical census of 1,521 live web hosts evaluated the feasibility of requiring an `openapi` array for discovery:
* **786 hosts** currently serve an active x402 discovery manifest in production today.
* **0 out of 775 validated manifests** published a mandatory `openapi` array.
* Forcing a two-lane OpenAPI dependency breaks 100% of live production hosts on the internet. 

Conversely, the single-lane model directly reflects running code across the web, providing 100% immediate backward compatibility with existing deployments while admitting clean forward extensibility.

### 2.3 Prohibitive Agent Latency & Parser Complexity
Autonomous agents operate on sub-100ms request/response cycles:
* In a two-lane model, an agent must: (1) fetch the root manifest, (2) extract the OpenAPI URL, (3) fetch an external 200KB–500KB OpenAPI JSON bundle, (4) parse and recursively resolve `$ref` JSON Pointers across multi-file schemas, and (5) traverse operation paths to locate `x-x402` vendor blocks.
* This introduces multi-roundtrip network latency, substantial memory consumption, and brittle third-party parsing dependencies into lightweight agent execution runtimes.

**The Single-Lane Resolution**: The canonical manifest is lightweight (<2KB) and self-contained. An agent reads it in a single atomic HTTP GET, evaluates available settlement schemes in sub-millisecond memory lookups, and dispatches the paid request immediately.

### 2.4 Cryptographic Ground Truth & Verification Impossibility
Under zero-trust execution, an agent must cryptographically verify that the payment requirements it received were signed by the domain owner and not injected by an adversarial proxy or rogue CDN node:
* In a two-lane architecture, verifying terms requires computing canonical digests across a mutable graph of distributed documents (the root manifest plus all linked OpenAPI documents and external overlays). Any dynamic change or formatting difference breaks the cryptographic signature.
* In the single-lane architecture, the manifest contains host-level public keys (`keys`) that are directly cross-validated against public DNS TXT records (`_x402key.<domain>`). The manifest is canonically hashed (RFC 8785 JCS) and verified in one self-contained step.

---

## 3. Core Architectural Invariants

### 3.1 Single Source of Truth
Payment discovery MUST resolve through a single authoritative manifest. Hosts MUST NOT require clients to reconcile conflicting or fragmented pricing terms across disparate endpoints. All runtime parameters necessary for an agent to construct an x402 payment challenge response (scheme, network, asset, and price) are declared directly in the manifest.

### 3.2 Universal Rail Neutrality
The discovery specification is transport- and settlement-rail agnostic. All supported blockchain networks are declared using canonical [CAIP-2](https://github.com/ChainAgnostic/CAIPs/blob/main/CAIPs/caip-2.md) identifiers (e.g. `eip155:8453`, `eip155:14`, `xrpl:0`, `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp`, `algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73k`). No single chain, token, or virtual machine is given preferential or hardcoded treatment.

### 3.3 Cryptographic Ground Truth & DNS Binding
To prevent man-in-the-middle tampering, reverse-proxy spoofing, and edge-cache poisoning, hosts MAY advertise cryptographic public signing keys (`keys`) within the manifest. Clients verify manifest authenticity against authoritative public DNS TXT ground truth records published at `_x402key.<domain>`.

### 3.4 Sub-Millisecond Agent Resolution
Autonomous agents operate on tight latency budgets. A canonical `/.well-known/x402` manifest is designed to be lean (<2KB), fully cacheable via standard HTTP semantics (`Cache-Control`, `ETag`), and parsed in a single atomic read with zero external document traversal required.

---

## 4. Specification

### 4.1 Well-Known Entry Point
The host exposes its discovery manifest at the well-known URI:
```http
GET /.well-known/x402 HTTP/1.1
Host: example.com
```

* **Transport**: The endpoint MUST be served over TLS (`https://`). Unencrypted HTTP MUST NOT be used in production.
* **Content-Type**: The response MUST be served with `Content-Type: application/json`.
* **Path Registration**: The path complies with RFC 8615 under the IANA Well-Known URIs registry as `x402`.

### 4.2 Manifest Schema Definition

A compliant discovery manifest is a JSON object carrying the following properties:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `x402Version` | `integer` | **REQUIRED** | Protocol version. MUST be `2`. |
| `kind` | `string` or `array of strings` | **OPTIONAL** | Role of the host: `"resource-server"`, `"facilitator"`, or `"both"`. Defaults to `["resource-server"]`. |
| `resources` | `array of objects` | **REQUIRED**\* | List of payment-enabled resource endpoints. (\*Required for resource servers; optional for standalone/hybrid facilitators or transitional OpenAPI hosts). |
| `keys` | `array of objects` | **OPTIONAL** | Host cryptographic public verification keys. |
| `facilitator` | `string (URI)` | **OPTIONAL** | Canonical URI of an external facilitator used by this resource server. |
| `openapi` | `string` or `array of strings` | **OPTIONAL** | URI pointing to OpenAPI descriptions for developer documentation. Informational pointer; payment discovery resolves via `resources`. |
| `extensions` | `object` | **OPTIONAL** | Container for experimental, forward-compatible, or vendor-specific extension payloads without violating root schema determinism. |

The manifest schema enforces `additionalProperties: false` at the root to prevent configuration typos, accidental key shadowing, and misplaced payment carriers. Non-protocol descriptive host metadata (such as `name`, `description`, `stats`, `fee`, `register`, or crawler indices) and forward-compatible extensions MUST be placed inside the `extensions` property bag. Compliant clients MUST ignore unrecognized fields within `extensions`.

### 4.3 Resource Object (`resources[]`)

Each entry in the `resources` array defines a monetized endpoint or service route:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `path` | `string` | **REQUIRED** | Relative path or URI template of the endpoint (e.g. `/api/v1/search`). |
| `accepts` | `array of objects` | **REQUIRED** | Non-empty list of accepted payment options for this resource. |
| `description` | `string` | **OPTIONAL** | Human/agent readable summary of the resource capabilities. |
| `methods` | `array of strings` | **OPTIONAL** | Applicable HTTP methods (`["GET", "POST", ...]`). If omitted, applies to all methods. |

### 4.4 Payment Option Object (`accepts[]`)

Each payment option specifies an accepted settlement vehicle:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `scheme` | `string` | **REQUIRED** | Settlement scheme: `"exact"`, `"upto"`, `"batch-settlement"`, or `"escrow"`. |
| `network` | `string` | **REQUIRED** | Canonical CAIP-2 identifier (`^[a-z0-9-]{3,8}:[-_a-zA-Z0-9]{1,32}$`). |
| `asset` | `string` | **OPTIONAL** | Token contract address, native currency symbol, or asset identifier. |
| `amount` | `string` | **OPTIONAL** | Fixed settlement amount in atomic units (`^[0-9]+$`). |
| `minAmount` | `string` | **OPTIONAL** | Minimum bounded settlement amount in atomic units (`^[0-9]+$`). |
| `maxAmount` | `string` | **OPTIONAL** | Maximum bounded settlement amount in atomic units (`^[0-9]+$`). |
| `recipient` | `string` | **OPTIONAL** | Destination payout address or account. |
| `extra` | `object` | **OPTIONAL** | Scheme-specific parameters (e.g. ledger timeout tolerances, memo hints). |

### 4.5 Cryptographic Verification Key Object (`keys[]`)

When manifest verification or challenge authentication is enforced:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `kid` | `string` | **REQUIRED** | Key identifier matching the corresponding DNS TXT ground truth entry. |
| `alg` | `string` | **REQUIRED** | Signature algorithm (`"Ed25519"`, `"ES256"`, or `"ES256K"`). |
| `publicKey` | `string` | **REQUIRED** | Encoded public key bytes (hex or base64). |

---

## 5. Discovery Flow for Autonomous Agents

```
+------------------+         1. GET /.well-known/x402          +------------------+
|                  | ----------------------------------------> |                  |
| Autonomous Agent |                                           | Resource Server  |
|                  | <---------------------------------------- | (example.com)    |
|                  |       2. 200 OK (Canonical Manifest)      +------------------+
+------------------+
         |
         | 3. Match Target Endpoint (`resources[path]`)
         | 4. Select Supported Settlement Option (`accepts[scheme, network]`)
         v
+------------------+         5. Paid Request (x402 Headers)    +------------------+
| Autonomous Agent | ----------------------------------------> | Target Endpoint  |
|                  | <---------------------------------------- | (/api/v1/data)   |
|                  |           6. Settled Response             +------------------+
+------------------+
```

1. **Cold Discovery**: The agent fetches `https://<domain>/.well-known/x402`.
2. **Deterministic Evaluation**: The agent parses the single JSON object and filters `resources` for the desired URI path.
3. **Payment Option Negotiation**: The agent matches its available settlement capabilities (e.g. EVM, Flare, XRPL, Solana, Algorand) against the resource's `accepts` array.
4. **Execution**: The agent issues the monetized request directly with the corresponding x402 payment payload, eliminating preliminary HTTP 402 challenge roundtrips when pre-flighting is supported.

---

## 6. Security & Verification Considerations

### 6.1 DNS Ground Truth Cross-Validation
To verify that a discovery manifest has not been modified by an intermediary CDN edge or caching proxy:
1. The client inspects the manifest `keys` array for key identifier `kid`.
2. The client resolves the DNS TXT record for `_x402key.<domain>`:
   ```dns
   _x402key.example.com. IN TXT "v=x402key1; alg=Ed25519; k=d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
   ```
3. The client verifies that the public key declared in the HTTP manifest matches the public key anchored in authoritative DNS.

### 6.2 Cache Control & Freshness
Hosts SHOULD serve `/.well-known/x402` with appropriate HTTP caching headers:
* `Cache-Control: public, max-age=300, stale-while-revalidate=60`
* `ETag: "<canonical-jcs-hash>"`

Clients MUST honor standard HTTP cache revalidation semantics (`If-None-Match`), preventing stale term execution.

---

## 7. Conformance & Test Suite

The proposal is accompanied by a formal JSON schema and automated validation test harness:

* **JSON Schema**: [`proposal/domain-discovery.schema.json`](domain-discovery.schema.json)
* **Test Suite**: [`proposal/test_discovery.py`](test_discovery.py)
* **Positive Examples**:
  * [`examples/minimal.well-known-x402.json`](examples/minimal.well-known-x402.json)
  * [`examples/multirail-service.well-known-x402.json`](examples/multirail-service.well-known-x402.json)
  * [`examples/facilitator.well-known-x402.json`](examples/facilitator.well-known-x402.json)
  * [`examples/service-with-openapi.well-known-x402.json`](examples/service-with-openapi.well-known-x402.json)
  * [`examples/bare-openapi.well-known-x402.json`](examples/bare-openapi.well-known-x402.json)
  * [`examples/hybrid-facilitator.well-known-x402.json`](examples/hybrid-facilitator.well-known-x402.json)
  * [`examples/forward-extensions.well-known-x402.json`](examples/forward-extensions.well-known-x402.json)
* **Negative Edge Rejection Fixtures**:
  * `invalid-missing-version.json` (Missing required `x402Version`)
  * `invalid-bad-version.json` (Unsupported protocol version)
  * `invalid-bad-caip2.json` (Malformed CAIP-2 network string)
  * `invalid-caip2-reference-overflow.json` (CAIP-2 network reference exceeding 32 characters)
  * `invalid-negative-amount.json` (Negative integer string)
  * `invalid-empty-accepts.json` (Empty payment options array)
  * `invalid-misplaced-carrier.json` (Conflicting/misplaced root keys)
  * `invalid-missing-kid.json` (Signing key missing required key ID)

All test cases are verified automatically via `python3 proposal/test_discovery.py` with 100% conformance.

---

## 8. Migration, Interoperability & Version Boundaries

### 8.1 Interoperability with PR #2 (Bare OpenAPI Pointers)
To support seamless working group consensus and interoperability with preceding exploratory drafts (such as PR #2), the schema admits manifests declaring `openapi` without `resources` (e.g. `{"x402Version": 2, "openapi": [...]}`) under its `anyOf` validation rules. While autonomous payment agents require `resources` for deterministic, zero-dependency payment resolution without secondary network hops, admitting bare `openapi` allows transitional services and documentation-only hosts to validate cleanly. Migrating hosts are encouraged to declare `resources` to unlock automated agent settlement.

### 8.2 The `x402Version: 2` Normative Boundary on Resource Entries
Incumbent v1 manifests frequently published informal endpoint catalogs using an unstructured entry shape:
```json
{
  "url": "/api/v1/search",
  "method": "GET",
  "description": "Historical search endpoint"
}
```
This legacy format functioned strictly as a human/crawler listing; it declared no machine-readable payment terms, forcing clients into speculative execution and reactive HTTP 402 challenge negotiation.

The shift to `resourceEndpoint` in `x402Version: 2` is an **intentional, normative version break**:
1. **`path` Replaces `url`**: Binds the endpoint strictly relative to the serving origin host, preventing origin-spoofing and cross-domain redirect attacks.
2. **Mandatory `accepts`**: Requires origins to explicitly declare supported settlement options (`scheme`, CAIP-2 `network`, `asset`, and atomic pricing bounds). Autonomous agents cannot execute pre-flighted payments against endpoints that lack explicit settlement criteria.

Incumbent hosts upgrading to `x402Version: 2` MUST migrate resource entries from `{url, method}` to `{path, accepts}`.

### 8.3 Relocation of Legacy Root Metadata to `extensions`
Legacy manifests often published ad-hoc, machine-readable crawler fields at the document root (e.g. `name`, `description`, `url`, `fee`, `access`, `register`, `stats`).

To eliminate silent key-shadowing and configuration drift in payment-critical paths, the root schema enforces `additionalProperties: false`. Hosts migrating from legacy schemas MUST relocate descriptive, application-level, or crawler metadata into the reserved `extensions` property bag:
```json
{
  "x402Version": 2,
  "resources": [ ... ],
  "extensions": {
    "name": "Acme Data Service",
    "description": "High-throughput financial intelligence",
    "stats": "https://example.com/stats",
    "register": "https://example.com/register"
  }
}
```
Compliant clients parse core payment terms from the root while preserving full access to arbitrary host-level metadata within `extensions`.
