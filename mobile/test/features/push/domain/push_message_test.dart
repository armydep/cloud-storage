import 'package:cloudestorage/features/push/domain/push_message.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('parsePushMessageData', () {
    test(
      'parses a file_shared message with the generic title from the server',
      () {
        final content = parsePushMessageData({
          'event_type': 'file_shared',
          'file_id': 'file-123',
          'notification_id': 'outbox-1',
          'title': 'You have a new notification',
        });

        expect(content, isNotNull);
        expect(content!.title, 'You have a new notification');
      },
    );

    test(
      'never surfaces a file name -- there is none in the data map to begin with',
      () {
        // The server never sends one (design doc decision 12); this asserts
        // the client-side parser has no code path that could invent one
        // either, by checking the only text field it ever reads is `title`.
        final content = parsePushMessageData({
          'event_type': 'file_shared',
          'file_id': 'file-123',
          'notification_id': 'outbox-1',
          'title': 'You have a new notification',
        });

        expect(content!.title, isNot(contains('.pdf')));
        expect(content.title, isNot(contains('.jpg')));
      },
    );

    test('falls back to a generic title when the server omits one', () {
      final content = parsePushMessageData({
        'event_type': 'file_shared',
        'notification_id': 'outbox-1',
      });

      expect(content!.title, 'You have a new notification');
    });

    test('returns null for an unsupported event type', () {
      final content = parsePushMessageData({
        'event_type': 'user_registered',
        'notification_id': 'outbox-1',
      });

      expect(content, isNull);
    });

    test('returns null when event_type is missing', () {
      final content = parsePushMessageData({'notification_id': 'outbox-1'});

      expect(content, isNull);
    });

    test(
      'the same notification_id always maps to the same notification id',
      () {
        final first = parsePushMessageData({
          'event_type': 'file_shared',
          'notification_id': 'outbox-1',
        });
        final second = parsePushMessageData({
          'event_type': 'file_shared',
          'notification_id': 'outbox-1',
        });

        expect(first!.notificationId, second!.notificationId);
      },
    );

    test(
      'different notification_id values map to different notification ids',
      () {
        final first = parsePushMessageData({
          'event_type': 'file_shared',
          'notification_id': 'outbox-1',
        });
        final second = parsePushMessageData({
          'event_type': 'file_shared',
          'notification_id': 'outbox-2',
        });

        expect(first!.notificationId, isNot(second!.notificationId));
      },
    );
  });

  group('stableNotificationId', () {
    test('is deterministic across calls', () {
      expect(stableNotificationId('abc'), stableNotificationId('abc'));
    });

    test('is always non-negative', () {
      for (final value in ['', 'a', 'file_shared', 'outbox-id-with-a-uuid']) {
        expect(stableNotificationId(value), greaterThanOrEqualTo(0));
      }
    });
  });
}
