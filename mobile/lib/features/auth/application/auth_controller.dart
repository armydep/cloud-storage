import 'dart:async';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/application/auth_state.dart';
import 'package:cloudestorage/features/auth/data/auth_repository.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._repository, this._session, {bool restoreOnCreate = true})
    : super(const AuthState.initializing()) {
    _invalidations = _session.invalidations.listen((_) {
      state = const AuthState.unauthenticated();
    });
    if (restoreOnCreate) unawaited(restoreSession());
  }

  final AuthRepository _repository;
  final AuthSession _session;
  late final StreamSubscription<void> _invalidations;
  Future<void> _pendingOperation = Future.value();

  Future<void> restoreSession() => _locked(_restoreSession);

  Future<void> _restoreSession() async {
    state = const AuthState.initializing();
    try {
      final token = await _session.readToken();
      if (token == null || token.isEmpty) {
        state = const AuthState.unauthenticated();
        return;
      }
      state = AuthState.authenticated(await _repository.validateSession());
    } on ApiException catch (error) {
      state = error.isAuthenticationFailure
          ? const AuthState.unauthenticated()
          : AuthState.restoreFailure(error.message);
    } on Object {
      state = const AuthState.restoreFailure(
        'Secure session storage is unavailable. Please retry.',
      );
    }
  }

  Future<void> login({required String email, required String password}) {
    return _locked(() => _login(email: email, password: password));
  }

  Future<void> _login({required String email, required String password}) async {
    state = const AuthState.authenticating();
    try {
      state = AuthState.authenticated(
        await _repository.login(email: email, password: password),
      );
    } on ApiException catch (error) {
      if (error.isNetworkError) {
        String? token;
        try {
          token = await _session.readToken();
        } on Object {
          state = const AuthState.unauthenticated(
            errorMessage:
                'Secure session storage is unavailable. Please retry.',
          );
          return;
        }
        if (token != null && token.isNotEmpty) {
          state = AuthState.restoreFailure(error.message);
          return;
        }
      }
      state = AuthState.unauthenticated(errorMessage: error.message);
    } on Object {
      state = const AuthState.unauthenticated(
        errorMessage: 'Secure session storage is unavailable. Please retry.',
      );
    }
  }

  Future<void> logout() => _locked(_logout);

  Future<void> _logout() async {
    try {
      await _repository.logout();
      state = const AuthState.unauthenticated();
    } on Object {
      state = const AuthState.restoreFailure(
        'The secure session could not be cleared. Please retry.',
      );
    }
  }

  Future<void> _locked(Future<void> Function() operation) {
    final result = _pendingOperation.then((_) => operation());
    _pendingOperation = result.then<void>((_) {}, onError: (_) {});
    return result;
  }

  @override
  void dispose() {
    _invalidations.cancel();
    super.dispose();
  }
}
