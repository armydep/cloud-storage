import 'dart:async';
import 'dart:convert';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/application/auth_controller.dart';
import 'package:cloudestorage/features/auth/application/auth_state.dart';
import 'package:cloudestorage/features/auth/data/auth_repository.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';
import '../../../support/auth_fixtures.dart';

AuthController buildController(
  FakeTokenStorage storage,
  MockClient httpClient,
) {
  final session = AuthSession(storage);
  final apiClient = ApiClient(
    Uri.parse('https://example.com/'),
    httpClient: httpClient,
    authSession: session,
  );
  return AuthController(
    AuthRepository(apiClient, session),
    session,
    restoreOnCreate: false,
  );
}

void main() {
  test('restores a valid stored session', () async {
    final controller = buildController(
      FakeTokenStorage(token: 'stored-token'),
      MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.headers['Authorization'], 'Bearer stored-token');
        return http.Response(jsonEncode(userJson), 200);
      }),
    );

    await controller.restoreSession();

    expect(controller.state.status, AuthStatus.authenticated);
    expect(controller.state.user?.email, 'user@example.com');
    controller.dispose();
  });

  test('removes an invalid stored session', () async {
    final storage = FakeTokenStorage(token: 'expired-token');
    final controller = buildController(
      storage,
      MockClient((_) async => http.Response('{}', 403)),
    );

    await controller.restoreSession();

    expect(controller.state.status, AuthStatus.unauthenticated);
    expect(storage.token, isNull);
    controller.dispose();
  });

  test('retains token and exposes retry after a server failure', () async {
    final storage = FakeTokenStorage(token: 'stored-token');
    final controller = buildController(
      storage,
      MockClient((_) async => http.Response('{}', 503)),
    );

    await controller.restoreSession();

    expect(controller.state.status, AuthStatus.restoreFailure);
    expect(storage.token, 'stored-token');
    controller.dispose();
  });

  test('login trims email, stores token, and validates user', () async {
    final storage = FakeTokenStorage();
    var call = 0;
    final controller = buildController(
      storage,
      MockClient((request) async {
        call++;
        if (call == 1) {
          expect(request.bodyFields['username'], 'user@example.com');
          return http.Response('{"access_token":"new-token"}', 200);
        }
        expect(request.method, 'POST');
        expect(request.headers['Authorization'], 'Bearer new-token');
        return http.Response(jsonEncode(userJson), 200);
      }),
    );

    await controller.login(email: ' user@example.com ', password: 'password');

    expect(controller.state.status, AuthStatus.authenticated);
    expect(storage.token, 'new-token');
    controller.dispose();
  });

  test('rejected login remains unauthenticated with a safe error', () async {
    final storage = FakeTokenStorage();
    final controller = buildController(
      storage,
      MockClient((_) async => http.Response('{"detail":"private"}', 400)),
    );

    await controller.login(email: 'user@example.com', password: 'wrong');

    expect(controller.state.status, AuthStatus.unauthenticated);
    expect(controller.state.errorMessage, 'Incorrect email or password.');
    expect(controller.state.errorMessage, isNot(contains('private')));
    expect(storage.token, isNull);
    controller.dispose();
  });

  test(
    'secure-storage read failure exposes a retryable restore error',
    () async {
      final storage = FakeTokenStorage()..readError = StateError('private');
      final controller = buildController(
        storage,
        MockClient((_) async => http.Response('{}', 500)),
      );

      await controller.restoreSession();

      expect(controller.state.status, AuthStatus.restoreFailure);
      expect(controller.state.errorMessage, contains('Secure session storage'));
      expect(controller.state.errorMessage, isNot(contains('private')));
      controller.dispose();
    },
  );

  test('malformed user validation clears a newly issued token', () async {
    final storage = FakeTokenStorage();
    var call = 0;
    final controller = buildController(
      storage,
      MockClient((_) async {
        call++;
        return call == 1
            ? http.Response('{"access_token":"new-token"}', 200)
            : http.Response('{"unexpected":true}', 200);
      }),
    );

    await controller.login(email: 'user@example.com', password: 'password');

    expect(controller.state.status, AuthStatus.unauthenticated);
    expect(storage.token, isNull);
    controller.dispose();
  });

  test(
    'overlapping logins are serialized and each validates its own token',
    () async {
      final storage = FakeTokenStorage();
      final firstLoginResponse = Completer<http.Response>();
      var call = 0;
      final controller = buildController(
        storage,
        MockClient((request) {
          call++;
          return switch (call) {
            1 => firstLoginResponse.future,
            2 => Future.value(http.Response(jsonEncode(userJson), 200)),
            3 => Future.value(http.Response('{"access_token":"token-b"}', 200)),
            4 => Future.value(
              http.Response(
                jsonEncode({...userJson, 'email': 'second@example.com'}),
                200,
              ),
            ),
            _ => throw StateError('Unexpected request'),
          };
        }),
      );

      final first = controller.login(
        email: 'first@example.com',
        password: 'password-a',
      );
      await Future<void>.delayed(Duration.zero);
      final second = controller.login(
        email: 'second@example.com',
        password: 'password-b',
      );
      await Future<void>.delayed(Duration.zero);
      expect(call, 1);

      firstLoginResponse.complete(
        http.Response('{"access_token":"token-a"}', 200),
      );
      await first;
      await second;

      expect(call, 4);
      expect(storage.token, 'token-b');
      expect(controller.state.user?.email, 'second@example.com');
      controller.dispose();
    },
  );

  test('logout removes the token and session identity', () async {
    final storage = FakeTokenStorage(token: 'stored-token');
    final controller = buildController(
      storage,
      MockClient((_) async => http.Response(jsonEncode(userJson), 200)),
    );
    await controller.restoreSession();

    await controller.logout();

    expect(storage.token, isNull);
    expect(controller.state.status, AuthStatus.unauthenticated);
    controller.dispose();
  });
}
