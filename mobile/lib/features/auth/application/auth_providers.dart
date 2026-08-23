import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/application/auth_controller.dart';
import 'package:cloudestorage/features/auth/application/auth_state.dart';
import 'package:cloudestorage/features/auth/data/auth_repository.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/auth/data/token_storage.dart';
import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

final appConfigProvider = Provider<AppConfig>(
  (ref) =>
      throw UnimplementedError('AppConfig must be overridden at bootstrap.'),
);

final tokenStorageProvider = Provider<TokenStorage>(
  (ref) => SecureTokenStorage(),
);

final httpClientProvider = Provider<http.Client>((ref) => http.Client());

final authSessionProvider = Provider<AuthSession>((ref) {
  final session = AuthSession(ref.watch(tokenStorageProvider));
  ref.onDispose(session.dispose);
  return session;
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient(
    ref.watch(appConfigProvider).apiBaseUri,
    httpClient: ref.watch(httpClientProvider),
    authSession: ref.watch(authSessionProvider),
  );
  ref.onDispose(client.close);
  return client;
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.watch(apiClientProvider),
    ref.watch(authSessionProvider),
    onBeforeLogout: ref.watch(pushLogoutHookProvider),
  );
});

final authControllerProvider = StateNotifierProvider<AuthController, AuthState>(
  (ref) {
    return AuthController(
      ref.watch(authRepositoryProvider),
      ref.watch(authSessionProvider),
    );
  },
);

/// The signed-in user's id, or `null` while signed out.
///
/// Per-account providers watch this so their state is rebuilt from scratch
/// whenever the identity changes — on sign-out (id becomes `null`) and on the
/// next sign-in (id becomes the new user's). Without it, cross-account
/// isolation would rest on the router happening to unmount the widget tree on
/// logout, which nothing in the code enforces.
///
/// This resolves to `String?`, so dependents rebuild only when the identity
/// actually changes, not on unrelated auth-state transitions.
final currentUserIdProvider = Provider<String?>((ref) {
  return ref.watch(authControllerProvider).user?.id;
});
