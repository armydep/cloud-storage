# Phase 8: Notification infrastructure

## Goal

Give the project a minimal, general notification infrastructure: business events
are recorded in the same transaction as the write that caused them, relayed to a
message broker, and delivered by a per-channel consumer.

The first event delivered through it is a welcome email on registration, which
completes ROADMAP 4.1. The same infrastructure is the foundation for ROADMAP 4.3
(quota notifications) and ROADMAP 6.7 (shared-content notifications).

This phase deliberately builds the smallest infrastructure that supports future
events and channels, not the full notification system.

## Product and technical decisions

1. **The outbox is written in the same transaction as the business write.** A
   notification intent and the row that caused it commit together or not at all.
   This is the entire reason the pattern exists: no ordering of two independent
   systems gives atomicity, so the durable record must live in the same database
   as the business data.

2. **`crud.create_user` must stop committing internally.** It currently commits
   (`app/crud.py:15`), so an outbox insert placed after it would run in a
   separate transaction and the guarantee above would not hold. It gains a
   `commit: bool = True` parameter, mirroring the existing
   `repository.create_file(..., commit=False)` pattern
   (`app/files/repository.py:435`).

3. **The broker owns delivery retry.** Failed deliveries are nacked and
   redelivered by RabbitMQ, with a dead-letter exchange as the terminal
   destination. The outbox table therefore carries no `attempts` or
   `next_attempt_at` columns.

4. **Fan-out happens at the broker, not at enqueue time.** One outbox row is one
   event. Queue bindings decide which channels receive it, so adding a channel
   is configuration rather than a schema migration.

5. **Delivery is at-least-once end to end.** Consumers must tolerate receiving
   the same event twice. Exactly-once is not achievable across SMTP or any
   external provider.

6. **The relay never talks to a provider.** Its only job is moving rows from the
   outbox to the exchange. Rendering and delivery belong to consumers.

7. **The relay marks a row published only after the broker confirms.** Publisher
   confirms are required. Without them a broker crash between publish and
   persist would silently lose the event.

8. **RabbitMQ durability is load-bearing, not belt-and-braces.** Once
   `published_at` is set, the outbox no longer backstops the message. Durable
   exchange, durable queue, persistent messages, and a named volume on
   `/var/lib/rabbitmq` are all required together — missing any one breaks the
   guarantee silently.

9. **Worker processes reuse the backend image.** The relay and the consumer are
   different entrypoints into the same package, deployed as separate compose
   services. They share models, settings, templates, and one Alembic chain. A
   separate codebase would mean a second implementation of a schema it does not
   own.

## Architecture

```
   API request                        ┌─────────── RabbitMQ ───────────┐
   (same transaction)                 │                                 │
        │                             │  exchange: notifications        │
        ▼                             │      (topic)                    │
 ┌─────────────────┐                  │        │                        │
 │ Postgres        │   relay          │        ├─► q.email  ──┐         │
 │ notification_   │ ────────────────►│        ├─► q.sms    ──┼──┐      │
 │    outbox       │   publish        │        └─► q.push   ──┼──┼──┐   │
 └─────────────────┘                  └──────────────────────┼──┼──┼───┘
        ▲                                                     │  │  │
        │ INSERT event                                        ▼  ▼  ▼
   business write                                        ┌──────────────┐
                                                          │  consumers   │
                                                          │  → providers │
                                                          └──────────────┘
```

Only two processes are written here: the relay and the consumer. Everything else
is a table, an exchange, and queue bindings.

Routing key is `event_type`. Each channel queue binds to the events it cares
about, so `q.sms` is not woken by events it would discard.

## Data model

```sql
notification_outbox
  id            uuid         PRIMARY KEY
  event_type    text         NOT NULL      -- 'user_registered'
  payload       jsonb        NOT NULL      -- who and what
  created_at    timestamptz  NOT NULL
  published_at  timestamptz  NULL          -- NULL = not yet published

  CREATE INDEX ... ON notification_outbox (created_at)
    WHERE published_at IS NULL;            -- partial, stays small as the table grows
```

Five columns. `published_at` doubles as status and audit, so there is no status
enum. There is no `channel` column, per decision 4, and no retry columns, per
decision 3.

Per repository convention, every index and constraint is mirrored in the model's
`__table_args__` so autogenerate reports no drift.

## Delivery guarantees

```
business write → outbox     ATOMIC          same transaction
outbox → broker             at-least-once   relay may republish after a crash
broker → consumer           at-least-once   ack-based redelivery
──────────────────────────────────────────────────────────────
end to end                  at-least-once
```

Failure behaviour at each step:

| Crash point | Outcome |
| --- | --- |
| After business commit, before publish | Row still `NULL`, relay picks it up next poll |
| Publish sent, broker never received it | No confirm, `published_at` stays `NULL`, relay republishes |
| Broker confirmed, relay died before marking | Broker has it *and* the row is `NULL` — event is delivered twice |
| Broker restart after confirm | Survives only on the durability settings in decision 8 |
| Consumer crash before ack | Broker redelivers |

## Slice breakdown

Each slice is independently shippable. The broker is deliberately absent from
slice 1 so that ROADMAP 4.1 lands inside the three-day size rule in
`docs/project-management.md` §4; the table and the enqueue code are identical
either way.

### Slice 1 — outbox table and welcome email delivered by a worker (#102)

Migration and model for `notification_outbox`; `commit=False` on
`crud.create_user`; transactional enqueue in `register_user`
(`app/api/routes/users.py:145`); a worker that polls, claims with
`FOR UPDATE SKIP LOCKED`, renders, sends, and sets `published_at`; a
`notification-worker` compose service; a welcome template.

