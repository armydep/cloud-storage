import 'package:cloudestorage/features/notifications/domain/notification_models.dart';
import 'package:cloudestorage/features/notifications/domain/render_notification.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class NotificationListTile extends StatelessWidget {
  const NotificationListTile({
    super.key,
    required this.notification,
    required this.onMarkRead,
  });

  final AppNotification notification;
  final VoidCallback onMarkRead;

  @override
  Widget build(BuildContext context) {
    final isUnread = notification.isUnread;

    return ListTile(
      key: Key('notification-${notification.id}'),
      tileColor: isUnread
          ? Theme.of(
              context,
            ).colorScheme.primaryContainer.withValues(alpha: 0.3)
          : null,
      title: Text(renderNotificationText(notification)),
      subtitle: Text(
        DateFormat.yMMMd().add_jm().format(notification.createdAt.toLocal()),
      ),
      trailing: isUnread
          ? TextButton(
              key: Key('mark-read-${notification.id}'),
              onPressed: onMarkRead,
              child: const Text('Mark read'),
            )
          : null,
    );
  }
}
