import 'package:flutter/material.dart';

class NotificationBellIcon extends StatelessWidget {
  const NotificationBellIcon({
    super.key,
    required this.unreadCount,
    required this.onPressed,
  });

  final int unreadCount;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final icon = IconButton(
      key: const Key('notifications-button'),
      tooltip: 'Notifications',
      onPressed: onPressed,
      icon: const Icon(Icons.notifications_outlined),
    );

    if (unreadCount <= 0) {
      return icon;
    }

    return Badge(
      key: const Key('notifications-unread-badge'),
      label: Text(unreadCount > 99 ? '99+' : '$unreadCount'),
      child: icon,
    );
  }
}
