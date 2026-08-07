import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/auth/application/auth_state.dart';
import 'package:cloudestorage/features/auth/presentation/authenticated_screen.dart';
import 'package:cloudestorage/features/auth/presentation/login_screen.dart';
import 'package:cloudestorage/features/auth/presentation/session_error_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

final appRouterProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier(0);
  ref.listen<AuthState>(authControllerProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      final target = switch (auth.status) {
        AuthStatus.initializing => '/splash',
        AuthStatus.restoreFailure => '/session-error',
        AuthStatus.unauthenticated || AuthStatus.authenticating => '/login',
        AuthStatus.authenticated => '/',
      };
      return state.matchedLocation == target ? null : target;
    },
    routes: [
      GoRoute(path: '/', builder: (_, _) => const AuthenticatedScreen()),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(
        path: '/splash',
        builder: (_, _) => const Scaffold(
          body: Center(
            child: CircularProgressIndicator(key: Key('session-loading')),
          ),
        ),
      ),
      GoRoute(
        path: '/session-error',
        builder: (_, _) => const SessionErrorScreen(),
      ),
    ],
  );
});
