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
  GlobalKey<_CreateFolderDialogState>? _dialogKey;

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

    ref.listen(filesControllerProvider, (previous, next) {
      if (previous?.isCreatingFolder == true && next.isCreatingFolder == false) {
        if (next.createError == null) {
          _dialogKey?.currentState?.closeDialog();
        } else {
          _dialogKey?.currentState
              ?.updateState(error: next.createError, isLoading: false);
        }
      }
    });

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
              key: const Key('upload-file-button'),
              tooltip: 'Upload file',
              onPressed: () => _handleUploadFile(context, controller),
              icon: const Icon(Icons.upload_file),
            ),
            IconButton(
              key: const Key('create-folder-button'),
              tooltip: 'Create folder',
              onPressed: () => _showCreateFolderDialog(context, controller),
              icon: const Icon(Icons.create_new_folder),
            ),
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

  void _handleUploadFile(
    BuildContext context,
    FilesController controller,
  ) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Upload File'),
        content: const Text('Select a file from your device to upload'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              try {
                await controller.selectAndUploadFile();
                if (context.mounted) Navigator.pop(context);
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Upload error: $e')),
                  );
                }
              }
            },
            child: const Text('Select File'),
          ),
        ],
      ),
    );
  }

  void _showCreateFolderDialog(
    BuildContext context,
    FilesController controller,
  ) {
    _dialogKey = GlobalKey<_CreateFolderDialogState>();
    showDialog(
      context: context,
      builder: (context) => _CreateFolderDialogWidget(
        key: _dialogKey,
        onCreateFolder: (name) {
          _dialogKey?.currentState?.updateState(isLoading: true);
          controller.createFolder(name);
        },
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

    if (folder.isEmpty) {
      return RefreshIndicator(
        onRefresh: () => controller.refresh(),
        child: _buildEmptyState(),
      );
    } else {
      return _buildFolderContents(folder, controller, state);
    }
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
    FilesState state,
  ) {
    final items = [...folder.folders, ...folder.files];

    return RefreshIndicator(
      onRefresh: () => controller.refresh(),
      child: ListView.builder(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        itemCount: items.length,
        itemBuilder: (context, index) {
          final item = items[index];
          final filePath = state.getDownloadedFilePath(item.id);
          return FileListItem(
            item: item,
            onTap: item.isFolder && item.path != null
                ? () => controller.navigateToFolder(item.path!)
                : null,
            onDownload: item.isFile
                ? () => controller.downloadFile(item.id, item.name)
                : null,
            onCancel: item.isFile
                ? () => controller.cancelDownload(item.id)
                : null,
            onOpen: (item.isFile && filePath != null)
                ? () => controller.openDownloadedFile(filePath)
                : null,
            downloadProgress: item.isFile ? state.getDownloadProgress(item.id) : null,
            downloadError: item.isFile ? state.getDownloadError(item.id) : null,
            uploadProgress: item.isFile ? state.getUploadProgress(item.name) : null,
            uploadError: item.isFile ? state.getUploadError(item.name) : null,
          );
        },
      ),
    );
  }
}

class _CreateFolderDialogWidget extends StatefulWidget {
  final void Function(String name) onCreateFolder;

  const _CreateFolderDialogWidget({
    Key? key,
    required this.onCreateFolder,
  }) : super(key: key);

  @override
  State<_CreateFolderDialogWidget> createState() =>
      _CreateFolderDialogState();
}

class _CreateFolderDialogState extends State<_CreateFolderDialogWidget> {
  final _controller = TextEditingController();
  String? _error;
  bool _isLoading = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _handleCreate() {
    if (_isLoading) return;
    widget.onCreateFolder(_controller.text);
  }

  void updateState({String? error, bool? isLoading}) {
    if (!mounted) return;
    setState(() {
      _error = error;
      if (isLoading != null) _isLoading = isLoading;
    });
  }

  void closeDialog() {
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Create Folder'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _controller,
            enabled: !_isLoading,
            decoration: InputDecoration(
              hintText: 'Folder name',
              errorText: _error,
              errorMaxLines: 2,
            ),
            onChanged: (_) {
              if (_error != null) {
                setState(() => _error = null);
              }
            },
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _isLoading ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _isLoading ? null : _handleCreate,
          child: const Text('Create'),
        ),
      ],
    );
  }
}
