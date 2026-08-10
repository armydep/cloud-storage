# Phase 9: In-app notifications

## Goal

Show users a notification feed inside the web and mobile clients: a bell with an
unread count, a list of recent notifications, and the ability to mark them read.

The feed reuses the Phase 8 notification infrastructure. In-app is added as a
**channel**, not as a new pipeline — a queue binding and a consumer whose
delivery is a database row rather than an SMTP message.

The first event shown in the feed is `file_shared`, which advances ROADMAP 6.7.

## Product and technical decisions

1. **In-app is a channel on the existing pipeline.** A `q.inapp` queue binds to
   the `notifications` exchange from Phase 8, and an in-app consumer inserts a
   row. Nothing about `notification_outbox`, the relay, or the email consumer
   changes. This is the first real test of Phase 8 decision 4.

2. **The feed is a read model, not a queue.** `notification_outbox` rows are
   transient work items; `notifications` rows are durable, user-facing records
   with read state. They are different tables with different lifetimes and are
   not merged.

3. **`notifications.outbox_id` is UNIQUE.** Phase 8 delivery is at-least-once, so
   the in-app consumer will eventually receive the same event twice. For email a
   duplicate is a second message; for a feed it is a visibly duplicated row. The
   unique constraint makes redelivery a no-op.

4. **`create_file_share` must stop committing internally.** It currently commits
   (`app/files/repository.py:219`), so the outbox insert would land in a separate
   transaction. It gains `commit: bool = True`, exactly as `crud.create_user` did
   in Phase 8.

5. **Clients poll; there is no push transport.** A 15–30 second poll is
   sufficient for this content. SSE and WebSocket are deliberately rejected for
   now: route handlers are synchronous `def` and run in a 40-thread pool
   (`docs/scalability-review.md` SCALE 2.3), so each held-open connection pins a
   thread and the API stops serving everything else at roughly 40 concurrent
   clients. A push transport also needs a cross-worker backplane, because the
   backend runs `--workers 4`.

6. **Notifications are rendered client-side from a structured payload.** The row
   stores `event_type` and `payload`, not rendered text. This keeps wording and
   translation out of the database and lets copy changes apply to existing rows.
   The cost is a small render mapping in both TypeScript and Dart.

7. **Keyset pagination on `(created_at, id)`.** Not offset. The lesson is already
   recorded in SCALE 1.1 and 4.3, and unlike `files` this table has `created_at`
   from the start.

8. **`user_registered` is not shown in the feed.** The user is present when it
   happens. Only events that are useful after the fact are bound to `q.inapp`.

9. **`file_shared` is delivered on both channels.** It binds to `q.email` and
   `q.inapp`, so a recipient gets an email *and* a feed entry. The event is
   emitted once; the two bindings are independent. This requires a `file_shared`
   email template and builder alongside the feed row.

10. **Feed rows are kept indefinitely.** There is no retention or archival job.
    Accepted deliberately: the partial unread index keeps the badge query cheap
    regardless of table size, and the feed query is keyset-paginated on
    `(user_id, created_at DESC)`, so read performance does not degrade with row
    count. Revisit if table size itself becomes an operational problem.

11. **Read state is per notification.** Opening the feed does not mark everything
    read; each notification is marked individually. A mark-all-read action
    remains available as an explicit user choice.

## Architecture

```
 notification_outbox ──► relay ──► RabbitMQ exchange: notifications
                                          │
                             ┌────────────┴────────────┐
                             ▼                         ▼
                          q.email                   q.inapp        ← added here
                             │                         │
                       email consumer          in-app consumer
                             │                         │
                             ▼                         ▼
                           SMTP            INSERT notifications
                                                       │
                                             ┌─────────┴─────────┐
                                             ▼                   ▼
                                        React SPA           Flutter app
                                        GET /notifications (poll)
```

Everything left of `q.inapp` already exists from Phase 8.

## Data model

```sql
notifications
  id          uuid         PRIMARY KEY
  outbox_id   uuid         NOT NULL UNIQUE   -- idempotency, decision 3
  user_id     uuid         NOT NULL  FK user.id  ON DELETE CASCADE
  event_type  text         NOT NULL
  payload     jsonb        NOT NULL
  created_at  timestamptz  NOT NULL
  read_at     timestamptz  NULL              -- NULL = unread

  INDEX (user_id, created_at DESC)              -- the feed query
  INDEX (user_id) WHERE read_at IS NULL         -- unread count
```

Per repository convention, every index and constraint is mirrored in the model's
`__table_args__` so autogenerate reports no drift.

## API

```
GET  /api/v1/notifications?limit=&cursor=&unread_only=
GET  /api/v1/notifications/unread-count
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/read-all
```

Constraints go on `Query(...)` so they reach the OpenAPI schema and therefore the
generated client. Every query filters on the owning user; another user's
notification returns 404, never 403.

## Slice breakdown

Mirrors the backend / frontend / mobile split already used by Phase 7.

### Slice 1 — backend: `file_shared` event, feed table, consumer, API

`commit=False` on `create_file_share`; emit a `file_shared` outbox row inside the
share transaction; migration and model for `notifications`; `q.inapp` queue bound
to `file_shared` and the existing `q.email` bound to it as well; a `file_shared`
email template and builder; the in-app consumer; the four endpoints above.

### Slice 2 — web: notification bell and feed in the React SPA

Bell with unread count, dropdown or page listing notifications, per-notification
mark-read, mark-all-read, polling every 15–30 seconds with backoff when the tab
is hidden. Client-side rendering of `file_shared`.

### Slice 3 — mobile: notification feed in the Flutter client

The same feed and read behaviour in the Android app, using the same endpoints.

## Acceptance flow

1. Alice shares a file with Bob.
2. The `file_shares` row and one `notification_outbox` row commit together.
3. The relay publishes; the exchange routes the event to **both** `q.email` and
   `q.inapp`.
4. The email consumer sends Bob a "file shared with you" email. Independently,
   the in-app consumer inserts a `notifications` row for Bob, unread.
5. Bob's client polls, sees an unread count of 1, and displays "Alice shared
   `report.pdf` with you".
6. Bob opens that notification; it is marked read individually and the badge
   decrements. Other unread notifications are unaffected.
7. Redelivery of the same event inserts no second feed row.

## Out of scope

- OS-level push while the app is backgrounded (FCM/APNs). That needs
  `firebase_messaging`, a device-token table, permission grants and token
  rotation — a feature in its own right, not a channel.
- SSE or WebSocket transport. See decision 5.
- Per-user notification preferences or muting.
- Notification grouping, digests, or summaries.
- Events other than `file_shared` in the feed.

## Open questions

None currently open. The three questions raised when this phase was drafted are
resolved as decisions 9, 10 and 11.

Two consequences were accepted knowingly and are worth revisiting if they bite:

- **Share notifications cannot be turned off.** Decision 9 sends both an email
  and a feed entry for every share, and there are no preferences (out of scope).
  A user sharing many files with the same person will generate one email each
  time. Per-user notification preferences are the mitigation when it becomes a
  complaint.
- **The `notifications` table grows without bound.** Decision 10 accepts this.
  Query performance is protected by the indexes, so the first symptom would be
  storage or backup size rather than latency.
