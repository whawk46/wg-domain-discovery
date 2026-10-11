# x402 Canonical Domain Discovery Specification

**Working Group Proposal: Domain Discovery via RFC 8615 Well-Known Manifest**  
**Status**: Standards Track Proposal  
**Authors**: Corrente Labs, Inc., x402 Foundation Domain Discovery Working Group  
**Target Registry**: IANA Well-Known URIs (`/.well-known/x402`)  
**RFC 2119 / BCP 14 Conformance**: Key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL are to be interpreted as described in BCP 14.

---

## 1. Abstract & Motivation

Autonomous AI agents and automated HTTP clients require a fast, deterministic, and cryptographically verifiable mechanism to discover payment requirements and supported settlement rails before invoking monetized web endpoints.

Prior experimental proposals introduced fragmented, multi-lane discovery patterns—forcing clients to download heavy API description documents (such as OpenAPI 3.1 bundles), traverse arbitrary route hierarchies, and parse bespoke vendor extensions (`x-x402`) to extract basic payment terms. Empirical network analysis of 1,521 live hosts revealed that mandatory OpenAPI publication breaks 100% of existing production deployments (0/775 pass rate), while introducing fatal split-brain cache divergence between root domain manifests and external API descriptions.

This specification defines the authoritative, single-lane **x402 Domain Discovery Standard**. Grounded in IETF RFC 8615, it establishes a lightweight, canonical manifest at `/.well-known/x402` that directly advertises resource endpoints, payment schemes, CAIP-2 blockchain networks, settlement assets, and host-level cryptographic verification keys. OpenAPI descriptions remain fully supported as an optional documentation reference, preserving clean architectural separation between human developer documentation and real-time machine payment negotiation.

---

## 2. Core Architectural Invariants

### 2.1 Single Source of Truth (Zero Split-Brain)
Payment discovery MUST resolve through a single authoritative manifest. Hosts MUST NOT require clients to reconcile conflicting or fragmented pricing terms across disparate endpoints. All runtime parameters necessary for an agent to construct an x402 payment challenge response (scheme, network, asset, and price) are declared directly in the manifest.

