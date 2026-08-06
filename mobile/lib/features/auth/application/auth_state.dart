import 'package:cloudestorage/features/auth/domain/current_user.dart';

enum AuthStatus {
  initializing,
  unauthenticated,
  authenticating,
  authenticated,
  restoreFailure,
}

class AuthState {
  const AuthState({required this.status, this.user, this.errorMessage});
  const AuthState.initializing() : this(status: AuthStatus.initializing);
  const AuthState.unauthenticated({String? errorMessage})
    : this(status: AuthStatus.unauthenticated, errorMessage: errorMessage);
  const AuthState.authenticating() : this(status: AuthStatus.authenticating);
  const AuthState.authenticated(CurrentUser user)
    : this(status: AuthStatus.authenticated, user: user);
  const AuthState.restoreFailure(String message)
    : this(status: AuthStatus.restoreFailure, errorMessage: message);

  final AuthStatus status;
  final CurrentUser? user;
  final String? errorMessage;
}
