import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_state.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final filesRepositoryProvider = Provider<FilesRepository>((ref) {
  return FilesRepository(ref.watch(apiClientProvider));
});

final currentFolderPathProvider = StateProvider<String>((ref) => 'root');

final folderContentsProvider =
    FutureProvider.family<FolderWithContents, String>((ref, path) async {
  final repository = ref.watch(filesRepositoryProvider);
  return repository.getFolder(path: path);
});

final currentFolderContentsProvider = FutureProvider<FolderWithContents>((ref) {
  final currentPath = ref.watch(currentFolderPathProvider);
  return ref.watch(folderContentsProvider(currentPath).future);
});

final filesControllerProvider =
    StateNotifierProvider<FilesController, FilesState>((ref) {
  return FilesController(
    ref.watch(filesRepositoryProvider),
    ref,
  );
});

class FilesController extends StateNotifier<FilesState> {
  final FilesRepository _repository;
  final Ref _ref;
  final List<String> _navigationStack = ['root'];

  FilesController(this._repository, this._ref) : super(const FilesState());

  Future<void> loadFolder(String path) async {
    state = const FilesState.loading();
    _ref.read(currentFolderPathProvider.notifier).state = path;

    try {
      final folder = await _repository.getFolder(path: path);
      state = FilesState.loaded(folder);
    } on FolderNotFoundError catch (e) {
      state = FilesState.error('Folder not found');
    } on ServerError catch (e) {
      state = FilesState.error('Server error. Please try again.');
    } on NetworkError catch (e) {
      state = FilesState.error('Network error. Please check your connection.');
    } catch (e) {
      state = FilesState.error('An error occurred. Please try again.');
    }
  }

  Future<void> navigateToFolder(String path) async {
    _navigationStack.add(path);
    await loadFolder(path);
  }

  Future<void> navigateBack() async {
    if (_navigationStack.length > 1) {
      _navigationStack.removeLast();
      await loadFolder(_navigationStack.last);
    }
  }

  Future<void> refresh() async {
    final currentPath = _ref.read(currentFolderPathProvider);
    await loadFolder(currentPath);
  }

  bool canNavigateBack() => _navigationStack.length > 1;
}
