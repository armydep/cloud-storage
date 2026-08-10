# Notification Flow

This diagram shows the broker-backed notification flow. Registration remains
independent of SMTP: the API commits the user and outbox row together, the relay
moves the event to RabbitMQ, and the email consumer performs delivery.

```mermaid
sequenceDiagram
    participant User
    participant API as Backend API
    participant DB as Postgres
    participant Relay as Notification Relay
    participant MQ as RabbitMQ
    participant Consumer as Email Consumer
    participant SMTP as SMTP server

    User->>API: POST /users/signup
    API->>DB: BEGIN
    API->>DB: INSERT user
    API->>DB: INSERT notification outbox row
    API->>DB: COMMIT both rows
    API-->>User: UserPublic

    loop Poll unpublished rows
        Relay->>DB: SELECT row FOR UPDATE SKIP LOCKED
        DB-->>Relay: Registered user event
        Relay->>MQ: Publish persistent message
        alt Broker confirms publish
            MQ-->>Relay: Publisher confirm
            Relay->>DB: Set published_at and COMMIT
        else Publish is not confirmed
            Relay->>DB: ROLLBACK
            Note over Relay,DB: Row remains unpublished
        end
    end

    MQ->>Consumer: Deliver from q.email
    alt Email delivery succeeds
        Consumer->>SMTP: Send welcome email
        SMTP-->>Consumer: Accepted
        Consumer->>MQ: ACK
    else Email delivery fails
        Consumer->>MQ: Reject and requeue
        alt Delivery limit not reached
            MQ->>Consumer: Redeliver message
        else Delivery limit reached
            MQ->>MQ: Dead-letter to q.email.dead-letter
        end
    end
```

The `notifications` topic exchange, `q.email`, and dead-letter topology are
durable. Messages are persistent and the broker data directory is backed by a
named volume. Delivery is at-least-once: a relay crash after broker confirmation
but before the database commit can publish the same event again.
