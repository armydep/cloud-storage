import 'dart:async';
import 'dart:convert';

import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/presentation/files_browser_screen.dart';
import 'package:cloudestorage/features/notifications/application/notifications_controller.dart';
import 'package:cloudestorage/features/notifications/application/notifications_providers.dart';
import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_fcm_client.dart';
import '../../../support/fake_token_storage.dart';

void main() {
  group('Mobile file delete', () {
    testWidgets('shows delete for files and folders and file cancel works', (
      tester,
    ) async {
      var deleteCount = 0;
      final httpClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/api/v1/files') {
          return http.Response(jsonEncode(_folderJson()), 200);
        }
        if (request.method == 'DELETE') {
          deleteCount += 1;
          return http.Response('', 204);
        }
        return http.Response('{}', 404);
      });

      await _pumpFilesScreen(tester, httpClient);

      expect(find.byKey(const Key('delete-file-file-123')), findsOneWidget);
      expect(find.byKey(const Key('delete-folder-folder-123')), findsOneWidget);

      await tester.tap(find.byKey(const Key('delete-file-file-123')));
      await tester.pumpAndSettle();

      expect(find.text('Delete file'), findsOneWidget);
      expect(
        find.textContaining('document.pdf will be permanently deleted'),
        findsOneWidget,
      );

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Delete file'), findsNothing);
      expect(deleteCount, 0);
      expect(find.text('document.pdf'), findsOneWidget);
    });

    testWidgets('confirming delete calls endpoint and refreshes the folder', (
      tester,
    ) async {
      var deleted = false;
      String? deletePath;
      final httpClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/api/v1/files') {
          return http.Response(
            jsonEncode(_folderJson(includeFile: !deleted)),
            200,
          );
        }
        if (request.method == 'DELETE') {
          deletePath = request.url.path;
          deleted = true;
          return http.Response('', 204);
        }
        return http.Response('{}', 404);
      });

      await _pumpFilesScreen(tester, httpClient);

      await tester.tap(find.byKey(const Key('delete-file-file-123')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(deletePath, '/api/v1/files/file-123');
      expect(find.text('File deleted successfully'), findsOneWidget);
      expect(find.text('document.pdf'), findsNothing);
    });

    testWidgets('failed delete keeps the file visible and shows error', (
      tester,
    ) async {
      final httpClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/api/v1/files') {
          return http.Response(jsonEncode(_folderJson()), 200);
        }
        if (request.method == 'DELETE') {
          return http.Response('{"detail":"failed"}', 500);
        }
        return http.Response('{}', 404);
      });

      await _pumpFilesScreen(tester, httpClient);

      await tester.tap(find.byKey(const Key('delete-file-file-123')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(
        find.text('File delete failed. Please try again later.'),
        findsOneWidget,
      );
      expect(find.text('document.pdf'), findsOneWidget);
    });

    testWidgets('delete pending state survives the post-delete refresh', (
      tester,
    ) async {
      var getCount = 0;
      final refreshStarted = Completer<void>();
      final refreshResponse = Completer<http.Response>();
      final httpClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/api/v1/files') {
          getCount += 1;
          if (getCount == 1) {
            return http.Response(jsonEncode(_folderJson()), 200);
          }
          refreshStarted.complete();
          return refreshResponse.future;
        }
        if (request.method == 'DELETE') {
          return http.Response('', 204);
        }
        return http.Response('{}', 404);
      });

      final container = await _pumpFilesScreen(tester, httpClient);

      await tester.tap(find.byKey(const Key('delete-file-file-123')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await refreshStarted.future;
      await tester.pump();

      expect(
        container.read(filesControllerProvider).isDeleting('file-123'),
        isTrue,
      );
      expect(find.byKey(const Key('delete-file-file-123')), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      refreshResponse.complete(http.Response('{"detail":"failed"}', 500));
      await tester.pumpAndSettle();

      expect(
        container.read(filesControllerProvider).isDeleting('file-123'),
        isFalse,
      );
      expect(find.text('document.pdf'), findsOneWidget);
    });

    testWidgets('canceling folder delete does not call delete', (tester) async {
      var deleteCount = 0;
      final httpClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/api/v1/files') {
          return http.Response(jsonEncode(_folderJson()), 200);
        }
        if (request.method == 'DELETE') {
          deleteCount += 1;
          return http.Response('', 204);
        }
        return http.Response('{}', 404);
      });

      await _pumpFilesScreen(tester, httpClient);

      await tester.tap(find.byKey(const Key('delete-folder-folder-123')));
      await tester.pumpAndSettle();

      expect(find.text('Delete folder'), findsOneWidget);
      expect(
        find.textContaining(
          'Documents and all files and folders inside it will be permanently deleted',
        ),
        findsOneWidget,
      );

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Delete folder'), findsNothing);
      expect(deleteCount, 0);
      expect(find.text('Documents'), findsOneWidget);
    });

    testWidgets(
      'confirming folder delete calls endpoint and refreshes folder',
      (tester) async {
        var deleted = false;
        String? deletePath;
        final httpClient = MockClient((request) async {
          if (request.method == 'GET' && request.url.path == '/api/v1/files') {
            return http.Response(
              jsonEncode(_folderJson(includeFolder: !deleted)),
              200,
            );
          }
          if (request.method == 'DELETE') {
            deletePath = request.url.path;
            deleted = true;
            return http.Response('', 204);
          }
          return http.Response('{}', 404);
        });

        await _pumpFilesScreen(tester, httpClient);

        await tester.tap(find.byKey(const Key('delete-folder-folder-123')));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Delete'));
        await tester.pumpAndSettle();

        expect(deletePath, '/api/v1/files/folders/folder-123');
        expect(find.text('Folder deleted successfully'), findsOneWidget);
        expect(find.text('Documents'), findsNothing);
      },
    );

    testWidgets(
      'failed folder delete keeps the folder visible and shows error',
      (tester) async {
        final httpClient = MockClient((request) async {
          if (request.method == 'GET' && request.url.path == '/api/v1/files') {
            return http.Response(jsonEncode(_folderJson()), 200);
          }
          if (request.method == 'DELETE') {
            return http.Response('{"detail":"failed"}', 500);
          }
          return http.Response('{}', 404);
        });

        await _pumpFilesScreen(tester, httpClient);

        await tester.tap(find.byKey(const Key('delete-folder-folder-123')));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Delete'));
        await tester.pumpAndSettle();

        expect(
          find.text('Folder delete failed. Please try again later.'),
          findsOneWidget,
        );
        expect(find.text('Documents'), findsOneWidget);
      },
    );

    testWidgets('folder delete pending state survives post-delete refresh', (
      tester,
    ) async {
      var getCount = 0;
      final refreshStarted = Completer<void>();
      final refreshResponse = Completer<http.Response>();
      final httpClient = MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/api/v1/files') {
          getCount += 1;
          if (getCount == 1) {
            return http.Response(jsonEncode(_folderJson()), 200);
          }
          refreshStarted.complete();
          return refreshResponse.future;
        }
        if (request.method == 'DELETE') {
          return http.Response('', 204);
        }
        return http.Response('{}', 404);
      });

      final container = await _pumpFilesScreen(tester, httpClient);

      await tester.tap(find.byKey(const Key('delete-folder-folder-123')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await refreshStarted.future;
      await tester.pump();

      expect(
        container.read(filesControllerProvider).isDeleting('folder-123'),
        isTrue,
      );
      expect(find.byKey(const Key('delete-folder-folder-123')), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      refreshResponse.complete(http.Response('{"detail":"failed"}', 500));
      await tester.pumpAndSettle();

      expect(
        container.read(filesControllerProvider).isDeleting('folder-123'),
        isFalse,
      );
      expect(find.text('Documents'), findsOneWidget);
    });
  });
}

