import 'package:cloudestorage/core/config/app_config.dart';
import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/application/auth_controller.dart';
import 'package:cloudestorage/features/auth/application/auth_state.dart';
import 'package:cloudestorage/features/auth/data/auth_repository.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/auth/data/token_storage.dart';
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
