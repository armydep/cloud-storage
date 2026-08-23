import 'dart:async';

import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show NetworkError, ServerError;
import 'package:cloudestorage/features/push/application/push_state.dart';
import 'package:cloudestorage/features/push/data/fcm_client.dart';
import 'package:cloudestorage/features/push/data/push_repository.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final fcmClientProvider = Provider<FcmClient>(
  (ref) => const FirebaseFcmClient(),
);

final pushRepositoryProvider = Provider<PushRepository>((ref) {
  return PushRepository(ref.watch(apiClientProvider));
});

final pushControllerProvider = StateNotifierProvider<PushController, PushState>(
  (ref) {
    ref.watch(currentUserIdProvider);
    final initiallyEnabled =
        ref.watch(authControllerProvider).user?.pushEnabled ?? false;
    return PushController(
      ref.watch(pushRepositoryProvider),
      ref.watch(fcmClientProvider),
      initiallyEnabled: initiallyEnabled,
    );
  },
);

class PushController extends StateNotifier<PushState> {
  final PushRepository _repository;
  final FcmClient _fcm;

  PushController(this._repository, this._fcm, {required bool initiallyEnabled})
    : super(PushState(isEnabled: initiallyEnabled));

  /// Requests the OS permission and sets the preference in one flow (design
  /// doc: "A settings toggle that requests the OS POST_NOTIFICATIONS
  /// permission and sets push_enabled together"). Declining the permission
  /// leaves push_enabled false and does not error -- it is the designed
  /// default, not a failure.
  Future<void> enable() async {
    state = state.copyWith(
      isLoading: true,
      clearError: true,
      permissionDenied: false,
    );
    try {
      final granted = await _fcm.requestPermission();
      if (!granted) {
        state = state.copyWith(isLoading: false, permissionDenied: true);
        return;
      }
      final token = await _fcm.getToken();
      if (token != null) {
        await _repository.registerToken(token: token, platform: 'android');
      }
      await _repository.setPushEnabled(true);
      state = state.copyWith(isEnabled: true, isLoading: false);
    } on ServerError catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
    } on NetworkError catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Could not enable push notifications. Please try again.',
      );
    }
  }

  /// Skips this user's tokens, it does not delete them -- re-enabling must
  /// not require the device to register again (design doc decision 16).
  Future<void> disable() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      await _repository.setPushEnabled(false);
      state = state.copyWith(isEnabled: false, isLoading: false);
    } on ServerError catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
    } on NetworkError catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Could not disable push notifications. Please try again.',
      );
    }
  }
}

/// Unregisters this device's current token, for `AuthRepository.logout` to
/// call before it clears the local session -- unregistering needs a valid
/// token to authenticate, so it must run first (design doc decision 6: this
/// is a security requirement, not hygiene).
final pushLogoutHookProvider = Provider<Future<void> Function()>((ref) {
  final repository = ref.watch(pushRepositoryProvider);
  final fcm = ref.watch(fcmClientProvider);
  return () async {
    final token = await fcm.getToken();
    if (token == null) return;
    await repository.unregisterToken(token);
  };
});

/// Registers this device's FCM token against the signed-in user and keeps
/// it current. Watching this from within the authenticated app shell is
/// what triggers "register on login" -- construction happens exactly when
/// the user becomes authenticated and the shell mounts -- and "re-register
/// on token refresh", via the stream subscription below. autoDispose tears
/// the subscription down on logout, mirroring
/// notifications_providers.dart's poll timer.
final pushDeviceRegistrationProvider = Provider.autoDispose<void>((ref) {
  final repository = ref.watch(pushRepositoryProvider);
  final fcm = ref.watch(fcmClientProvider);

  Future<void> register(String? token) async {
    try {
      final resolvedToken = token ?? await fcm.getToken();
      if (resolvedToken == null) return;
      await repository.registerToken(token: resolvedToken, platform: 'android');
    } on Object catch (e) {
      // Registration failure must never break the signed-in experience.
      debugPrint('Device token registration failed: $e');
    }
  }

  unawaited(register(null));
  final subscription = fcm.onTokenRefresh.listen(register);
  ref.onDispose(subscription.cancel);

  // Foreground suppression (design doc decision 14): a message arriving
  // while the app is in front must not raise a system banner over itself.
  // firebase_messaging already delivers foreground messages through this
  // separate stream instead of auto-displaying them, so the correct
  // handling here is to do nothing user-visible -- not to call the local
  // notification client. The feed still gets the same event over its own,
  // separate channel (q.inapp), which is what stays authoritative.
  final foregroundSubscription = fcm.onMessage.listen((_) {});
  ref.onDispose(foregroundSubscription.cancel);
});
