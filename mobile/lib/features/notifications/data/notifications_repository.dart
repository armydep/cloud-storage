import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/notifications/domain/notification_models.dart';

class NotificationsRepository {
  final ApiClient apiClient;

  NotificationsRepository(this.apiClient);

  Future<NotificationsPage> listNotifications({
    int limit = 20,
    String? cursor,
  }) async {
    try {
      final json = await apiClient.getJson(
        '/api/v1/notifications',
        authenticated: true,
        queryParameters: {'limit': '$limit', 'cursor': ?cursor},
      );
      return NotificationsPage.fromJson(json);
    } on ApiException catch (e) {
      throw _mapError(e, 'Notifications could not be loaded.');
    }
  }

  Future<int> getUnreadCount() async {
    try {
      final json = await apiClient.getJson(
        '/api/v1/notifications/unread-count',
        authenticated: true,
      );
      return json['count'] as int? ?? 0;
    } on ApiException catch (e) {
      throw _mapError(e, 'Unread count could not be loaded.');
    }
  }

  Future<AppNotification> markRead(String notificationId) async {
    try {
      final json = await apiClient.postJson(
        '/api/v1/notifications/$notificationId/read',
        authenticated: true,
      );
      return AppNotification.fromJson(json);
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw NotificationNotFoundError('Notification not found');
      }
      throw _mapError(e, 'Could not mark this notification read. Try again.');
    }
  }

  Future<void> markAllRead() async {
    try {
      await apiClient.postEmpty(
        '/api/v1/notifications/read-all',
        authenticated: true,
      );
    } on ApiException catch (e) {
      throw _mapError(e, 'Could not mark all notifications read. Try again.');
    }
  }

  Exception _mapError(ApiException e, String fallback) {
    if (e.isNetworkError) {
      return NotificationsNetworkError(
        'Connection lost. Please check your network and try again.',
      );
    }
    if (e.statusCode != null && e.statusCode! >= 500) {
      return NotificationsServerError(fallback);
    }
    return NotificationsApiError(e.message);
  }
}

class NotificationNotFoundError implements Exception {
  final String message;
  NotificationNotFoundError(this.message);

  @override
  String toString() => message;
}

class NotificationsApiError implements Exception {
  final String message;
  NotificationsApiError(this.message);

  @override
  String toString() => message;
}

class NotificationsServerError implements Exception {
  final String message;
  NotificationsServerError(this.message);

  @override
  String toString() => message;
}

class NotificationsNetworkError implements Exception {
  final String message;
  NotificationsNetworkError(this.message);

  @override
  String toString() => message;
}
