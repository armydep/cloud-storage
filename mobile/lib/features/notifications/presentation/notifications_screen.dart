import 'package:cloudestorage/features/notifications/application/notifications_controller.dart';
import 'package:cloudestorage/features/notifications/application/notifications_providers.dart';
import 'package:cloudestorage/features/notifications/application/notifications_state.dart';
import 'package:cloudestorage/features/notifications/presentation/widgets/notification_list_tile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    // A read-only fetch -- opening the feed must not mark anything read
    // (phase-9-in-app-notifications.md decision 11).
    Future.microtask(
      () => ref.read(notificationsControllerProvider.notifier).loadFirstPage(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notificationsControllerProvider);
    final controller = ref.read(notificationsControllerProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          TextButton(
            key: const Key('mark-all-read-button'),
            onPressed: state.hasUnread ? controller.markAllRead : null,
            child: const Text('Mark all read'),
          ),
        ],
      ),
      body: _buildBody(state, controller),
    );
  }

  Widget _buildBody(
    NotificationsState state,
    NotificationsController controller,
  ) {
    if (state.isLoading && state.notifications.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.error != null && state.notifications.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(state.error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                key: const Key('retry-button'),
                onPressed: controller.loadFirstPage,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (state.notifications.isEmpty) {
      return RefreshIndicator(
        onRefresh: controller.loadFirstPage,
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: const Center(child: Text('No notifications yet.')),
            ),
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: controller.loadFirstPage,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: state.notifications.length + (state.hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == state.notifications.length) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Center(
                child: state.isLoadingMore
                    ? const CircularProgressIndicator()
                    : TextButton(
                        key: const Key('load-more-button'),
                        onPressed: controller.loadMore,
                        child: const Text('Load more'),
                      ),
              ),
            );
          }

          final notification = state.notifications[index];
          return NotificationListTile(
            notification: notification,
            onMarkRead: () => controller.markRead(notification.id),
          );
        },
      ),
    );
  }
}