Future<ProviderContainer> _pumpFilesScreen(
  WidgetTester tester,
  http.Client httpClient,
) async {
  final container = ProviderContainer(
    overrides: [
      fcmClientProvider.overrideWithValue(const NoOpFcmClient()),
      appConfigProvider.overrideWithValue(
        AppConfig.fromApiBaseUrl('https://example.com/'),
      ),
      tokenStorageProvider.overrideWithValue(
        FakeTokenStorage(token: 'test-token'),
      ),
      httpClientProvider.overrideWithValue(httpClient),
      // This suite pumps the real FilesBrowserScreen, which now hosts the
      // notification bell. Without autoStart: false, its real
      // Timer.periodic would still be pending when the test body returns,
      // which flutter_test's binding treats as a leaked timer -- container
      // teardown (below) runs too late to prevent that check from failing.
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
      child: const MaterialApp(home: FilesBrowserScreen()),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

Map<String, dynamic> _folderJson({
  bool includeFolder = true,
  bool includeFile = true,
}) {
  return {
    'id': 'root-folder',
    'name': 'root',
    'path': 'root',
    'created_at': '2026-08-09T00:00:00Z',
    'contents': [
      if (includeFolder)
        {
          'id': 'folder-123',
          'name': 'Documents',
          'type': 'folder',
          'path': 'root.Documents',
        },
      if (includeFile)
        {
          'id': 'file-123',
          'name': 'document.pdf',
          'type': 'file',
          'size_bytes': 1024,
          'category': 'document',
          'mime_type': 'application/pdf',
        },
    ],
  };
}
