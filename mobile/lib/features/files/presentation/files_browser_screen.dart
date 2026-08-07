import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/files_state.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:cloudestorage/features/files/presentation/widgets/file_list_item.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class FilesBrowserScreen extends ConsumerStatefulWidget {
  const FilesBrowserScreen({super.key});

  @override
  ConsumerState<FilesBrowserScreen> createState() => _FilesBrowserScreenState();
}

class _FilesBrowserScreenState extends ConsumerState<FilesBrowserScreen> {
  late ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _scrollController = ScrollController();
    Future.microtask(
      () => ref.read(filesControllerProvider.notifier).loadFolder('root'),
    );
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final filesState = ref.watch(filesControllerProvider);
    final controller = ref.read(filesControllerProvider.notifier);

    return WillPopScope(
      onWillPop: () async {
        if (controller.canNavigateBack()) {
          await controller.navigateBack();
          return false;
        }
        return true;
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(filesState.folder?.name ?? 'Files'),
          actions: [
            IconButton(
              key: const Key('logout-button'),
              tooltip: 'Sign out',
              onPressed: () =>
                  ref.read(authControllerProvider.notifier).logout(),
              icon: const Icon(Icons.logout),
            ),
          ],
        ),
        body: _buildBody(filesState, controller),
      ),
    );
  }

  Widget _buildBody(
    FilesState state,
    FilesController controller,
  ) {
    if (state.isLoading && state.folder == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.hasError && state.folder == null) {
      return _buildErrorState(state.error!, controller);
    }

    final folder = state.folder;
    if (folder == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: () => controller.refresh(),
      child: folder.isEmpty
          ? _buildEmptyState()
          : _buildFolderContents(folder, controller),
    );
  }

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.8,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.folder_open,
                size: 64,
                color: Colors.grey[400],
              ),
              const SizedBox(height: 16),
              Text(
                'This folder is empty',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: Colors.grey[600],
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorState(String error, FilesController controller) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            size: 64,
            color: Colors.red[300],
          ),
          const SizedBox(height: 16),
          Text(
            error,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            key: const Key('retry-button'),
            onPressed: () => controller.refresh(),
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildFolderContents(
    FolderWithContents folder,
    FilesController controller,
  ) {
    final items = [...folder.folders, ...folder.files];

    return ListView.builder(
      controller: _scrollController,
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: items.length,
      itemBuilder: (context, index) {
        final item = items[index];
        return FileListItem(
          item: item,
          onTap: item.isFolder && item.path != null
              ? () => controller.navigateToFolder(item.path!)
              : null,
        );
      },
    );
  }
}
