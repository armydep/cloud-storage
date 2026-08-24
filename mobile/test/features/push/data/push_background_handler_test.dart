import 'package:cloudestorage/features/push/data/push_background_handler.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/fake_local_notifications_client.dart';

void main() {
  group('handleBackgroundMessageData', () {
    test('shows a local notification for a file_shared message', () async {
      final client = FakeLocalNotificationsClient();

      await handleBackgroundMessageData({
        'event_type': 'file_shared',
        'file_id': 'file-123',
        'notification_id': 'outbox-1',
        'title': 'You have a new notification',
      }, client: client);

      expect(client.shown, hasLength(1));
      expect(client.shown.single.title, 'You have a new notification');
    });

    test('shows nothing for an unsupported event type', () async {
      final client = FakeLocalNotificationsClient();

      await handleBackgroundMessageData({
        'event_type': 'user_registered',
        'notification_id': 'outbox-1',
      }, client: client);

      expect(client.shown, isEmpty);
    });

    test('a failure showing the notification does not throw', () async {
      final client = FakeLocalNotificationsClient()
        ..nextError = Exception('boom');

      await expectLater(
        handleBackgroundMessageData({
          'event_type': 'file_shared',
          'notification_id': 'outbox-1',
        }, client: client),
        completes,
      );
    });

    test(
      'redelivering the same event shows the same notification id, replacing it',
      () async {
        final client = FakeLocalNotificationsClient();
        final data = {
          'event_type': 'file_shared',
          'notification_id': 'outbox-1',
        };

        await handleBackgroundMessageData(data, client: client);
        await handleBackgroundMessageData(data, client: client);

        expect(client.shown, hasLength(2));
        expect(client.shown[0].id, client.shown[1].id);
      },
    );
  });
}
