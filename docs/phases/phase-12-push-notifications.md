# Phase 12: Push notifications

## Goal

Deliver OS-level push notifications to the Android client, so a user learns that
something happened without opening the app.

Push is added as one more channel on the notification infrastructure built in
phase 8, alongside email and the in-app feed.

There is no ROADMAP item for this yet. It is adjacent to ROADMAP 5.1 (Android
client) and 6.7 (notifications for shared content), and should be added to
ROADMAP.md when this phase is scheduled.

## Product and technical decisions

1. **Firebase Cloud Messaging is the only realistic option, and it is not a
   preference.** Android only accepts notifications from FCM; there is no
   self-hosted path for a normal consumer app. Wrappers such as OneSignal or
   Pusher Beams sit on top of FCM and solve segmentation and campaign problems
   this project does not have. UnifiedPush requires users to install a separate
   distributor app.

   This makes FCM the **first mandatory external service dependency** in a stack
   that is otherwise entirely self-hosted — Postgres, MinIO, RabbitMQ, Traefik and
   Elasticsearch all run in compose. Unlike earlier decisions where an external
   dependency was weighed and rejected, here there is nothing to weigh: it is the
   cost of entry.

2. **Push never replaces the in-app feed.** FCM is best-effort and offers no
   delivery guarantee. The `notifications` table from phase 9 remains the source
   of truth for what a user has been told; push is a nudge that something arrived.
   A user who misses every push must still see everything in the feed.

3. **The delivery half is one more consumer; the prerequisite half is a whole
   feature.** Phase 8 decision 4 promised that adding a channel is a queue
   binding plus a consumer, and that holds — `q.push` and a sender are small.
   Roughly four fifths of this phase is device-token lifecycle and application
   configuration, which the phase 8 architecture does not help with. Sizing this
   as "another channel" would badly underestimate it.

4. **Device tokens are the actual work.** Tokens rotate on reinstall, on data
   clear, on device restore, and periodically for no reason at all. A token is a
   per-installation identifier, not a per-user one, so the same device can carry
   different users over time and one user can hold several tokens at once.

5. **FCM only reports a dead token when you try to send to it.** The consumer must
   delete tokens on `UNREGISTERED` and `NOT_FOUND` responses. Without that, dead
   tokens accumulate forever and every send wastes quota on devices that will
   never receive anything.

6. **Unregistering on logout is a security requirement, not hygiene.** If a token
   survives logout, the next person to sign in on that device receives the
   previous user's notifications — including file names. This is a data leak, and
   it is easy to omit because nothing fails visibly when you do.

7. **One user has many devices.** Sends fan out to every token the user holds,
   and each result is handled independently: one dead token must not abort
   delivery to the others.

8. **Development and production need separate Firebase projects.** The
   `google-services.json` bundled into the app is per-project, so sharing one
   means development pushes reaching production devices.

9. **Delivery cannot be verified in CI, and that breaks the project's usual
   pattern.** There is no mailcatcher equivalent for FCM, emulators need Google
   Play Services images, and no test suite can meaningfully assert that a
   notification arrived on a handset. This phase therefore needs a written manual
   verification procedure, in the same spirit as the broker durability checks
   recorded in phase 8.

10. **The schema is not Android-only even though the client is.** `device_tokens`
    carries a `platform` column from the start. iOS and APNs are out of scope, but
    a schema that assumes Android would need a migration rather than a row.

11. **Not every event pushes.** Push is intrusive in a way email is not.
    `file_shared` is a reasonable push; `user_registered` obviously is not, since
    the user is holding the phone at the time. Which events push is a per-event
    decision recorded in the bindings, not a property of the channel.

## Architecture

```
notification_outbox ──► relay ──► RabbitMQ exchange: notifications
                                        │
                     ┌──────────────────┼──────────────────┐
                     ▼                  ▼                  ▼
                  q.email            q.inapp            q.push          ← added here
                     │                  │                  │
              email consumer     inapp consumer      push consumer
                     │                  │                  │
                     ▼                  ▼                  ▼
                   SMTP        notifications table    FCM ──► device
```

