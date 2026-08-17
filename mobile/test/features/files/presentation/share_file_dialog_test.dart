import 'dart:convert';

import 'package:cloudestorage/app/app.dart';
import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/auth_fixtures.dart';
import '../../../support/fake_token_storage.dart';

const _rootFolderJson = {
  'id': 'root',
  'name': 'root',
  'path': 'root',
  'created_at': '2026-08-07T00:00:00Z',
  'contents': [
    {
      'id': 'file-1',
      'name': 'report.pdf',
      'type': 'file',
      'path': 'root.report.pdf',
      'size_bytes': 100,
    },
  ],
};

http.Response _emptySharesListResponse(http.Request request) =>
    http.Response(jsonEncode({'data': [], 'count': 0}), 200);

http.Response _noContentResponse(http.Request request) =>
    http.Response('', 204);

/// Pumps the app already signed in and navigated to the file detail screen
/// for `report.pdf`, with the dialog's three requests configurable:
/// `shareResponse` answers `POST /api/v1/files/file-1/shares` (creating a
/// share), `sharesListResponse` answers the `GET` on the same path (loading
/// the recipient list, fired from `initState`), and `revokeResponse` answers
/// `DELETE /api/v1/files/file-1/shares/{shareId}`.
Future<void> _pumpToShareDialog(
  WidgetTester tester, {
  http.Response Function(http.Request request)? shareResponse,
  http.Response Function(http.Request request)? sharesListResponse,
  http.Response Function(http.Request request)? revokeResponse,
}) async {
  final storage = FakeTokenStorage(token: 'saved-token');
  final client = MockClient((request) async {
    if (request.url.path == '/api/v1/login/test-token') {
      return http.Response(jsonEncode(userJson), 200);
    }
    if (request.url.path == '/api/v1/notifications/unread-count') {
      return http.Response(jsonEncode({'count': 0}), 200);
    }
    if (request.url.path == '/api/v1/files/file-1/shares') {
      return request.method == 'GET'
          ? (sharesListResponse ?? _emptySharesListResponse)(request)
          : shareResponse!(request);
    }
    if (request.url.path.startsWith('/api/v1/files/file-1/shares/')) {
      return (revokeResponse ?? _noContentResponse)(request);
    }
    return http.Response(jsonEncode(_rootFolderJson), 200);
  });

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
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

  await tester.longPress(find.text('report.pdf'));
  await tester.pumpAndSettle();

  await tester.tap(find.byKey(const Key('share-file-button')));
  await tester.pumpAndSettle();
}

