<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.0 → 1.3.0 (minor — new testing discipline principle added)
Modified principles: none renamed
Added sections:
  - Core Principles › VI. End-to-End Testing Discipline (new principle)
    Triggered by: user directive to avoid mock tests in favor of end-to-end
    behavioral validation. Mocks mask real integration failures and increase
    long-term maintenance burden.
Removed sections: none
Templates reviewed:
  - .specify/templates/plan-template.md      ✅ compatible — Constitution Check gates unchanged
  - .specify/templates/spec-template.md      ✅ compatible — no affected sections
  - .specify/templates/tasks-template.md     ✅ updated — testing note updated to reflect
    no-mock policy and end-to-end preference
  - .specify/templates/agent-file-template.md ✅ compatible — no conflicts
Deferred TODOs: none
Previous amendment: 1.1.0 → 1.2.0 (demo tool exemption in result schema)
-->

# LocalSearch Constitution

## Core Principles

### I. Token Efficiency (NON-NEGOTIABLE)

Every tool response MUST minimize token count without sacrificing correctness.
Results MUST include only the information an agent needs: file path, line range,
and a concise excerpt. Full-file dumps are PROHIBITED. Responses MUST be
structured so agents can act immediately without re-querying for context.

**Rationale**: The primary value proposition of LocalSearch is speed via low
token overhead. Violating this principle defeats the purpose of the server.

### II. Simplicity Over Cleverness

Implementations MUST choose the simplest correct solution. Abstractions are
only permitted when they eliminate real, observed duplication across at least
two call sites. YAGNI applies unconditionally: no speculative features, no
configuration hooks for hypothetical use cases, no generic frameworks when a
direct implementation suffices.

**Rationale**: Simple code is auditable, debuggable, and fast to iterate on.
Complexity that is not justified by a current requirement MUST be removed.

### III. Concurrent and Non-Blocking I/O (NON-NEGOTIABLE)

All file system operations, index builds, and search queries MUST be performed
asynchronously and concurrently. Blocking calls on the main event loop are
PROHIBITED. CPU-bound indexing work MUST be offloaded to worker threads or
processes. The MCP server MUST remain responsive to new requests while
long-running searches are in progress.

**Rationale**: Search over large codebases can involve thousands of file reads.
Blocking I/O would stall the agent and negate LocalSearch's performance goals.

### IV. Precise Trigger Surface

The MCP tool description and parameter documentation MUST be written so that
an LLM agent triggers LocalSearch when and only when it needs to:
(a) locate code implementing a concept, feature, or user story, or
(b) find files or symbols by name, pattern, or semantic intent.

The description MUST be concise (≤3 sentences), informative, and free of
marketing language. Parameter names and descriptions MUST be self-documenting.

**Rationale**: An overly broad or vague description causes agents to over-call
(wasting tokens) or under-call (missing relevant results). Precision here
directly affects agent correctness.

### V. Performance-Aware Design

Search operations MUST complete within a time budget proportional to corpus
size. Indexing MUST use incremental strategies (e.g., file-watch invalidation
or mtime checks) so repeated queries do not re-scan unchanged files.
Hot-path code MUST avoid unnecessary allocations. Benchmarks MUST be run and
results recorded before any change to the search or index pipeline is merged.

**Rationale**: Token efficiency is meaningless if latency forces agents to
time out or retry. Performance is a first-class correctness requirement.

### VI. End-to-End Testing Discipline (NON-NEGOTIABLE)

Tests MUST validate real, observable behavior through the full system stack.
Mock-based tests are PROHIBITED. Unit tests that substitute real dependencies
with mocks or fakes MUST NOT be introduced; they mask integration failures and
create a false sense of correctness. All tests MUST exercise actual components:
real file I/O, real MCP transport, real subprocess calls, real async execution.

**Rationale**: Mock tests pass while production breaks. This project has a
narrow, well-defined integration surface (MCP stdio/SSE + file system); the
cost of running real end-to-end tests is low and the confidence gain is high.
Mocks add maintenance burden without commensurate safety.

## Technical Standards

- **Transport**: MCP stdio or SSE transport; no custom protocols.
- **Concurrency model**: async/await throughout; worker pool for CPU-bound
  indexing; no blocking calls on the event loop.
- **Result schema**: every search result MUST include `file`, `start_line`,
  `end_line`, and `snippet` fields. No field may be omitted or set to null
  unless explicitly documented as optional. **Exception**: demo or
  validation tools (i.e., tools whose sole purpose is to verify the
  agent-MCP integration loop, not to return search results) are exempt from
  this schema requirement, provided their purpose is explicitly documented in
  the tool description and data-model.md.
- **Index storage**: in-process only by default; persistent disk cache is
  permitted as an opt-in optimization but MUST NOT be required for correctness.
- **Error surface**: errors MUST be returned as structured MCP error responses,
  never as unformatted stderr noise. Stack traces MUST NOT appear in production
  responses.
- **Dependencies**: minimize third-party dependencies; prefer standard-library
  or well-audited ecosystem packages. Each new dependency MUST be justified in
  the relevant PR.

## Development Workflow

- All new tool handlers MUST have at least one end-to-end integration test that
  validates real behavior through the MCP transport layer. Mock-based tests are
  PROHIBITED (see Principle VI).
- Benchmark baselines MUST be committed alongside any change to the index or
  search pipeline (see Principle V).
- Constitution compliance MUST be checked in the plan-template "Constitution
  Check" gate before any Phase 0 research begins and re-checked after Phase 1
  design.
- Complexity violations (e.g., adding a second abstraction layer) MUST be
  recorded in the Complexity Tracking table of the relevant plan.md with
  explicit justification.
- Code review MUST verify: no blocking I/O, no full-file token dumps, result
  schema completeness, simplicity rationale for any new abstraction, and
  absence of mock-based tests.
- All code MUST pass the relevant linters and formatters after every major edit
  and before any commit to source control. No commit may introduce linting or
  formatting violations. Linter and formatter configuration MUST be established
  in Phase 1 Setup of every feature plan.

## Governance

This constitution supersedes all other written or verbal conventions for the
LocalSearch project. Amendments require:

1. A pull request updating this file with a version bump per the policy below.
2. A completed Sync Impact Report (HTML comment at the top of this file).
3. Review and approval by at least one maintainer.
4. A migration note if any existing feature spec, plan, or task set is
   invalidated by the amendment.

**Versioning policy**:
- MAJOR: removal or redefinition of a NON-NEGOTIABLE principle.
- MINOR: new principle or section added, or material expansion of guidance.
- PATCH: clarifications, wording fixes, non-semantic refinements.

**Compliance review**: each feature plan MUST pass the Constitution Check gate.
Non-compliance found in review MUST be resolved before merge; waivers are not
permitted without a formal amendment.

**Version**: 1.3.0 | **Ratified**: 2026-03-20 | **Last Amended**: 2026-03-20