### 2.2 Universal Rail Neutrality
The discovery specification is transport- and settlement-rail agnostic. All supported blockchain networks are declared using canonical [CAIP-2](https://github.com/ChainAgnostic/CAIPs/blob/main/CAIPs/caip-2.md) identifiers (e.g. `eip155:8453`, `eip155:14`, `xrpl:0`, `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp`, `algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73k`). No single chain, token, or virtual machine is given preferential or hardcoded treatment.

### 2.3 Cryptographic Ground Truth & DNS Binding
To prevent man-in-the-middle tampering, reverse-proxy spoofing, and edge-cache poisoning, hosts MAY advertise cryptographic public signing keys (`keys`) within the manifest. Clients verify manifest authenticity against authoritative public DNS TXT ground truth records published at `_x402key.<domain>`.

### 2.4 Sub-Millisecond Agent Resolution
Autonomous agents operate on tight latency budgets. A canonical `/.well-known/x402` manifest is designed to be lean (<2KB), fully cacheable via standard HTTP semantics (`Cache-Control`, `ETag`), and parsed in a single atomic read with zero external document traversal required.

---

## 3. Specification

### 3.1 Well-Known Entry Point
The host exposes its discovery manifest at the well-known URI:
```http
GET /.well-known/x402 HTTP/1.1
Host: example.com
```

* **Transport**: The endpoint MUST be served over TLS (`https://`). Unencrypted HTTP MUST NOT be used in production.
* **Content-Type**: The response MUST be served with `Content-Type: application/json`.
* **Path Registration**: The path complies with RFC 8615 under the IANA Well-Known URIs registry as `x402`.

### 3.2 Manifest Schema Definition

A compliant discovery manifest is a JSON object carrying the following properties:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `x402Version` | `integer` | **REQUIRED** | Protocol version. MUST be `2`. |
| `kind` | `string` or `array of strings` | **OPTIONAL** | Role of the host: `"resource-server"`, `"facilitator"`, or `"both"`. Defaults to `["resource-server"]`. |
| `resources` | `array of objects` | **REQUIRED**\* | List of payment-enabled resource endpoints. (\*Required for resource servers; optional for standalone facilitators). |
| `keys` | `array of objects` | **OPTIONAL** | Host cryptographic public verification keys. |
| `facilitator` | `string (URI)` | **OPTIONAL** | Canonical URI of an external facilitator used by this resource server. |
| `openapi` | `string` or `array of strings` | **OPTIONAL** | URI pointing to OpenAPI descriptions for developer documentation. Informational only. |

Clients MUST ignore any unrecognized members. This guarantees forward compatibility across minor specification revisions.

### 3.3 Resource Object (`resources[]`)

Each entry in the `resources` array defines a monetized endpoint or service route:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `path` | `string` | **REQUIRED** | Relative path or URI template of the endpoint (e.g. `/api/v1/search`). |
| `accepts` | `array of objects` | **REQUIRED** | Non-empty list of accepted payment options for this resource. |
| `description` | `string` | **OPTIONAL** | Human/agent readable summary of the resource capabilities. |
| `methods` | `array of strings` | **OPTIONAL** | Applicable HTTP methods (`["GET", "POST", ...]`). If omitted, applies to all methods. |

### 3.4 Payment Option Object (`accepts[]`)

Each payment option specifies an accepted settlement vehicle:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `scheme` | `string` | **REQUIRED** | Settlement scheme: `"exact"`, `"upto"`, `"batch-settlement"`, or `"escrow"`. |
| `network` | `string` | **REQUIRED** | Canonical CAIP-2 identifier (`^[a-z0-9-]{3,8}:[-_a-zA-Z0-9]{1,64}$`). |
| `asset` | `string` | **OPTIONAL** | Token contract address, native currency symbol, or asset identifier. |
| `amount` | `string` | **OPTIONAL** | Fixed settlement amount in atomic units (`^[0-9]+$`). |
| `minAmount` | `string` | **OPTIONAL** | Minimum bounded settlement amount in atomic units (`^[0-9]+$`). |
| `maxAmount` | `string` | **OPTIONAL** | Maximum bounded settlement amount in atomic units (`^[0-9]+$`). |
| `recipient` | `string` | **OPTIONAL** | Destination payout address or account. |
| `extra` | `object` | **OPTIONAL** | Scheme-specific parameters (e.g. ledger timeout tolerances, memo hints). |

### 3.5 Cryptographic Verification Key Object (`keys[]`)

When manifest verification or challenge authentication is enforced:

| Field | Type | Requirement | Description |
| :--- | :--- | :--- | :--- |
| `kid` | `string` | **REQUIRED** | Key identifier matching the corresponding DNS TXT ground truth entry. |
| `alg` | `string` | **REQUIRED** | Signature algorithm (`"Ed25519"`, `"ES256"`, or `"ES256K"`). |
| `publicKey` | `string` | **REQUIRED** | Encoded public key bytes (hex or base64). |

---

## 4. Discovery Flow for Autonomous Agents

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

## 5. Security & Verification Considerations

### 5.1 DNS Ground Truth Cross-Validation
To verify that a discovery manifest has not been modified by an intermediary CDN edge or caching proxy:
1. The client inspects the manifest `keys` array for key identifier `kid`.
2. The client resolves the DNS TXT record for `_x402key.<domain>`:
   ```dns
   _x402key.example.com. IN TXT "v=x402key1; alg=Ed25519; k=d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
   ```
3. The client verifies that the public key declared in the HTTP manifest matches the public key anchored in authoritative DNS.

### 5.2 Cache Control & Freshness
Hosts SHOULD serve `/.well-known/x402` with appropriate HTTP caching headers:
* `Cache-Control: public, max-age=300, stale-while-revalidate=60`
* `ETag: "<canonical-jcs-hash>"`

Clients MUST honor standard HTTP cache revalidation semantics (`If-None-Match`), preventing stale term execution.

---

## 6. Conformance & Test Suite

The proposal is accompanied by a formal JSON schema and automated validation test harness:

* **JSON Schema**: [`proposal/domain-discovery.schema.json`](domain-discovery.schema.json)
* **Test Suite**: [`proposal/test_discovery.py`](test_discovery.py)
* **Positive Examples**:
  * [`examples/minimal.well-known-x402.json`](examples/minimal.well-known-x402.json)
  * [`examples/multirail-service.well-known-x402.json`](examples/multirail-service.well-known-x402.json)
  * [`examples/facilitator.well-known-x402.json`](examples/facilitator.well-known-x402.json)
  * [`examples/service-with-openapi.well-known-x402.json`](examples/service-with-openapi.well-known-x402.json)
* **Negative Edge Rejection Fixtures**:
  * `invalid-missing-version.json` (Missing required `x402Version`)
  * `invalid-bad-version.json` (Unsupported protocol version)
  * `invalid-bad-caip2.json` (Malformed CAIP-2 network string)
  * `invalid-negative-amount.json` (Negative integer string)
  * `invalid-empty-accepts.json` (Empty payment options array)
  * `invalid-misplaced-carrier.json` (Conflicting/misplaced root keys)
  * `invalid-missing-kid.json` (Signing key missing required key ID)

All test cases are verified automatically via `python3 proposal/test_discovery.py` with 100% conformance.
