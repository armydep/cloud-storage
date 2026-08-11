import 'dart:io';
import 'dart:async';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../support/fake_token_storage.dart';

void main() {
  test('posts OAuth2 credentials as form data', () async {
    late http.Request capturedRequest;
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      httpClient: MockClient((request) async {
        capturedRequest = request;
        return http.Response('{"access_token":"token"}', 200);
      }),
    );

    await apiClient.postForm(
      '/api/v1/login/access-token',
      fields: const {'username': 'user@example.com', 'password': 'secret'},
    );

    expect(capturedRequest.method, 'POST');
    expect(
      capturedRequest.headers['content-type'],
      contains('form-urlencoded'),
    );
    expect(capturedRequest.bodyFields['username'], 'user@example.com');
    expect(capturedRequest.bodyFields['password'], 'secret');
  });

  test(
    'injects bearer token and clears it after an authenticated 403',
    () async {
      final storage = FakeTokenStorage(token: 'secret-token');
      final session = AuthSession(storage);
      late http.Request capturedRequest;
      final apiClient = ApiClient(
        Uri.parse('https://example.com/'),
        authSession: session,
        httpClient: MockClient((request) async {
          capturedRequest = request;
          return http.Response('{"detail":"invalid"}', 403);
        }),
      );

      await expectLater(
        apiClient.getJson('/api/v1/login/test-token', authenticated: true),
        throwsA(isA<ApiException>()),
      );

      expect(capturedRequest.headers['Authorization'], 'Bearer secret-token');
      expect(storage.token, isNull);
    },
  );

  test('maps transport failures to a safe network error', () async {
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      httpClient: MockClient(
        (_) async => throw const SocketException('private'),
      ),
    );

    await expectLater(
      apiClient.getJson('/health'),
      throwsA(
        isA<ApiException>()
            .having((error) => error.isNetworkError, 'isNetworkError', isTrue)
            .having(
              (error) => error.message,
              'message',
              isNot(contains('private')),
            ),
      ),
    );
  });

  test('sends authenticated DELETE requests without decoding a body', () async {
    final storage = FakeTokenStorage(token: 'secret-token');
    final session = AuthSession(storage);
    late http.Request capturedRequest;
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      authSession: session,
      httpClient: MockClient((request) async {
        capturedRequest = request;
        return http.Response('', 204);
      }),
    );

    await apiClient.delete('/api/v1/files/file-123', authenticated: true);

    expect(capturedRequest.method, 'DELETE');
    expect(capturedRequest.url.path, '/api/v1/files/file-123');
    expect(capturedRequest.headers['Authorization'], 'Bearer secret-token');
  });

  test('sends authenticated POST requests without decoding a body', () async {
    final storage = FakeTokenStorage(token: 'secret-token');
    final session = AuthSession(storage);
    late http.Request capturedRequest;
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      authSession: session,
      httpClient: MockClient((request) async {
        capturedRequest = request;
        return http.Response('', 204);
      }),
    );

    await apiClient.postEmpty(
      '/api/v1/notifications/read-all',
      authenticated: true,
    );

    expect(capturedRequest.method, 'POST');
    expect(capturedRequest.url.path, '/api/v1/notifications/read-all');
    expect(capturedRequest.headers['Authorization'], 'Bearer secret-token');
  });

  test('maps DELETE network failures to ApiException network errors', () async {
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      httpClient: MockClient(
        (_) async => throw const SocketException('private'),
      ),
    );

    await expectLater(
      apiClient.delete('/api/v1/files/file-123'),
      throwsA(
        isA<ApiException>().having(
          (error) => error.isNetworkError,
          'isNetworkError',
          isTrue,
        ),
      ),
    );
  });

  test('missing authenticated token remains an authentication error', () async {
    final session = AuthSession(FakeTokenStorage());
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      authSession: session,
      httpClient: MockClient((_) async => http.Response('{}', 200)),
    );

    await expectLater(
      apiClient.postJson('/api/v1/login/test-token', authenticated: true),
      throwsA(
        isA<ApiException>()
            .having((error) => error.statusCode, 'statusCode', 401)
            .having((error) => error.isNetworkError, 'isNetworkError', isFalse),
      ),
    );
  });

  test('stale unauthorized response does not clear a newer token', () async {
    final storage = FakeTokenStorage(token: 'old-token');
    final session = AuthSession(storage);
    final requestStarted = Completer<void>();
    final finishRequest = Completer<http.Response>();
    final apiClient = ApiClient(
      Uri.parse('https://example.com/'),
      authSession: session,
      httpClient: MockClient((request) {
        expect(request.headers['Authorization'], 'Bearer old-token');
        requestStarted.complete();
        return finishRequest.future;
      }),
    );

    final staleRequest = apiClient.postJson(
      '/api/v1/login/test-token',
      authenticated: true,
    );
    await requestStarted.future;
    await session.saveToken('new-token');
    finishRequest.complete(http.Response('{}', 403));

    await expectLater(staleRequest, throwsA(isA<ApiException>()));
    expect(storage.token, 'new-token');
  });
}
