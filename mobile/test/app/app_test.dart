import 'dart:convert';

import 'package:cloudestorage/app/app.dart';
import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../support/auth_fixtures.dart';
import '../support/fake_fcm_client.dart';
import '../support/fake_token_storage.dart';

void main() {
  testWidgets('shows login and validates required credentials', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          fcmClientProvider.overrideWithValue(const NoOpFcmClient()),
          appConfigProvider.overrideWithValue(
            AppConfig.fromApiBaseUrl('https://api.example.com'),
          ),
          tokenStorageProvider.overrideWithValue(FakeTokenStorage()),
          httpClientProvider.overrideWithValue(
            MockClient((_) async => http.Response('{}', 500)),
          ),
        ],
        child: const CloudStorageApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sign in to Cloude Storage'), findsOneWidget);
    await tester.tap(find.byKey(const Key('login-button')));
    await tester.pump();

    expect(find.text('Enter a valid email address.'), findsOneWidget);
    expect(find.text('Enter your password.'), findsOneWidget);
  });

  testWidgets('logs in, shows file browser, and logs out', (tester) async {
    final storage = FakeTokenStorage();
    var call = 0;
    final client = MockClient((request) async {
      call++;
      if (call == 1) {
        // Login call
        return http.Response('{"access_token":"new-token"}', 200);
      } else if (call == 2) {
        // Session restore call
        return http.Response(jsonEncode(userJson), 200);
      } else {
        // File browser - load root folder
        return http.Response(
          jsonEncode({
            'id': '123',
            'name': 'root',
            'path': 'root',
            'created_at': '2026-08-07T00:00:00Z',
            'contents': [],
          }),
          200,
        );
      }
    });
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          fcmClientProvider.overrideWithValue(const NoOpFcmClient()),
          appConfigProvider.overrideWithValue(
            AppConfig.fromApiBaseUrl('https://api.example.com'),
          ),
          tokenStorageProvider.overrideWithValue(storage),
          httpClientProvider.overrideWithValue(client),
        ],
        child: const CloudStorageApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('email-field')),
      'user@example.com',
    );
    await tester.enterText(find.byKey(const Key('password-field')), 'password');
    await tester.tap(find.byKey(const Key('login-button')));
    await tester.pumpAndSettle();

    // File browser should display with root folder
    expect(find.text('root'), findsOneWidget);
    expect(find.text('This folder is empty'), findsOneWidget);
    expect(storage.token, 'new-token');

    await tester.tap(find.byKey(const Key('logout-button')));
    await tester.pumpAndSettle();

    expect(find.text('Sign in to Cloude Storage'), findsOneWidget);
    expect(storage.token, isNull);
  });

  testWidgets('authenticated users can navigate to Shared with me', (
    tester,
  ) async {
    final storage = FakeTokenStorage(token: 'saved-token');
    final client = MockClient((request) async {
      if (request.url.path == '/api/v1/login/test-token') {
        return http.Response(jsonEncode(userJson), 200);
      }
      if (request.url.path == '/api/v1/files/shared-with-me') {
        return http.Response(jsonEncode({'data': [], 'count': 0}), 200);
      }
      if (request.url.path == '/api/v1/notifications/unread-count') {
        return http.Response(jsonEncode({'count': 0}), 200);
      }
      return http.Response(
        jsonEncode({
          'id': '123',
          'name': 'root',
          'path': 'root',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [],
        }),
        200,
      );
    });

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          fcmClientProvider.overrideWithValue(const NoOpFcmClient()),
          appConfigProvider.overrideWithValue(
            AppConfig.fromApiBaseUrl('https://api.example.com'),
          ),
          tokenStorageProvider.overrideWithValue(storage),
          httpClientProvider.overrideWithValue(client),
        ],
        child: const CloudStorageApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('shared-navigation-destination')));
    await tester.pumpAndSettle();

    expect(find.text('Shared with me'), findsWidgets);
    expect(find.text('No files shared with you'), findsOneWidget);
    expect(storage.token, 'saved-token');
  });

  testWidgets('tab switching preserves nested folder navigation', (
    tester,
  ) async {
    final storage = FakeTokenStorage(token: 'saved-token');
    final client = MockClient((request) async {
      if (request.url.path == '/api/v1/login/test-token') {
        return http.Response(jsonEncode(userJson), 200);
      }
      if (request.url.path == '/api/v1/files/shared-with-me') {
        return http.Response(jsonEncode({'data': [], 'count': 0}), 200);
      }
      if (request.url.path == '/api/v1/notifications/unread-count') {
        return http.Response(jsonEncode({'count': 0}), 200);
      }
      if (request.url.queryParameters['path'] == 'root.Documents') {
        return http.Response(
          jsonEncode({
            'id': 'documents',
            'name': 'Documents',
            'path': 'root.Documents',
            'created_at': '2026-08-07T00:00:00Z',
            'contents': [],
          }),
          200,
        );
      }
      return http.Response(
        jsonEncode({
          'id': 'root',
          'name': 'root',
          'path': 'root',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [
            {
              'id': 'documents',
              'name': 'Documents',
              'type': 'folder',
              'path': 'root.Documents',
            },
          ],
        }),
        200,
      );
    });

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          fcmClientProvider.overrideWithValue(const NoOpFcmClient()),
          appConfigProvider.overrideWithValue(
            AppConfig.fromApiBaseUrl('https://api.example.com'),
          ),
          tokenStorageProvider.overrideWithValue(storage),
          httpClientProvider.overrideWithValue(client),
        ],
        child: const CloudStorageApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Documents'));
    await tester.pumpAndSettle();
    expect(find.text('This folder is empty'), findsOneWidget);

    await tester.tap(find.byKey(const Key('shared-navigation-destination')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('files-navigation-destination')));
    await tester.pumpAndSettle();

    expect(find.text('Documents'), findsOneWidget);
    expect(find.text('This folder is empty'), findsOneWidget);

    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('root'), findsOneWidget);
    expect(find.text('Documents'), findsOneWidget);
  });
}