Completes ROADMAP 4.1.

### Slice 2 — introduce RabbitMQ, split the worker into relay and consumer (#103)

A `rabbitmq` compose service with a durable volume; topic exchange
`notifications`; queue `q.email` bound to `user_registered`; a dead-letter
exchange; the slice-1 worker split into a relay and a consumer.

No user-visible change. The value is operational: retry and dead-lettering move
out of application code.

#### Operational verification procedure

Run this against an isolated Compose project so the normal development volumes
are not modified. Start from a fresh copy of `.env.example`, then:

```bash
docker compose -p cfs-notification-verify up -d --build \
  backend frontend adminer notification-relay notification-consumer \
  mailcatcher minio-create-bucket
docker compose -p cfs-notification-verify ps -a
```

Wait until `db`, `rabbitmq`, and `backend` report healthy. `prestart` and
`minio-create-bucket` are expected to exit with status `0` after their one-time
work completes.

Use `POST /api/v1/users/signup` to enqueue a uniquely addressed user for each
step. Inspect queue depths with:

```bash
docker compose -p cfs-notification-verify exec rabbitmq \
  rabbitmqctl list_queues name messages_ready messages_unacknowledged
```

1. Register a user with all services running. Confirm the welcome message
   appears at `http://localhost:1080` and both notification queues are empty.
2. Stop `notification-consumer`, register another user, and confirm `q.email`
   has one ready message. Start the consumer and confirm the queue drains and
   the message appears in Mailcatcher.
3. Remove the consumer container with
   `docker compose -p cfs-notification-verify rm -sf notification-consumer`
   (Compose otherwise restarts dependents when RabbitMQ restarts). Register
   another user and record the non-zero `q.email` depth. Run
   `docker compose -p cfs-notification-verify restart rabbitmq`, wait for
   health, and confirm the depth is unchanged.
4. Recreate the broker with
   `docker compose -p cfs-notification-verify up -d --force-recreate rabbitmq`.
   Wait for health and confirm the queued message remains. This step proves the
   named `/var/lib/rabbitmq` volume; a restart alone does not.
5. Recreate the consumer with
   `docker compose -p cfs-notification-verify up -d notification-consumer` and
   confirm the preserved message drains.
6. Stop `mailcatcher`, register another user, and leave the consumer running.
   After the quorum queue's delivery limit is reached, confirm `q.email` is
   empty and `q.email.dead-letter` contains the failed message. Start
   Mailcatcher again when finished.

Clean up only the isolated verification project:

```bash
docker compose -p cfs-notification-verify down -v --remove-orphans
```

Verification run on 2026-08-10:

- Fresh `.env.example` stack: all long-running services started; signup produced
  a welcome message in Mailcatcher.
- Consumer stopped: `q.email` accumulated one message; starting the consumer
  drained it.
- Broker restart: the queued message count remained `1`.
- Broker container recreation: the queued message count remained `1`, and the
  `/var/lib/rabbitmq` mount was confirmed as the named
  `cfs-notification-verify_rabbitmq-data` volume.
- SMTP unavailable: after five failed deliveries, `q.email` was empty and
  `q.email.dead-letter` contained one message.

The recreation check requires the stable `hostname: rabbitmq` setting in
addition to the named volume. Without it, RabbitMQ derives its node name from
the generated container hostname and does not recover the prior node's data
after recreation.

### Later, not yet scheduled

A second event, to prove the infrastructure generalises. `file_shared` is the
natural candidate because sharing already exists (ROADMAP 6.1), so no detector
is needed.

A second channel. Both non-email channels have prerequisites that do not exist
yet: there is no phone field on `User` (`app/models.py:14-20`), and the Flutter
app has no push integration (no `firebase_messaging` in `mobile/pubspec.yaml`).
Each is a feature in its own right before it is a channel.

## Acceptance flow

1. A user registers through `POST /users/signup`.
2. The user row and one `notification_outbox` row commit in the same
   transaction. The response returns without waiting on SMTP.
3. The relay claims the unpublished row, publishes it to the `notifications`
   exchange with routing key `user_registered`, and sets `published_at` only
   after the broker confirms.
4. `q.email` receives the message. The email consumer renders the welcome
   template and sends it through SMTP, then acks.
5. On the local stack the message appears in mailcatcher.
6. Stopping the consumer causes messages to accumulate in `q.email`; starting it
   drains them. Restarting the broker does not lose them.

## Out of scope

- Retry columns on the outbox — the broker owns retry
- User notification preferences, and the consent records SMS would legally
  require
- Delivery-status webhooks (bounces, complaints, dead push tokens) and a
  suppression list
- Retention and archival of published rows
- `user_logged_in` as an event. Its volume is unbounded, and the useful version
  is "login from a new device", which is a security feature needing device
  fingerprinting rather than a notification row
- An in-app notification feed. A feed is a read model with different access
  patterns, not a delivery queue

## Open questions

1. **Is ROADMAP 6.7 email, an in-app feed, or both?** A feed is a read model,
   not a delivery queue. This is also the only scenario that would justify the
   broker on fan-out grounds rather than retry grounds, since it would introduce
   a genuinely independent second consumer of the same event.

2. **Who detects `quota_reached`?** It is a condition, not an event — nothing
   emits it. Either checked after each upload or scanned on a schedule. It
   should stay out of the consumer either way, in the same spirit as the
   detection/delivery split in the orphan-cleanup work.

3. **Retention for published rows.** They currently accumulate forever. This is
   answerable cheaply while registration is the only event, and becomes
   unavoidable if higher-volume events are added later.
