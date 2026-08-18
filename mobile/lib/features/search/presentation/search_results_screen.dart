import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/files_state.dart';
import 'package:cloudestorage/features/files/presentation/widgets/file_list_item.dart';
import 'package:cloudestorage/features/search/application/search_providers.dart';
import 'package:cloudestorage/features/search/application/search_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// Matches the categories search-svc accepts (search-svc/app/schemas.py
// FileCategory) and the wording used by the web client's search UI
// (frontend/src/features/search/SearchFiles.tsx).
const List<String> kSearchCategories = [
  'image',
  'video',
  'audio',
  'document',
  'spreadsheet',
  'archive',
  'other',
];

class SearchResultsScreen extends ConsumerStatefulWidget {
  final String folderPath;

  const SearchResultsScreen({required this.folderPath, super.key});

  @override
  ConsumerState<SearchResultsScreen> createState() =>
      _SearchResultsScreenState();
}

class _SearchResultsScreenState extends ConsumerState<SearchResultsScreen> {
  late final TextEditingController _textController;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController();
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = searchControllerProvider(widget.folderPath);
    final state = ref.watch(provider);
    final controller = ref.read(provider.notifier);
    final filesState = ref.watch(filesControllerProvider);
    final filesController = ref.read(filesControllerProvider.notifier);

    return Scaffold(
      appBar: AppBar(title: Text('Search in ${widget.folderPath}')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Column(
              children: [
                TextField(
                  key: const Key('search-query-field'),
                  controller: _textController,
                  textInputAction: TextInputAction.search,
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.search),
                    hintText: 'Search files',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: controller.updateQuery,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String?>(
                  key: const Key('search-category-dropdown'),
                  initialValue: state.category,
                  decoration: const InputDecoration(
                    labelText: 'Category',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    const DropdownMenuItem(
                      value: null,
                      child: Text('All categories'),
                    ),
                    ...kSearchCategories.map(
                      (category) => DropdownMenuItem(
                        value: category,
                        child: Text(_capitalize(category)),
                      ),
                    ),
                  ],
                  onChanged: controller.updateCategory,
                ),
              ],
            ),
          ),
          Expanded(
            child: _buildBody(state, controller, filesState, filesController),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(
    SearchState state,
    FileSearchController controller,
    FilesState filesState,
    FilesController filesController,
  ) {
    if (!state.isSearchActive) {
      return _buildIdleState();
    }
    if (state.isLoading) {
      return const Center(
        key: Key('search-loading'),
        child: CircularProgressIndicator(),
      );
    }
    // A search failure must never look like "no matches" (decision 15): it
    // gets its own branch, checked before the empty-results branch below.
    if (state.hasError) {
      return _buildErrorState(state.error!, controller);
    }
    if (state.results.isEmpty) {
      return _buildEmptyState();
    }
    return _buildResults(state, controller, filesState, filesController);
  }

  Widget _buildIdleState() {
    return const Center(
      key: Key('search-idle'),
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Type a name or choose a category to search this folder.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return const Center(
      key: Key('search-empty'),
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('No matching files'),
            SizedBox(height: 8),
            Text(
              'Try a different name or category in this folder.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(String error, FileSearchController controller) {
    return Center(
      key: const Key('search-error'),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(error, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              key: const Key('search-retry-button'),
              onPressed: controller.retry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResults(
    SearchState state,
    FileSearchController controller,
    FilesState filesState,
    FilesController filesController,
  ) {
    return ListView.builder(
      key: const Key('search-results-list'),
      itemCount: state.results.length + (state.hasNextPage ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= state.results.length) {
          return Padding(
            padding: const EdgeInsets.all(16),
            child: Center(
              child: state.isLoadingMore
                  ? const CircularProgressIndicator()
                  : ElevatedButton(
                      key: const Key('search-load-more-button'),
                      onPressed: controller.loadMore,
                      child: const Text('Load more'),
                    ),
            ),
          );
        }

        final result = state.results[index];
        final item = result.toFileContent();
        final filePath = filesState.getDownloadedFilePath(item.id);
        // Opening a result matches existing file-row behaviour: it is wired
        // to the same FilesController the folder browser uses, so download
        // progress and errors are shared rather than duplicated.
        return FileListItem(
          key: Key('search-result-${item.id}'),
          item: item,
          onDownload: () => filesController.downloadFile(item.id, item.name),
          onCancel: () => filesController.cancelDownload(item.id),
          onOpen: filePath != null
              ? () => filesController.openDownloadedFile(filePath)
              : null,
          downloadProgress: filesState.getDownloadProgress(item.id),
          downloadError: filesState.getDownloadError(item.id),
          // Results can come from any subfolder of the one searched
          // (decision 11), so the row must say which one.
          folderPathCaption: result.folderPath,
        );
      },
    );
  }

  String _capitalize(String value) =>
      value.isEmpty ? value : '${value[0].toUpperCase()}${value.substring(1)}';
}
