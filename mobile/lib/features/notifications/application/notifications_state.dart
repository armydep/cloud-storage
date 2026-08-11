import 'package:cloudestorage/features/notifications/domain/notification_models.dart';
import 'package:flutter/foundation.dart';

@immutable
class NotificationsState {
  final int unreadCount;
  final List<AppNotification> notifications;
  final String? nextCursor;
  final bool isLoading;
  final bool isLoadingMore;
  final String? error;

  const NotificationsState({
    this.unreadCount = 0,
    this.notifications = const [],
    this.nextCursor,
    this.isLoading = false,
    this.isLoadingMore = false,
    this.error,
  });

  bool get hasMore => nextCursor != null;

  // Driven by the polled unread count rather than the loaded page(s): the
  // feed is unbounded and paginated, so "any unread on the loaded page" is
  // not the same as "any unread at all" -- an older, unfetched page could
  // still hold unread rows.
  bool get hasUnread => unreadCount > 0;

  NotificationsState copyWith({
    int? unreadCount,
    List<AppNotification>? notifications,
    String? nextCursor,
    bool clearNextCursor = false,
    bool? isLoading,
    bool? isLoadingMore,
    String? error,
    bool clearError = false,
  }) {
    return NotificationsState(
      unreadCount: unreadCount ?? this.unreadCount,
      notifications: notifications ?? this.notifications,
      nextCursor: clearNextCursor ? null : (nextCursor ?? this.nextCursor),
      isLoading: isLoading ?? this.isLoading,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      error: clearError ? null : (error ?? this.error),
    );
  }
}
