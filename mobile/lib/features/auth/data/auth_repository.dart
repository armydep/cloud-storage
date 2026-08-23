import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/auth/domain/current_user.dart';
import 'package:flutter/foundation.dart';

class AuthRepository {
  AuthRepository(
    this._apiClient,
    this._session, {
    Future<void> Function()? onBeforeLogout,
  }) : _onBeforeLogout = onBeforeLogout ?? (() async {});

  final ApiClient _apiClient;
  final AuthSession _session;
  final Future<void> Function() _onBeforeLogout;

  Future<CurrentUser> login({
    required String email,
    required String password,
  }) async {
    final response = await _apiClient.postForm(
      '/api/v1/login/access-token',
      fields: {'username': email.trim(), 'password': password},
    );
    final token = response['access_token'];
    if (token is! String || token.isEmpty) {
      throw const ApiException(
        message: 'The service returned an invalid response.',
      );
    }
    await _session.saveToken(token);
    try {
      return await validateSession(authenticationToken: token);
    } on ApiException catch (error) {
      final isTransient =
          error.isNetworkError ||
          (error.statusCode != null && error.statusCode! >= 500);
      if (!isTransient) await _session.clearIfMatches(token);
      rethrow;
    }
  }

  Future<CurrentUser> validateSession({String? authenticationToken}) async {
    final response = await _apiClient.postJson(
      '/api/v1/login/test-token',
      authenticated: true,
      authenticationToken: authenticationToken,
    );
    try {
      return CurrentUser.fromJson(response);
    } on Object {
      throw const ApiException(
        message: 'The service returned an invalid response.',
      );
    }
  }

  Future<void> logout() async {
    // Must run before the session is cleared -- unregistering needs a valid
    // token to authenticate, and this is a security requirement, not
    // hygiene: if it's skipped, the next person to sign in on this device
    // inherits the previous user's notifications (design doc decision 6).
    // Best-effort: a failure here must never block the user from signing
    // out.
    try {
      await _onBeforeLogout();
    } on Object catch (e) {
      debugPrint('Pre-logout hook failed: $e');
    }
    await _session.clear();
  }
}
