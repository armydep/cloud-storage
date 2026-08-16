import 'dart:convert';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';

void main() {
  group('FilesRepository.getSharedFiles', () {
    test(
      'uses the authenticated shared-with-me endpoint and parses data',
      () async {
        late http.Request captured;
        final client = MockClient((request) async {
          captured = request;
          return http.Response(
            jsonEncode({
              'data': [
                {
                  'id': 'file-1',
                  'name': 'report.pdf',
                  'mime_type': 'application/pdf',
                  'category': 'document',
                  'size_bytes': 2048,
                  'owner_email': 'owner@example.com',
                  'shared_at': '2026-08-06T12:00:00Z',
                },
              ],
              'count': 1,
            }),
            200,
          );
        });
        final session = AuthSession(FakeTokenStorage(token: 'token'));
        addTearDown(session.dispose);
        final repository = FilesRepository(
          ApiClient(
            Uri.parse('https://api.example.com/'),
            httpClient: client,
            authSession: session,
          ),
        );

        final files = await repository.getSharedFiles();

        expect(captured.method, 'GET');
        expect(captured.url.path, '/api/v1/files/shared-with-me');
        expect(captured.headers['Authorization'], 'Bearer token');
        expect(files.single.name, 'report.pdf');
        expect(files.single.ownerEmail, 'owner@example.com');
      },
    );

    test('returns an empty list for an empty response', () async {
      final session = AuthSession(FakeTokenStorage(token: 'token'));
      addTearDown(session.dispose);
      final repository = FilesRepository(
        ApiClient(
          Uri.parse('https://api.example.com/'),
          httpClient: MockClient(
            (_) async =>
                http.Response(jsonEncode({'data': [], 'count': 0}), 200),
          ),
          authSession: session,
        ),
      );

      expect(await repository.getSharedFiles(), isEmpty);
    });

    test('maps network and server failures', () async {
      final serverSession = AuthSession(FakeTokenStorage(token: 'token'));
      addTearDown(serverSession.dispose);
      final serverRepository = FilesRepository(
        ApiClient(
          Uri.parse('https://api.example.com/'),
          httpClient: MockClient((_) async => http.Response('{}', 500)),
          authSession: serverSession,
        ),
      );
      expect(serverRepository.getSharedFiles, throwsA(isA<ServerError>()));

      final networkSession = AuthSession(FakeTokenStorage(token: 'token'));
      addTearDown(networkSession.dispose);
      final networkRepository = FilesRepository(
        ApiClient(
          Uri.parse('https://api.example.com/'),
          httpClient: MockClient((_) async => throw Exception('offline')),
          authSession: networkSession,
        ),
      );
      expect(networkRepository.getSharedFiles, throwsA(isA<NetworkError>()));
    });
  });
}
