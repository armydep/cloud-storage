import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/auth/domain/current_user.dart';

class AuthRepository {
  AuthRepository(this._apiClient, this._session);

  final ApiClient _apiClient;
  final AuthSession _session;

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

  Future<void> logout() => _session.clear();
}
