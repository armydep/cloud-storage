import 'package:flutter/foundation.dart';

/// What the background handler needs to show a local notification, derived
/// from a data-only FCM message (design doc decision 12: no file names, a
/// generic title, the event type and identifiers only).
@immutable
class PushMessageContent {
  const PushMessageContent({required this.notificationId, required this.title});

  /// Derived from the server's `notification_id` (the outbox event's id), so
  /// redelivering the same event (delivery is at-least-once) replaces the
  /// existing tray notification instead of stacking a duplicate one.
  final int notificationId;
  final String title;
}

const _defaultTitle = 'You have a new notification';

/// Only `file_shared` exists today (design doc decision 11: which events
/// push is a per-event decision, not a channel property) -- an unrecognized
/// event type is ignored rather than shown with a blank body.
const _supportedEventTypes = {'file_shared'};

/// Parses `RemoteMessage.data` into displayable content, or `null` when the
/// message is not one this app shows a notification for.
PushMessageContent? parsePushMessageData(Map<String, dynamic> data) {
  final eventType = data['event_type'];
  if (eventType is! String || !_supportedEventTypes.contains(eventType)) {
    return null;
  }

  final notificationIdSource = data['notification_id'];
  if (notificationIdSource is! String) {
    // Fail closed rather than falling back to a shared id derived from
    // `eventType` -- that would silently collapse unrelated notifications
    // (different events, different recipients even) onto the same Android
    // notification id and have them replace one another in the tray. The
    // server always sends `notification_id`, so this should not happen in
    // practice; treat it the same as an unsupported event type instead of
    // guessing at an id.
    return null;
  }

  final title = data['title'];
  return PushMessageContent(
    notificationId: stableNotificationId(notificationIdSource),
    title: title is String && title.isNotEmpty ? title : _defaultTitle,
  );
}

/// A deterministic, positive 31-bit hash (FNV-1a) of [value].
///
/// Not [String.hashCode]: Dart does not guarantee that is stable across
/// isolates or app runs, and the whole point of this id is that the same
/// server-side event always maps to the same Android notification id so a
/// redelivered event replaces rather than duplicates.
int stableNotificationId(String value) {
  const fnvOffsetBasis = 0x811c9dc5;
  const fnvPrime = 0x01000193;
  var hash = fnvOffsetBasis;
  for (final byte in value.codeUnits) {
    hash ^= byte;
    hash = (hash * fnvPrime) & 0xFFFFFFFF;
  }
  // Android notification ids are a signed 32-bit int; mask off the sign bit
  // so this is always non-negative.
  return hash & 0x7FFFFFFF;
}
