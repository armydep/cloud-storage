import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/data/auth_repository.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';

void main() {
  group('AuthRepository.logout', () {
    test('runs onBeforeLogout before the session is cleared', () async {
      // Unregistering on logout is a security requirement, not hygiene
      // (design doc decision 6): it needs a still-valid token to
      // authenticate, so it must run before the token is cleared.
      final storage = FakeTokenStorage(token: 'stored-token');
      final session = AuthSession(storage);
      final apiClient = ApiClient(
        Uri.parse('https://example.com/'),
        httpClient: MockClient((_) async => http.Response('{}', 200)),
        authSession: session,
      );
      String? tokenAtHookTime;
      final repository = AuthRepository(
        apiClient,
        session,
        onBeforeLogout: () async {
          tokenAtHookTime = await session.readToken();
        },
      );

      await repository.logout();

      expect(tokenAtHookTime, 'stored-token');
      expect(await session.readToken(), isNull);
    });

    test('clears the session even when onBeforeLogout fails', () async {
      final storage = FakeTokenStorage(token: 'stored-token');
      final session = AuthSession(storage);
      final apiClient = ApiClient(
        Uri.parse('https://example.com/'),
        httpClient: MockClient((_) async => http.Response('{}', 200)),
        authSession: session,
      );
      final repository = AuthRepository(
        apiClient,
        session,
        onBeforeLogout: () async {
          throw Exception('unregister failed');
        },
      );

      await repository.logout();

      expect(await session.readToken(), isNull);
    });

    test('clears the session when no onBeforeLogout is given', () async {
      final storage = FakeTokenStorage(token: 'stored-token');
      final session = AuthSession(storage);
      final apiClient = ApiClient(
        Uri.parse('https://example.com/'),
        httpClient: MockClient((_) async => http.Response('{}', 200)),
        authSession: session,
      );
      final repository = AuthRepository(apiClient, session);

      await repository.logout();

      expect(await session.readToken(), isNull);
    });
  });
}
