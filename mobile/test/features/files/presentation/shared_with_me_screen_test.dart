import 'dart:async';
import 'dart:convert';

import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/data/file_transfer_service.dart';
import 'package:cloudestorage/features/notifications/application/notifications_controller.dart';
import 'package:cloudestorage/features/notifications/application/notifications_providers.dart';
import 'package:cloudestorage/features/notifications/data/notifications_repository.dart';
import 'package:cloudestorage/features/files/presentation/shared_with_me_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';

Map<String, dynamic> _sharedFileJson() => {
  'id': 'file-1',
  'name': 'report.pdf',
  'mime_type': 'application/pdf',
  'category': 'document',
  'size_bytes': 2048,
  'owner_email': 'owner@example.com',
  'shared_at': '2026-08-06T12:00:00Z',
};

Future<void> _pumpScreen(
  WidgetTester tester,
  http.Client client, {
  double textScale = 1,
  bool settle = true,
  FileTransferService? fileTransferService,
}) async {
  final apiClient = ApiClient(Uri.parse('https://api.example.com/'));
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(
          AppConfig.fromApiBaseUrl('https://api.example.com/'),
        ),
        tokenStorageProvider.overrideWithValue(
          FakeTokenStorage(token: 'test-token'),
        ),
        httpClientProvider.overrideWithValue(client),
        if (fileTransferService != null)
          fileTransferServiceProvider.overrideWithValue(fileTransferService),
        notificationsControllerProvider.overrideWith(
          (ref) => NotificationsController(
            NotificationsRepository(apiClient),
            autoStart: false,
          ),
        ),
      ],
      child: MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: const SharedWithMeScreen(),
      ),
    ),
  );
  if (settle) await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows loading while the initial request is pending', (
    tester,
  ) async {
    final response = Completer<http.Response>();
    await _pumpScreen(
      tester,
      MockClient((_) => response.future),
      settle: false,
    );
    await tester.pump();

    expect(find.byKey(const Key('shared-files-loading')), findsOneWidget);

    response.complete(http.Response(jsonEncode({'data': [], 'count': 0}), 200));
    await tester.pumpAndSettle();
  });

  testWidgets('renders shared metadata without owner-only actions', (
    tester,
  ) async {
    await _pumpScreen(
      tester,
      MockClient(
        (_) async => http.Response(
          jsonEncode({
            'data': [_sharedFileJson()],
            'count': 1,
          }),
          200,
        ),
      ),
    );

    expect(find.text('report.pdf'), findsOneWidget);
    expect(find.text('owner@example.com'), findsOneWidget);
    expect(find.textContaining('application/pdf'), findsOneWidget);
    expect(find.textContaining('2.0 KB'), findsOneWidget);
    expect(
      find.byKey(const Key('download-shared-file-file-1')),
      findsOneWidget,
    );
    expect(find.byIcon(Icons.delete_outline), findsNothing);
  });

  testWidgets('shared metadata remains readable at large text scale', (
    tester,
  ) async {
    await _pumpScreen(
      tester,
      MockClient(
        (_) async => http.Response(
          jsonEncode({
            'data': [_sharedFileJson()],
            'count': 1,
          }),
          200,
        ),
      ),
      textScale: 2,
    );

    expect(find.text('report.pdf'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('failed refresh preserves the current shared files', (
    tester,
  ) async {
    var shouldFail = false;
    await _pumpScreen(
      tester,
      MockClient((_) async {
        if (shouldFail) return http.Response('{}', 500);
        return http.Response(
          jsonEncode({
            'data': [_sharedFileJson()],
            'count': 1,
          }),
          200,
        );
      }),
    );

    shouldFail = true;
    await tester.fling(find.byType(ListView), const Offset(0, 300), 1000);
    await tester.pumpAndSettle();

    expect(find.text('report.pdf'), findsOneWidget);
    expect(
      find.byKey(const Key('shared-files-refresh-retry-button')),
      findsOneWidget,
    );
  });

  testWidgets('successful refresh replaces the current shared files', (
    tester,
  ) async {
    var refreshed = false;
    await _pumpScreen(
      tester,
      MockClient((_) async {
        return http.Response(
          jsonEncode({
            'data': refreshed ? [] : [_sharedFileJson()],
            'count': refreshed ? 0 : 1,
          }),
          200,
        );
      }),
    );

    refreshed = true;
    await tester.fling(find.byType(ListView), const Offset(0, 300), 1000);
    await tester.pumpAndSettle();

    expect(find.text('report.pdf'), findsNothing);
    expect(find.text('No files shared with you'), findsOneWidget);
  });

  testWidgets('renders the empty state', (tester) async {
    await _pumpScreen(
      tester,
      MockClient(
        (_) async => http.Response(jsonEncode({'data': [], 'count': 0}), 200),
      ),
    );

    expect(find.text('No files shared with you'), findsOneWidget);
    expect(
      find.text('Files other users share with you will appear here.'),
      findsOneWidget,
    );
  });

  testWidgets('renders an error with retry', (tester) async {
    await _pumpScreen(
      tester,
      MockClient((_) async => http.Response('{}', 500)),
    );

    expect(find.byKey(const Key('shared-files-retry-button')), findsOneWidget);
    expect(find.text('Server error. Please try again.'), findsOneWidget);
  });

  testWidgets(
    'downloads and opens a shared file through injected transfer I/O',
    (tester) async {
      String? presignPath;
      final transferService = _FakeFileTransferService();
      await _pumpScreen(
        tester,
        MockClient((request) async {
          if (request.url.path == '/api/v1/files/shared-with-me') {
            return http.Response(
              jsonEncode({
                'data': [_sharedFileJson()],
                'count': 1,
              }),
              200,
            );
          }
          presignPath = request.url.path;
          return http.Response(
            jsonEncode({
              'download_url': 'https://objects.example.com/report.pdf',
              'expires_in': 900,
            }),
            200,
          );
        }),
        fileTransferService: transferService,
      );

      await tester.tap(find.byKey(const Key('download-shared-file-file-1')));
      await tester.pumpAndSettle();

      expect(presignPath, '/api/v1/files/file-1/presign-download');
      expect(
        transferService.downloadUrl,
        'https://objects.example.com/report.pdf',
      );
      expect(transferService.downloadFileName, 'report.pdf');
      expect(find.byKey(const Key('open-shared-file-file-1')), findsOneWidget);

      await tester.tap(find.byKey(const Key('open-shared-file-file-1')));
      await tester.pumpAndSettle();
      expect(transferService.openedPath, '/downloads/report.pdf');
    },
  );

  testWidgets('shows transfer progress while a download is pending', (
    tester,
  ) async {
    final transferService = _FakeFileTransferService(waitForCompletion: true);
    await _pumpScreen(
      tester,
      MockClient((request) async {
        if (request.url.path == '/api/v1/files/shared-with-me') {
          return http.Response(
            jsonEncode({
              'data': [_sharedFileJson()],
              'count': 1,
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'download_url': 'https://objects.example.com/report.pdf',
            'expires_in': 900,
          }),
          200,
        );
      }),
      fileTransferService: transferService,
    );

    await tester.tap(find.byKey(const Key('download-shared-file-file-1')));
    await tester.pump();
    await tester.pump();
    final progress = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator),
    );
    expect(progress.value, 0.5);

    transferService.completeDownload();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('open-shared-file-file-1')), findsOneWidget);
  });

  testWidgets('shows retry when shared access is no longer available', (
    tester,
  ) async {
    await _pumpScreen(
      tester,
      MockClient((request) async {
        if (request.url.path == '/api/v1/files/shared-with-me') {
          return http.Response(
            jsonEncode({
              'data': [_sharedFileJson()],
              'count': 1,
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
      fileTransferService: _FakeFileTransferService(),
    );

    await tester.tap(find.byKey(const Key('download-shared-file-file-1')));
    await tester.pumpAndSettle();

    expect(
      find.text('File not found or you do not have permission'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<IconButton>(
            find.byKey(const Key('download-shared-file-file-1')),
          )
          .tooltip,
      'Retry download report.pdf',
    );
  });
}

class _FakeFileTransferService extends FileTransferService {
  final bool waitForCompletion;
  final Completer<String> _downloadCompleter = Completer<String>();

  String? downloadUrl;
  String? downloadFileName;
  String? openedPath;

  _FakeFileTransferService({this.waitForCompletion = false});

  @override
  Future<String> download({
    required String url,
    required String fileName,
    required DownloadProgressCallback onProgress,
  }) async {
    downloadUrl = url;
    downloadFileName = fileName;
    onProgress(0.5);
    if (waitForCompletion) return _downloadCompleter.future;
    return '/downloads/$fileName';
  }

  void completeDownload() {
    _downloadCompleter.complete('/downloads/$downloadFileName');
  }

  @override
  Future<void> open(String filePath) async {
    openedPath = filePath;
  }
}