Everything left of `q.push` already exists. The consumer looks up the recipient's
device tokens, sends to each, and prunes the ones FCM rejects.

## Data model

```sql
device_tokens
  id            uuid         PRIMARY KEY
  user_id       uuid         NOT NULL  FK user.id  ON DELETE CASCADE
  token         text         NOT NULL  UNIQUE
  platform      text         NOT NULL            -- 'android' for now
  created_at    timestamptz  NOT NULL
  last_seen_at  timestamptz  NOT NULL

  INDEX (user_id)
```

`token` is unique globally, not per user: the same device registering under a
second account must move the token rather than duplicate it, which is what makes
decision 6 enforceable.

Per repository convention, every index and constraint is mirrored in the model's
`__table_args__` so autogenerate reports no drift.

## Token lifecycle

```
  login              → obtain token from FCM, register with backend
  token refresh      → re-register (FCM raises this on its own schedule)
  logout             → UNREGISTER, or the next user on this device
                       receives the previous user's notifications
  send fails with
   UNREGISTERED /    → delete the row; the device is gone
   NOT_FOUND
  app uninstalled    → discovered only on the next send, as above
```

There is no event for uninstall. Dead tokens are found lazily, by failing to send
to them, which is why decision 5 is load-bearing rather than tidying.

## Slice breakdown

### Slice 1 — device token registration

`device_tokens` table; register and unregister endpoints; `firebase_messaging` in
the Flutter app; runtime `POST_NOTIFICATIONS` permission on Android 13+; register
on login, re-register on refresh, unregister on logout; Firebase project setup
for development.

This slice delivers nothing a user can see, which sits awkwardly with the
vertical-slicing rule in `docs/project-management.md` §4. It is separated anyway
because it is large enough to swamp the slice that follows. Merging slices 1 and
2 into one demoable piece — "share a file, the phone buzzes" — is a legitimate
alternative if the combined size is acceptable.

### Slice 2 — push delivery for `file_shared`

`q.push` binding and dead-letter queue; a push consumer that fans out to a user's
tokens and prunes rejected ones; the FCM service-account credential in the deploy
pipeline; the manual verification procedure from decision 9.

### Slice 3 — tap to open

Deep linking so tapping a notification opens the relevant file or folder rather
than the app's default screen.

## Acceptance flow

1. A user signs in on an Android device and grants notification permission.
2. The device's FCM token is registered against that user.
3. Another user shares a file with them.
4. The event reaches `q.push`; the consumer sends to every token the recipient
   holds.
5. The notification appears on the device with the app closed.
6. Tapping it opens the shared file.
7. The same notification is also present in the in-app feed, which remains
   authoritative.
8. The user signs out; the token is unregistered and the device stops receiving
   their notifications.
9. A token FCM reports as dead is removed on the next send.

## Out of scope

- iOS and APNs. The client is Android-only; `platform` exists so this does not
  require a migration later.
- Web push for the React client. Different mechanism (VAPID), different plumbing.
- Marketing, campaign or broadcast pushes. Only event-driven notifications.
- Silent data-sync pushes.
- Rich notifications — images, action buttons, grouping.
- Delivery receipts or read tracking.

## Open questions

1. **What goes in the push payload?** This is specific to a file-storage product
   and worth deciding deliberately rather than defaulting to whatever an FCM
   tutorial does.

   ```
   CONTENT PUSH                        DATA-ONLY PUSH
   "Alice shared tax_return.pdf"       "You have a new notification"
   better UX, readable at a glance     app fetches details on open
   filename passes through Google      nothing sensitive leaves our servers
   ```

   Recommendation: a generic title with the details fetched on tap, or at most a
   sender name without a file name. Sending customer file names through a third
   party is a poor default for a product whose whole purpose is storing private
   files.

2. **Do per-user notification preferences come along in this phase?**
   Preferences have been deliberately out of scope since phase 9, and email
   without an opt-out is tolerable. An unmutable push is a much larger imposition,
   and the usual first complaint about any push feature is that it cannot be
   turned off.

   Recommendation: include at minimum a per-channel on/off switch for push in
   this phase, even if full per-event preferences stay deferred.
