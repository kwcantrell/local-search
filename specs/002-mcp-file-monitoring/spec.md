# Feature Specification: MCP File Monitoring

**Feature Branch**: `002-mcp-file-monitoring`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "The agent should be able to provide a list of files they want the mcp server to monitor. The mcp server should be able to track those files through non-blocking event driven processes."

## Clarifications

### Session 2026-03-20

- Q: How does the agent receive file change notifications from the MCP server? → A: Server pushes notifications proactively via MCP (e.g., a long-running tool call streams events, or MCP resource/subscription)
- Q: When a file changes rapidly in quick succession, what should the server deliver to the agent? → A: Debounce — coalesce rapid changes into a single notification per file per time window
- Q: Which Python file-watching library should the MCP server use? → A: `watchdog` — mature, cross-platform, callback-based; thread bridging required for async
- Q: Should the monitored file list be shared across all agent sessions or isolated per session? → A: Shared global list — all connections see and modify the same monitored set
- Q: Should the MCP server monitor directories as well as individual file paths? → A: Both — registering a directory watches all files within it

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register Files for Monitoring (Priority: P1)

An agent submits a list of file paths to the MCP server. The server begins watching those files for changes and confirms registration to the agent.

**Why this priority**: Core capability — without file registration, no monitoring is possible. All other stories depend on this working correctly.

**Independent Test**: Can be fully tested by submitting a list of file paths and verifying the server confirms receipt and begins tracking, delivering the foundational monitoring capability.

**Acceptance Scenarios**:

1. **Given** the agent has a list of file paths, **When** it sends those paths to the MCP server, **Then** the server acknowledges each path and begins monitoring them.
2. **Given** the agent submits a path that does not exist, **When** the server processes the list, **Then** the server rejects that path with a descriptive error while accepting valid paths.
3. **Given** the agent submits a file path already being monitored, **When** the server processes the request, **Then** the server deduplicates the list and confirms the path is already tracked without duplicating watchers.

---

### User Story 2 - Receive File Change Notifications (Priority: P2)

After registering files, the agent is notified when a monitored file changes (created, modified, deleted, or renamed).

**Why this priority**: Without change notifications, monitoring has no value. This story delivers the core event-driven behavior.

**Independent Test**: Can be fully tested by registering a file, triggering a change to that file, and verifying the agent receives a notification describing the change type and affected file.

**Acceptance Scenarios**:

1. **Given** a file is registered and being monitored, **When** the file is modified, **Then** the agent receives a notification indicating the file path and the nature of the change.
2. **Given** a file is registered, **When** the file is deleted, **Then** the agent receives a deletion event notification.
3. **Given** a file is registered, **When** a rapid sequence of changes occurs (e.g., many writes in quick succession within a debounce window), **Then** the agent receives a single coalesced notification per debounce window rather than one per individual change, without blocking other operations.

---

### User Story 3 - Deregister Files from Monitoring (Priority: P3)

The agent can remove specific files from the monitored list, stopping future notifications for those files.

**Why this priority**: Enables the agent to manage resource usage and scope monitoring dynamically over time.

**Independent Test**: Can be fully tested by registering a file, deregistering it, triggering a change, and verifying no notification is received.

**Acceptance Scenarios**:

1. **Given** a file is being monitored, **When** the agent requests removal, **Then** the server stops watching that file and confirms deregistration.
2. **Given** the agent requests removal of a file not currently monitored, **When** the server processes the request, **Then** the server responds with an appropriate message without error.

---

### User Story 4 - Query Monitored File List (Priority: P4)

The agent can request the current list of files being monitored by the MCP server at any point.

**Why this priority**: Provides visibility and allows the agent to audit or reconcile state without relying on its own internal records.

**Independent Test**: Can be fully tested by registering several files then querying the server and verifying the returned list matches what was registered.

**Acceptance Scenarios**:

