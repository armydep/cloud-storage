import 'dart:convert';

import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/notifications/application/notifications_controller.dart';
import 'package:cloudestorage/features/notifications/application/notifications_providers.dart';
import 'package:cloudestorage/features/notifications/presentation/notifications_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';

Map<String, dynamic> _notificationJson(String id) {
  return {
    'id': id,
    'event_type': 'file_shared',
    'payload': {
      'sharer_email': 'alice@example.com',
      'file_name': 'report-$id.pdf',
    },
    'created_at': '2026-08-10T12:00:00Z',
    'read_at': null,
  };
}

Future<ProviderContainer> _pumpNotificationsScreen(
  WidgetTester tester,
  http.Client httpClient,
) async {
  final container = ProviderContainer(
    overrides: [
      appConfigProvider.overrideWithValue(
        AppConfig.fromApiBaseUrl('https://example.com/'),
      ),
      tokenStorageProvider.overrideWithValue(
        FakeTokenStorage(token: 'test-token'),
      ),
      httpClientProvider.overrideWithValue(httpClient),
      // autoStart: false -- a real Timer.periodic would still be pending
      // when the test body returns, which flutter_test's binding treats as
      // a leaked timer.
      notificationsControllerProvider.overrideWith(
        (ref) => NotificationsController(
          ref.watch(notificationsRepositoryProvider),
          autoStart: false,
        ),
      ),
    ],
  );
  addTearDown(container.dispose);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: NotificationsScreen()),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

void main() {
  group('NotificationsScreen', () {
    testWidgets('lists notifications and enables Mark all read', (
      tester,
    ) async {
      final container = await _pumpNotificationsScreen(
        tester,
        MockClient((request) async {
          if (request.url.path == '/api/v1/notifications/unread-count') {
            return http.Response(jsonEncode({'count': 2}), 200);
          }
          return http.Response(
            jsonEncode({
              'data': [
                _notificationJson('notif-1'),
                _notificationJson('notif-2'),
              ],
              'next_cursor': null,
            }),
            200,
          );
        }),
      );

      expect(
        find.text('alice@example.com shared "report-notif-1.pdf" with you'),
        findsOneWidget,
      );
      expect(
        find.text('alice@example.com shared "report-notif-2.pdf" with you'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('mark-read-notif-1')), findsOneWidget);
      expect(find.byKey(const Key('mark-read-notif-2')), findsOneWidget);

      // hasUnread is driven by the polled unread-count, not the loaded
      // page(s) (mirrors the fix already applied to the web client) -- the
      // bell would normally have populated this before the user ever
      // navigates here, so simulate that poll explicitly.
      await container
          .read(notificationsControllerProvider.notifier)
          .refreshUnreadCount();
      await tester.pumpAndSettle();

      final markAllRead = tester.widget<TextButton>(
        find.byKey(const Key('mark-all-read-button')),
      );
      expect(markAllRead.onPressed, isNotNull);
    });

    testWidgets('shows an empty state with no notifications', (tester) async {
      await _pumpNotificationsScreen(
        tester,
        MockClient(
          (_) async =>
              http.Response(jsonEncode({'data': [], 'next_cursor': null}), 200),
        ),
      );

      expect(find.text('No notifications yet.'), findsOneWidget);
      final markAllRead = tester.widget<TextButton>(
        find.byKey(const Key('mark-all-read-button')),
      );
      expect(markAllRead.onPressed, isNull, reason: 'nothing unread to mark');
    });

    testWidgets('shows an error state with a retry button on failure', (
      tester,
    ) async {
      await _pumpNotificationsScreen(
        tester,
        MockClient((_) async => http.Response('{}', 500)),
      );

      expect(find.byKey(const Key('retry-button')), findsOneWidget);
      expect(find.text('No notifications yet.'), findsNothing);
    });

    testWidgets(
      'tapping Mark read for one notification leaves the sibling unread',
      (tester) async {
        var notif1Read = false;
        await _pumpNotificationsScreen(
          tester,
          MockClient((request) async {
            if (request.method == 'POST' &&
                request.url.path == '/api/v1/notifications/notif-1/read') {
              notif1Read = true;
              return http.Response(
                jsonEncode({
                  'id': 'notif-1',
                  'event_type': 'file_shared',
                  'payload': {
                    'sharer_email': 'alice@example.com',
                    'file_name': 'report-notif-1.pdf',
                  },
                  'created_at': '2026-08-10T12:00:00Z',
                  'read_at': '2026-08-10T12:05:00Z',
                }),
                200,
              );
            }
            if (request.url.path == '/api/v1/notifications/unread-count') {
              return http.Response(
                jsonEncode({'count': notif1Read ? 1 : 2}),
                200,
              );
            }
            return http.Response(
              jsonEncode({
                'data': [
                  {
                    'id': 'notif-1',
                    'event_type': 'file_shared',
                    'payload': {
                      'sharer_email': 'alice@example.com',
                      'file_name': 'report-notif-1.pdf',
                    },
                    'created_at': '2026-08-10T12:00:00Z',
                    'read_at': notif1Read ? '2026-08-10T12:05:00Z' : null,
                  },
                  _notificationJson('notif-2'),
                ],
                'next_cursor': null,
              }),
              200,
            );
          }),
        );

        await tester.tap(find.byKey(const Key('mark-read-notif-1')));
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('mark-read-notif-1')), findsNothing);
        expect(find.byKey(const Key('mark-read-notif-2')), findsOneWidget);
      },
    );
  });
}
