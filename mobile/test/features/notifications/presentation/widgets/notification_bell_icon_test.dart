import 'package:cloudestorage/features/notifications/presentation/widgets/notification_bell_icon.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('NotificationBellIcon', () {
    testWidgets('hides the badge when the unread count is zero', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationBellIcon(unreadCount: 0, onPressed: () {}),
          ),
        ),
      );

      expect(find.byKey(const Key('notifications-unread-badge')), findsNothing);
      expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);
    });

    testWidgets('shows the unread count in the badge', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationBellIcon(unreadCount: 3, onPressed: () {}),
          ),
        ),
      );

      expect(
        find.byKey(const Key('notifications-unread-badge')),
        findsOneWidget,
      );
      expect(find.text('3'), findsOneWidget);
    });

    testWidgets('caps a large unread count at 99+', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationBellIcon(unreadCount: 150, onPressed: () {}),
          ),
        ),
      );

      expect(find.text('99+'), findsOneWidget);
    });

    testWidgets('calls onPressed when tapped', (tester) async {
      var tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: NotificationBellIcon(
              unreadCount: 1,
              onPressed: () => tapped = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('notifications-button')));
      expect(tapped, isTrue);
    });
  });
}
