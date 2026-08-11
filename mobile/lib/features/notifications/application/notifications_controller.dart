import 'dart:async';

import 'package:cloudestorage/features/notifications/application/notifications_state.dart';
import 'package:cloudestorage/features/notifications/data/notifications_repository.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Matches the web client's polling cadence
/// (frontend/src/hooks/useNotifications.ts), within the 15-30s window from
/// phase-9-in-app-notifications.md decision 5.
const notificationsPollInterval = Duration(seconds: 20);

class NotificationsController extends StateNotifier<NotificationsState>
    with WidgetsBindingObserver {
  final NotificationsRepository _repository;
  Timer? _pollTimer;

  NotificationsController(this._repository, {bool autoStart = true})
    : super(const NotificationsState()) {
    WidgetsBinding.instance.addObserver(this);
    if (autoStart) {
      unawaited(refreshUnreadCount());
      _startPolling();
    }
  }

  // The base parameter name `state` would shadow StateNotifier's own `state`
  // getter/setter for the rest of this method body.
  @override
  // ignore: avoid_renaming_method_parameters
  void didChangeAppLifecycleState(AppLifecycleState lifecycleState) {
    if (lifecycleState == AppLifecycleState.resumed) {
      _startPolling();
      unawaited(refreshUnreadCount());
    } else {
      _stopPolling();
    }
  }

  bool get isPolling => _pollTimer != null;

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(
      notificationsPollInterval,
      (_) => refreshUnreadCount(),
    );
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> refreshUnreadCount() async {
    try {
      final count = await _repository.getUnreadCount();
      if (!mounted) return;
      state = state.copyWith(unreadCount: count);
    } catch (_) {
      // Silent: the badge keeps its last known value and retries next poll.
    }
  }

  Future<void> loadFirstPage() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final page = await _repository.listNotifications();
      if (!mounted) return;
      state = state.copyWith(
        isLoading: false,
        notifications: page.data,
        nextCursor: page.nextCursor,
        clearNextCursor: page.nextCursor == null,
        clearError: true,
      );
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> loadMore() async {
    if (!state.hasMore || state.isLoadingMore) return;

    state = state.copyWith(isLoadingMore: true, clearError: true);
    try {
      final page = await _repository.listNotifications(
        cursor: state.nextCursor,
      );
      if (!mounted) return;
      state = state.copyWith(
        isLoadingMore: false,
        notifications: [...state.notifications, ...page.data],
        nextCursor: page.nextCursor,
        clearNextCursor: page.nextCursor == null,
      );
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(isLoadingMore: false, error: e.toString());
    }
  }

  Future<void> markRead(String notificationId) async {
    try {
      final updated = await _repository.markRead(notificationId);
      if (!mounted) return;
      state = state.copyWith(
        notifications: [
          for (final notification in state.notifications)
            if (notification.id == notificationId) updated else notification,
        ],
      );
      await refreshUnreadCount();
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> markAllRead() async {
    try {
      await _repository.markAllRead();
      if (!mounted) return;
      final now = DateTime.now();
      state = state.copyWith(
        notifications: [
          for (final notification in state.notifications)
            notification.isUnread ? notification.markedRead(now) : notification,
        ],
        unreadCount: 0,
      );
    } catch (e) {
      if (!mounted) return;
      state = state.copyWith(error: e.toString());
    }
  }

  @override
  void dispose() {
    _stopPolling();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
