import 'package:cloudestorage/features/notifications/domain/notification_models.dart';
import 'package:cloudestorage/features/notifications/presentation/widgets/notification_list_tile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('NotificationListTile', () {
    testWidgets('renders file_shared text and a Mark read button when unread', (
      tester,
    ) async {
      final notification = AppNotification(
        id: 'notif-1',
        eventType: 'file_shared',
        payload: {
          'sharer_email': 'alice@example.com',
          'file_name': 'report.pdf',
        },
        createdAt: DateTime.utc(2026, 8, 10, 12),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationListTile(
              notification: notification,
              onMarkRead: () {},
            ),
          ),
        ),
      );

      expect(
        find.text('alice@example.com shared "report.pdf" with you'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('mark-read-notif-1')), findsOneWidget);
    });

    testWidgets('hides the Mark read button once read', (tester) async {
      final notification = AppNotification(
        id: 'notif-1',
        eventType: 'file_shared',
        payload: {
          'sharer_email': 'alice@example.com',
          'file_name': 'report.pdf',
        },
        createdAt: DateTime.utc(2026, 8, 10, 12),
        readAt: DateTime.utc(2026, 8, 10, 12, 5),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationListTile(
              notification: notification,
              onMarkRead: () {},
            ),
          ),
        ),
      );

      expect(find.byKey(const Key('mark-read-notif-1')), findsNothing);
    });

    testWidgets('calls onMarkRead when the button is tapped', (tester) async {
      var marked = false;
      final notification = AppNotification(
        id: 'notif-1',
        eventType: 'file_shared',
        payload: {
          'sharer_email': 'alice@example.com',
          'file_name': 'report.pdf',
        },
        createdAt: DateTime.utc(2026, 8, 10, 12),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationListTile(
              notification: notification,
              onMarkRead: () => marked = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('mark-read-notif-1')));
      expect(marked, isTrue);
    });
  });
}
