import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/shared_files_providers.dart';
import 'package:cloudestorage/features/files/application/shared_files_state.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:cloudestorage/features/notifications/application/notifications_providers.dart';
import 'package:cloudestorage/features/notifications/presentation/notifications_screen.dart';
import 'package:cloudestorage/features/notifications/presentation/widgets/notification_bell_icon.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

class SharedWithMeScreen extends ConsumerStatefulWidget {
  const SharedWithMeScreen({super.key});

  @override
  ConsumerState<SharedWithMeScreen> createState() => _SharedWithMeScreenState();
}

class _SharedWithMeScreenState extends ConsumerState<SharedWithMeScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(sharedFilesControllerProvider.notifier).load(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sharedFilesControllerProvider);
    final unreadCount = ref.watch(
      notificationsControllerProvider.select((value) => value.unreadCount),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Shared with me'),
        actions: [
          NotificationBellIcon(
            unreadCount: unreadCount,
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => const NotificationsScreen(),
              ),
            ),
          ),
          IconButton(
            key: const Key('logout-button'),
            tooltip: 'Sign out',
            onPressed: () => ref.read(authControllerProvider.notifier).logout(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: _buildBody(state),
    );
  }

  Widget _buildBody(SharedFilesState state) {
    if (state.isLoading && state.files.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(key: Key('shared-files-loading')),
      );
    }
    if (state.error != null && state.files.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(state.error!, textAlign: TextAlign.center),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              key: const Key('shared-files-retry-button'),
              onPressed: () =>
                  ref.read(sharedFilesControllerProvider.notifier).load(),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }
    if (state.isEmpty) {
      return RefreshIndicator(
        onRefresh: () =>
            ref.read(sharedFilesControllerProvider.notifier).refresh(),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: const [
            SizedBox(height: 160),
            Icon(Icons.people_outline, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Center(
              child: Text(
                'No files shared with you',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
            ),
            SizedBox(height: 8),
            Center(
              child: Text('Files other users share with you will appear here.'),
            ),
          ],
        ),
      );
    }

    final hasRefreshError = state.error != null;
    return RefreshIndicator(
      onRefresh: () =>
          ref.read(sharedFilesControllerProvider.notifier).refresh(),
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: state.files.length + (hasRefreshError ? 1 : 0),
        itemBuilder: (context, index) {
          if (hasRefreshError && index == 0) {
            return MaterialBanner(
              content: Text(state.error!),
              actions: [
                TextButton(
                  key: const Key('shared-files-refresh-retry-button'),
                  onPressed: () => ref
                      .read(sharedFilesControllerProvider.notifier)
                      .refresh(),
                  child: const Text('Retry'),
                ),
              ],
            );
          }
          final fileIndex = index - (hasRefreshError ? 1 : 0);
          return _SharedFileListItem(file: state.files[fileIndex]);
        },
      ),
    );
  }
}

class _SharedFileListItem extends ConsumerWidget {
  final SharedFile file;

  const _SharedFileListItem({required this.file});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final downloadState = ref.watch(filesControllerProvider);
    final controller = ref.read(filesControllerProvider.notifier);
    final progress = downloadState.getDownloadProgress(file.id);
    final error = downloadState.getDownloadError(file.id);
    final downloadedPath = downloadState.getDownloadedFilePath(file.id);

    return Stack(
      children: [
        Padding(
          key: Key('shared-file-${file.id}'),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Icon(Icons.insert_drive_file_outlined),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      file.name,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 4),
                    Text(file.ownerEmail),
                    Text(
                      '${file.mimeType.isEmpty ? file.category : file.mimeType} · '
                      '${file.displaySize} · Shared '
                      '${DateFormat.yMMMd().format(file.sharedAt.toLocal())}',
                    ),
                    if (error != null)
                      Text(error, style: const TextStyle(color: Colors.red)),
                  ],
                ),
              ),
              if (downloadedPath != null)
                IconButton(
                  key: Key('open-shared-file-${file.id}'),
                  tooltip: 'Open ${file.name}',
                  onPressed: () =>
                      controller.openDownloadedFile(downloadedPath),
                  icon: const Icon(Icons.open_in_new),
                )
              else
                IconButton(
                  key: Key('download-shared-file-${file.id}'),
                  tooltip: error == null
                      ? 'Download ${file.name}'
                      : 'Retry download ${file.name}',
                  onPressed: progress == null
                      ? () => controller.downloadFile(file.id, file.name)
                      : null,
                  icon: progress == null
                      ? Icon(error == null ? Icons.download : Icons.refresh)
                      : const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                ),
            ],
          ),
        ),
        if (progress != null)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: LinearProgressIndicator(value: progress),
          ),
      ],
    );
  }
}
