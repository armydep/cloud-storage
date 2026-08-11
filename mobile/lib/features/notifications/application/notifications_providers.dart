import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/notifications/application/notifications_controller.dart';
import 'package:cloudestorage/features/notifications/application/notifications_state.dart';
import 'package:cloudestorage/features/notifications/data/notifications_repository.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final notificationsRepositoryProvider = Provider<NotificationsRepository>((
  ref,
) {
  return NotificationsRepository(ref.watch(apiClientProvider));
});

// autoDispose so the poll timer (and its WidgetsBindingObserver) stop as
// soon as nothing is watching this anymore -- e.g. after logout, when the
// app shell that hosts the bell unmounts. Without this the timer would keep
// polling indefinitely in the background.
final notificationsControllerProvider =
    StateNotifierProvider.autoDispose<
      NotificationsController,
      NotificationsState
    >((ref) {
      return NotificationsController(
        ref.watch(notificationsRepositoryProvider),
      );
    });