1. **Given** multiple files have been registered, **When** the agent queries the monitored file list, **Then** the server returns the current, accurate list of all tracked paths.
2. **Given** no files have been registered, **When** the agent queries the list, **Then** the server returns an empty list.

---

### Edge Cases

- What happens when the monitored file list is very large (hundreds or thousands of files)?
- How does the system handle files on network-mounted or remote file systems where events may be unreliable?
- What happens if the MCP server is restarted — are monitored files remembered or must the agent re-register?
- How does the system behave when two agents attempt to monitor the same file concurrently?
- What happens when a monitored directory is deleted along with the files inside it? (Directly applicable: directory monitoring is supported; deletion event must propagate for the directory and its contents.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent MUST be able to submit a list of one or more file paths or directory paths to the MCP server for monitoring. Registering a directory causes the server to watch all files within it (recursively).
- **FR-002**: The MCP server MUST validate submitted file and directory paths and report any invalid or inaccessible paths without rejecting the entire list.
- **FR-003**: The MCP server MUST track registered files using non-blocking, event-driven processes so that file watching does not interfere with other server operations. The `watchdog` library MUST be used for file system event detection, with its observer thread bridged into the async event loop.
- **FR-004**: The MCP server MUST emit a structured notification to the agent whenever a monitored file is created, modified, deleted, or renamed. Notifications are delivered by server-push via MCP (e.g., a long-running streaming tool call or MCP resource/subscription endpoint) — the agent does not poll.
- **FR-005**: Notifications MUST include at minimum the affected file path and the type of change event.
- **FR-006**: The agent MUST be able to deregister one or more files, causing the server to stop monitoring and emitting events for those files.
- **FR-007**: The agent MUST be able to query the current list of all files being monitored by the server.
- **FR-008**: The MCP server MUST deduplicate file paths so that the same path is never watched more than once simultaneously.
- **FR-009**: The system MUST handle bursts of rapid file change events by debouncing: coalescing multiple rapid changes to the same file within a configurable time window into a single notification, without blocking other server processes.

### Key Entities

- **MonitoredFile**: A file or directory path registered by an agent for tracking; has attributes including path, type (file/directory), registration timestamp, and current watch status. Directory entries cause recursive watching of all contained files.
- **ChangeEvent**: A record of a file system change; includes the affected file path, event type (created/modified/deleted/renamed), and timestamp.
- **MonitoredFileList**: The single, server-global collection of all currently registered MonitoredFile entries. All agent connections share and mutate the same list; there is no per-session isolation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent can register a list of files and receive confirmation within 1 second under normal load.
- **SC-002**: The server delivers change notifications to the agent within 2 seconds of the underlying file system event occurring.
- **SC-003**: The server correctly handles a monitored list of at least 500 files without degradation in notification delivery time.
- **SC-004**: During a burst of 50 rapid successive changes to a monitored file within a debounce window, the agent receives exactly one coalesced notification per debounce window rather than 50 individual events, and no notification is delivered for changes that have been superseded within the same window.
- **SC-005**: All server operations (registration, querying, deregistration, event delivery) complete without blocking each other under concurrent usage.
- **SC-006**: 100% of invalid file paths in a submitted list are reported back to the agent with descriptive errors, while all valid paths are successfully registered.

## Assumptions

- The MCP server runs on the same host as the files being monitored (native file system events are available).
- File monitoring state is not persisted across server restarts; agents must re-register files after a restart.
- There is a single agent interacting with the server in the initial implementation; multi-agent concurrency is an edge case to handle gracefully but not a primary design target. The monitored file list is global and shared — not scoped per session or connection.
- The maximum file list size per registration request is not explicitly bounded but reasonable limits (e.g., 1000 paths per call) are acceptable.
- Notifications are delivered to the agent via the existing MCP communication channel using server-push (no separate notification transport, no polling required).
- `watchdog` is the designated file-watching library; its observer runs in a background thread and events are forwarded to the async event loop via a thread-safe queue or callback bridge.
