# Notification Flow

This diagram shows notification Slice 1 for user registration. The API stores
the user and welcome-email intent atomically, then returns without contacting
SMTP. A separate worker claims and delivers unpublished notifications.

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API as Backend API
    participant DB as Postgres
    participant Worker as Notification Worker
    participant SMTP as SMTP server

    User->>Frontend: Submit registration
    Frontend->>API: POST /users/signup
    API->>DB: BEGIN
    API->>DB: INSERT user
    API->>DB: INSERT notification outbox row
    alt Either insert fails
        API->>DB: ROLLBACK
        API-->>Frontend: Registration error
    else Both inserts succeed
        API->>DB: COMMIT user and outbox row
        API-->>Frontend: UserPublic
        Frontend-->>User: Registration complete
    end

    Note over API,SMTP: Signup does not contact SMTP

    loop Poll for unpublished notifications
        alt Email delivery is disabled
            Worker->>Worker: Sleep without claiming or sending
        else Email delivery is enabled
            Worker->>DB: BEGIN
            Worker->>DB: SELECT row FOR UPDATE SKIP LOCKED
            alt No row available
                DB-->>Worker: No notification
                Worker->>DB: ROLLBACK read transaction
                Worker->>Worker: Sleep until next poll
            else Row claimed
                DB-->>Worker: Registered user payload
                Worker->>Worker: Render welcome email
                Worker->>SMTP: Send welcome email
                alt SMTP succeeds
                    SMTP-->>Worker: Successful response
                    Worker->>DB: Set published_at to UTC time
                    Worker->>DB: COMMIT
                else SMTP fails or worker stops before commit
                    Worker->>DB: Transaction rolls back
                    Note over Worker,DB: published_at remains NULL and the row can be claimed again
                end
            end
        end
    end
```

The worker holds the row lock while sending. Other worker instances skip the
locked row, while a crash or SMTP failure rolls back the transaction and leaves
the notification eligible for a later delivery attempt.
