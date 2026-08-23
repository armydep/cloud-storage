import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show ApiError, NetworkError, ServerError;

class PushRepository {
  final ApiClient apiClient;

  PushRepository(this.apiClient);

  Future<void> registerToken({
    required String token,
    required String platform,
  }) async {
    try {
      await apiClient.postJson(
        '/api/v1/push/device-tokens',
        authenticated: true,
        body: {'token': token, 'platform': platform},
      );
    } on ApiException catch (e) {
      throw _mapException(e, 'Device registration failed. Please try again.');
    }
  }

  /// Unregisters `token`, scoped to the caller by the backend. A device is
  /// a device, not a per-user record (design doc decision 6) -- this must
  /// be called before the local session is cleared on logout, or the next
  /// person signing in on this device inherits the previous user's
  /// registration.
  Future<void> unregisterToken(String token) async {
    try {
      await apiClient.delete(
        '/api/v1/push/device-tokens/${Uri.encodeComponent(token)}',
        authenticated: true,
      );
    } on ApiException catch (e) {
      throw _mapException(e, 'Could not unregister this device.');
    }
  }

  /// Push is opt-in and per-user (design doc decision 16): this sets the
  /// preference the push consumer checks before fanning out, and never
  /// touches device_tokens -- disabling skips tokens, it does not delete
  /// them.
  Future<void> setPushEnabled(bool enabled) async {
    try {
      await apiClient.patchJson(
        '/api/v1/users/me',
        authenticated: true,
        body: {'push_enabled': enabled},
      );
    } on ApiException catch (e) {
      throw _mapException(e, 'Could not update your push preference.');
    }
  }

  Exception _mapException(ApiException e, String genericMessage) {
    if (e.statusCode != null && e.statusCode! >= 500) {
      return ServerError(genericMessage);
    } else if (e.isNetworkError) {
      return NetworkError(
        'Connection lost. Please check your network and try again.',
      );
    } else {
      return ApiError(e.message);
    }
  }
}
