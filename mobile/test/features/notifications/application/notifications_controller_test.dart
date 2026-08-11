import 'dart:convert';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/notifications/application/notifications_controller.dart';
import 'package:cloudestorage/features/notifications/data/notifications_repository.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';

NotificationsController buildController(
  MockClient httpClient, {
  bool autoStart = false,
}) {
  final session = AuthSession(FakeTokenStorage(token: 'test-token'));
  final apiClient = ApiClient(
    Uri.parse('https://example.com/'),
    httpClient: httpClient,
    authSession: session,
  );
  return NotificationsController(
    NotificationsRepository(apiClient),
    autoStart: autoStart,
  );
}

Map<String, dynamic> _notificationJson({
  required String id,
  bool unread = true,
}) {
  return {
    'id': id,
    'event_type': 'file_shared',
    'payload': {
      'sharer_email': 'alice@example.com',
      'file_name': 'report-$id.pdf',
    },
    'created_at': '2026-08-10T12:00:00Z',
    'read_at': unread ? null : '2026-08-10T12:05:00Z',
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('loadFirstPage', () {
    test('populates notifications without marking anything read', () async {
      final requestedPaths = <String>[];
      final controller = buildController(
        MockClient((request) async {
          requestedPaths.add(request.url.path);
          return http.Response(
            jsonEncode({
              'data': [
                _notificationJson(id: 'notif-1'),
                _notificationJson(id: 'notif-2'),
              ],
              'next_cursor': null,
            }),
            200,
          );
        }),
      );
      addTearDown(controller.dispose);

      await controller.loadFirstPage();

      expect(controller.state.notifications, hasLength(2));
      expect(controller.state.notifications.every((n) => n.isUnread), isTrue);
      expect(controller.state.isLoading, isFalse);
      expect(controller.state.error, isNull);
      // Only GET /api/v1/notifications -- opening the feed must never call
      // the read/read-all endpoints (phase-9-in-app-notifications.md
      // decision 11).
      expect(requestedPaths, everyElement('/api/v1/notifications'));
    });

    test('surfaces an error and keeps the list empty on failure', () async {
      final controller = buildController(
        MockClient((_) async => http.Response('{}', 500)),
      );
      addTearDown(controller.dispose);

      await controller.loadFirstPage();

      expect(controller.state.notifications, isEmpty);
      expect(controller.state.error, isNotNull);
      expect(controller.state.isLoading, isFalse);
    });
  });

  group('loadMore', () {
    test(
      'appends the next page by cursor without duplicating entries',
      () async {
        final controller = buildController(
          MockClient((request) async {
            final cursor = request.url.queryParameters['cursor'];
            if (cursor == null) {
              return http.Response(
                jsonEncode({
                  'data': [
                    _notificationJson(id: 'notif-1'),
                    _notificationJson(id: 'notif-2'),
                  ],
                  'next_cursor': 'page-2',
                }),
                200,
              );
            }
            expect(cursor, 'page-2');
            return http.Response(
              jsonEncode({
                'data': [_notificationJson(id: 'notif-3')],
                'next_cursor': null,
              }),
              200,
            );
          }),
        );
        addTearDown(controller.dispose);

        await controller.loadFirstPage();
        expect(controller.state.hasMore, isTrue);

        await controller.loadMore();

        expect(controller.state.notifications.map((n) => n.id).toList(), [
          'notif-1',
          'notif-2',
          'notif-3',
        ]);
        expect(controller.state.hasMore, isFalse);
      },
    );

    test('does nothing when there is no next page', () async {
      var requestCount = 0;
      final controller = buildController(
        MockClient((_) async {
          requestCount++;
          return http.Response(
            jsonEncode({
              'data': [_notificationJson(id: 'notif-1')],
              'next_cursor': null,
            }),
            200,
          );
        }),
      );
      addTearDown(controller.dispose);

      await controller.loadFirstPage();
      expect(requestCount, 1);

      await controller.loadMore();

      expect(requestCount, 1, reason: 'hasMore is false, no request made');
    });
  });

  group('markRead', () {
    test(
      'marks only the target notification and refreshes the unread count',
      () async {
        var unreadCountRequests = 0;
        final controller = buildController(
          MockClient((request) async {
            if (request.method == 'GET' &&
                request.url.path == '/api/v1/notifications/unread-count') {
              unreadCountRequests++;
              return http.Response(jsonEncode({'count': 1}), 200);
            }
            if (request.method == 'POST' &&
                request.url.path == '/api/v1/notifications/notif-1/read') {
              return http.Response(
                jsonEncode(_notificationJson(id: 'notif-1', unread: false)),
                200,
              );
            }
            return http.Response(
              jsonEncode({
                'data': [
                  _notificationJson(id: 'notif-1'),
                  _notificationJson(id: 'notif-2'),
                ],
                'next_cursor': null,
              }),
              200,
            );
          }),
        );
        addTearDown(controller.dispose);
        await controller.loadFirstPage();

        await controller.markRead('notif-1');

        final byId = {for (final n in controller.state.notifications) n.id: n};
        expect(byId['notif-1']!.isUnread, isFalse);
        expect(byId['notif-2']!.isUnread, isTrue, reason: 'sibling untouched');
        expect(controller.state.unreadCount, 1);
        expect(unreadCountRequests, 1);
      },
    );

    test('surfaces an error without touching existing notifications', () async {
      final controller = buildController(
        MockClient((request) async {
          if (request.method == 'POST') {
            return http.Response('{"detail":"not found"}', 404);
          }
          return http.Response(
            jsonEncode({
              'data': [_notificationJson(id: 'notif-1')],
              'next_cursor': null,
            }),
            200,
          );
        }),
      );
      addTearDown(controller.dispose);
      await controller.loadFirstPage();

      await controller.markRead('notif-1');

      expect(controller.state.error, isNotNull);
      expect(controller.state.notifications.single.isUnread, isTrue);
    });
  });

  group('markAllRead', () {
    test('marks every loaded notification read and zeroes the badge', () async {
      final controller = buildController(
        MockClient((request) async {
          if (request.method == 'POST') {
            return http.Response('', 204);
          }
          return http.Response(
            jsonEncode({
              'data': [
                _notificationJson(id: 'notif-1'),
                _notificationJson(id: 'notif-2'),
              ],
              'next_cursor': null,
            }),
            200,
          );
        }),
      );
      addTearDown(controller.dispose);
      await controller.loadFirstPage();

      await controller.markAllRead();

      expect(
        controller.state.notifications.every((n) => n.isUnread == false),
        isTrue,
      );
      expect(controller.state.unreadCount, 0);
    });
  });

  group('polling and app lifecycle', () {
    test('polls only when autoStart is true', () async {
      final autoStarted = buildController(
        MockClient((_) async => http.Response(jsonEncode({'count': 0}), 200)),
        autoStart: true,
      );
      addTearDown(autoStarted.dispose);
      expect(autoStarted.isPolling, isTrue);

      final manual = buildController(
        MockClient((_) async => http.Response(jsonEncode({'count': 0}), 200)),
      );
      addTearDown(manual.dispose);
      expect(manual.isPolling, isFalse);
    });

    test(
      'stops polling when backgrounded and resumes in the foreground',
      () async {
        final controller = buildController(
          MockClient((_) async => http.Response(jsonEncode({'count': 0}), 200)),
          autoStart: true,
        );
        expect(controller.isPolling, isTrue);

        controller.didChangeAppLifecycleState(AppLifecycleState.paused);
        expect(controller.isPolling, isFalse);

        controller.didChangeAppLifecycleState(AppLifecycleState.inactive);
        expect(controller.isPolling, isFalse);

        controller.didChangeAppLifecycleState(AppLifecycleState.resumed);
        expect(controller.isPolling, isTrue);

        controller.dispose();
        expect(controller.isPolling, isFalse);
      },
    );
  });
}
