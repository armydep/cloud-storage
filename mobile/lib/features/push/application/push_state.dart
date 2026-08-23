import 'package:flutter/foundation.dart';

@immutable
class PushState {
  const PushState({
    this.isEnabled = false,
    this.isLoading = false,
    this.error,
    this.permissionDenied = false,
  });

  final bool isEnabled;
  final bool isLoading;
  final String? error;
  final bool permissionDenied;

  bool get hasError => error != null;

  PushState copyWith({
    bool? isEnabled,
    bool? isLoading,
    String? error,
    bool clearError = false,
    bool? permissionDenied,
  }) {
    return PushState(
      isEnabled: isEnabled ?? this.isEnabled,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      permissionDenied: permissionDenied ?? this.permissionDenied,
    );
  }
}
