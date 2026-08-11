import 'package:cloudestorage/features/notifications/domain/notification_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppNotification', () {
    test('parses an unread notification from JSON', () {
      final notification = AppNotification.fromJson({
        'id': 'notif-1',
        'event_type': 'file_shared',
        'payload': {
          'file_name': 'report.pdf',
          'sharer_email': 'alice@example.com',
        },
        'created_at': '2026-08-10T12:00:00Z',
        'read_at': null,
      });

      expect(notification.id, 'notif-1');
      expect(notification.eventType, 'file_shared');
      expect(notification.payload['file_name'], 'report.pdf');
      expect(notification.isUnread, isTrue);
      expect(notification.readAt, isNull);
    });

    test('parses a read notification from JSON', () {
      final notification = AppNotification.fromJson({
        'id': 'notif-2',
        'event_type': 'file_shared',
        'payload': <String, dynamic>{},
        'created_at': '2026-08-10T12:00:00Z',
        'read_at': '2026-08-10T12:05:00Z',
      });

      expect(notification.isUnread, isFalse);
      expect(notification.readAt, DateTime.parse('2026-08-10T12:05:00Z'));
    });

    test('markedRead returns a copy with readAt set, id unchanged', () {
      final notification = AppNotification.fromJson({
        'id': 'notif-3',
        'event_type': 'file_shared',
        'payload': <String, dynamic>{},
        'created_at': '2026-08-10T12:00:00Z',
        'read_at': null,
      });
      final at = DateTime.utc(2026, 8, 10, 12, 5);

      final read = notification.markedRead(at);

      expect(read.id, notification.id);
      expect(read.isUnread, isFalse);
      expect(read.readAt, at);
      expect(notification.isUnread, isTrue, reason: 'original is untouched');
    });
  });

  group('NotificationsPage', () {
    test('parses a page with a next cursor', () {
      final page = NotificationsPage.fromJson({
        'data': [
          {
            'id': 'notif-1',
            'event_type': 'file_shared',
            'payload': <String, dynamic>{},
            'created_at': '2026-08-10T12:00:00Z',
            'read_at': null,
          },
        ],
        'next_cursor': 'cursor-abc',
      });

      expect(page.data, hasLength(1));
      expect(page.nextCursor, 'cursor-abc');
    });

    test('parses the last page with a null cursor', () {
      final page = NotificationsPage.fromJson({
        'data': [],
        'next_cursor': null,
      });

      expect(page.data, isEmpty);
      expect(page.nextCursor, isNull);
    });
  });
}
