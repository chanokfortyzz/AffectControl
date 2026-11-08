# Real native S1 → Sage transport continuity audit (November 8, 2026)

**Mode:** actual data, strictly read-only. Research status **E1**, not a production scheduler intervention.

## Two distinct Sage-related transport paths in the live S1 source

Source inspected from the actual installed S1 project:

**Path A: Native task manager → Sage Bridge**
- `backend/app/tasks.py` creates the native S1 task, routes to `SageAdapter.submit_task`.
- `backend/app/sage.py` appends an S1 request with `s1_ref` and proposed `TASK-S1-...` provider task ID to `04-MAC_OUTBOX.md` and invokes the Bridge push.
- Native S1 stores `s1_task_id ↔ provider_task_id` in `agent_executions`, and monitors the `02-MAC_TASK_QUEUE.md` card and `07-MAC_TASK_STATE.json`.
- When a provider task is reported complete and a result file exists, the S1 task manager may register that result. Neither presence of a result file nor a provider `COMPLETED` state establishes independent business acceptance.

**Path B: Separate S1 Sage Bus gateway → WebClip**
- `backend/app/sage_relay.py` calls `POST /v1/bus/requests` via the separately configured Sage gateway and receives `request_id`, `message_id`, optional `thread_id`.
- That path logs `sage_bus_submitted` / `sage_bus_reply_received` with gateway metadata, but currently leaves the S1 event's native `task_id` empty and does NOT associate it with `agent_executions`.
- The calls are exposed by separate `backend/app/main.py` endpoints. They are not the `SageAdapter.submit_task` method used by the native task dispatcher.

Consequently, Path A's `provider_task_id` is not a WebClip `msg-...` identifier. The two mechanisms must not be joined by similar labels, timestamps, titles or status strings.

## Actual source census

Ran `benchmarks/native_sage_continuity_audit.py` against the user's S1 SQLite file and locally available Sage Bridge queue, watchdog state, and result directory.

| Evidence field | Count |
|---|---:|
| Native S1 → Sage provider mappings | **3** |
| Provider status COMPLETED in native DB | 2 |
| Provider status CREATED in native DB | 1 |
| Present in current `02-MAC_TASK_QUEUE.md` | **0/3** |
| Present in current `07-MAC_TASK_STATE.json` | **0/3** |
| Mappings with a nonempty result file | **2/3** |
| COMPLETED mappings with a nonempty result file | **2/2** |
| Mappings without a result file | 1 |
| Native S1 → authenticated WebClip message joins | **0** |

The current queue snapshot has only **one card**; its source file was last modified October 30, 2026. The separate watchdog file has **76 task entries** and was generated November 8, 2026, but none matches these three stored native provider IDs. This could represent archival/rotation, delayed indexing or a real source reconciliation gap. It is not proof that older tasks never ran: two exact-ID result files exist and were nonempty at the time of inspection.

Native S1 contains 9 tasks in total, with **zero nonempty `due_at`** values. Even a future nonempty value would need original user-origin/deadline provenance before E2 admission.

## Executed program and privacy limits

The new census code opens native S1 SQLite in URI read-only + `PRAGMA query_only` mode, parses the local queue and state snapshots, checks for exact provider IDs and exact source `s1_ref` matches, and checks result-file existence/nonempty bytes. It never evaluates result quality, writes to Sage/S1, dispatches requests, acknowledges Bus messages or reads raw prompts for inclusion in its report.

The report contains counts and an aggregate fingerprint of result content hashes. No task titles, raw prompts, user IDs, provider IDs, result text or credential material are published in Git. The actual private report stays under ignored `.research-data`.

Nine portable synthetic tests include exact matches, missing current card, nonempty vs empty result file, forged/mismatched `s1_ref`, duplicate IDs, unsafe provider paths, state corruption, symlinked result files, repeatability and unchanged input files.

## Correct next source-level integration

1. Preserve native S1's existing `tasks.id`, `agent_executions.s1_task_id` and provider card ID. Do **not** invent a duplicate task namespace.
2. Choose and make explicit which downstream transport actually carries each native task. If the **Sage Bridge outbox** remains authoritative, require Sage's authoritative card/event to record the native ID and any separate WebClip Bus request ID it truly originated. Never synthesize a Bus ID from `TASK-S1`.
3. If a native task is intentionally sent through **`sage_relay`** instead, pass a trusted native task ID at the originating API boundary and persist the actual gateway-returned request/message/thread IDs with original timestamps in a separate append-only source record. Changing native dispatch routing requires its own safety and regression review.
4. Verify Bus sender identity and message parent relationship against its source of truth. Bind original request/token/event hashes and protect trust keys independently. Only then create a source-authenticated native S1 ↔ Sage ↔ Bus attribution.
5. Separately capture user-provided deadlines at intake and independent outcome acceptance. None was established by this source census.

**Nothing in this work changes the live native S1 schema, Sage agent cards, WebClip Bus state, user task dispatch or existing result files.** The draft AffectControl PR remains research-only; E1 evidence level stays unchanged.