Future<void> _fillAndSubmit(WidgetTester tester, String email) async {
  await tester.enterText(
    find.byKey(const Key('share-recipient-email-field')),
    email,
  );
  await tester.tap(find.byKey(const Key('share-submit-button')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('share button is not shown from Shared with me', (tester) async {
    final storage = FakeTokenStorage(token: 'saved-token');
    final client = MockClient((request) async {
      if (request.url.path == '/api/v1/login/test-token') {
        return http.Response(jsonEncode(userJson), 200);
      }
      if (request.url.path == '/api/v1/notifications/unread-count') {
        return http.Response(jsonEncode({'count': 0}), 200);
      }
      if (request.url.path == '/api/v1/files/shared-with-me') {
        return http.Response(
          jsonEncode({
            'data': [
              {
                'id': 'shared-file-1',
                'name': 'shared.pdf',
                'mime_type': 'application/pdf',
                'category': 'document',
                'size_bytes': 100,
                'owner_email': 'owner@example.com',
                'shared_at': '2026-08-07T00:00:00Z',
              },
            ],
            'count': 1,
          }),
          200,
        );
      }
      return http.Response(jsonEncode(_rootFolderJson), 200);
    });

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
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

    expect(find.text('shared.pdf'), findsOneWidget);
    expect(find.byKey(const Key('share-file-button')), findsNothing);
  });

  testWidgets('shows the current recipient list', (tester) async {
    await _pumpToShareDialog(
      tester,
      sharesListResponse: (request) => http.Response(
        jsonEncode({
          'data': [
            {
              'id': 'share-1',
              'file_id': 'file-1',
              'recipient_email': 'friend@example.com',
              'created_at': '2026-08-01T00:00:00Z',
            },
            {
              'id': 'share-2',
              'file_id': 'file-1',
              'recipient_email': 'other@example.com',
              'created_at': '2026-08-02T00:00:00Z',
            },
          ],
          'count': 2,
        }),
        200,
      ),
    );

    expect(find.text('friend@example.com'), findsOneWidget);
    expect(find.text('other@example.com'), findsOneWidget);
    expect(
      find.byKey(const Key('revoke-share-button-share-1')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('revoke-share-button-share-2')),
      findsOneWidget,
    );
  });

  testWidgets('shows the empty state when the file is not shared', (
    tester,
  ) async {
    await _pumpToShareDialog(tester);

    expect(
      find.text('This file is not shared with anyone yet.'),
      findsOneWidget,
    );
  });

  testWidgets('revoke success removes the recipient from the list', (
    tester,
  ) async {
    await _pumpToShareDialog(
      tester,
      sharesListResponse: (request) => http.Response(
        jsonEncode({
          'data': [
            {
              'id': 'share-1',
              'file_id': 'file-1',
              'recipient_email': 'friend@example.com',
              'created_at': '2026-08-01T00:00:00Z',
            },
          ],
          'count': 1,
        }),
        200,
      ),
    );
    expect(find.text('friend@example.com'), findsOneWidget);

    await tester.tap(find.byKey(const Key('revoke-share-button-share-1')));
    await tester.pumpAndSettle();

    expect(find.text('friend@example.com'), findsNothing);
    expect(
      find.text('This file is not shared with anyone yet.'),
      findsOneWidget,
    );
  });

  testWidgets('revoke failure leaves the recipient visible with an error', (
    tester,
  ) async {
    await _pumpToShareDialog(
      tester,
      sharesListResponse: (request) => http.Response(
        jsonEncode({
          'data': [
            {
              'id': 'share-1',
              'file_id': 'file-1',
              'recipient_email': 'friend@example.com',
              'created_at': '2026-08-01T00:00:00Z',
            },
          ],
          'count': 1,
        }),
        200,
      ),
      revokeResponse: (request) =>
          http.Response(jsonEncode({'detail': 'Server error'}), 500),
    );
    expect(find.text('friend@example.com'), findsOneWidget);

    await tester.tap(find.byKey(const Key('revoke-share-button-share-1')));
    await tester.pumpAndSettle();

    expect(find.text('friend@example.com'), findsOneWidget);
    expect(find.byKey(const Key('revoke-share-error-share-1')), findsOneWidget);
  });

  testWidgets('happy path shares the file and closes with confirmation', (
    tester,
  ) async {
    await _pumpToShareDialog(
      tester,
      shareResponse: (request) => http.Response(
        jsonEncode({
          'id': 'share-1',
          'file_id': 'file-1',
          'recipient_email': 'friend@example.com',
          'created_at': '2026-08-16T00:00:00Z',
        }),
        200,
      ),
    );

    expect(find.byType(AlertDialog), findsOneWidget);

    await _fillAndSubmit(tester, 'friend@example.com');

    expect(find.byType(AlertDialog), findsNothing);
    expect(find.text('File shared successfully'), findsOneWidget);
  });

  testWidgets('shows mapped error when recipient does not exist', (
    tester,
  ) async {
    await _pumpToShareDialog(
      tester,
      shareResponse: (request) =>
          http.Response(jsonEncode({'detail': 'Recipient not found'}), 404),
    );

    await _fillAndSubmit(tester, 'nobody@example.com');

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(
      find.text('No account exists for that email address.'),
      findsOneWidget,
    );
  });

  testWidgets('shows mapped error when the file is gone', (tester) async {
    await _pumpToShareDialog(
      tester,
      shareResponse: (request) =>
          http.Response(jsonEncode({'detail': 'File not found'}), 404),
    );

    await _fillAndSubmit(tester, 'friend@example.com');

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(
      find.text('File not found or you do not have permission'),
      findsOneWidget,
    );
  });

  testWidgets('shows mapped error when recipient is inactive', (tester) async {
    await _pumpToShareDialog(
      tester,
      shareResponse: (request) =>
          http.Response(jsonEncode({'detail': 'Recipient is inactive'}), 422),
    );

    await _fillAndSubmit(tester, 'inactive@example.com');

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(find.text('That user account is inactive.'), findsOneWidget);
  });

  testWidgets('shows mapped error when sharing with yourself', (tester) async {
    await _pumpToShareDialog(
      tester,
      shareResponse: (request) => http.Response(
        jsonEncode({'detail': 'A file cannot be shared with its owner'}),
        422,
      ),
    );

    await _fillAndSubmit(tester, 'user@example.com');

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(find.text('You cannot share a file with yourself.'), findsOneWidget);
  });

  testWidgets('shows mapped error when the file is already shared', (
    tester,
  ) async {
    await _pumpToShareDialog(
      tester,
      shareResponse: (request) =>
          http.Response(jsonEncode({'detail': 'Already shared'}), 409),
    );

    await _fillAndSubmit(tester, 'friend@example.com');

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(
      find.text('This file is already shared with that user.'),
      findsOneWidget,
    );
  });
}
