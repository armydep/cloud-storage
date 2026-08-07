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

  static const String _folderNamePattern = r'^[a-zA-Z0-9\s\-_]+$';
  static const int _maxFolderNameLength = 255;

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

  String? validateFolderName(String name) {
    if (name.isEmpty) {
      return 'Folder name cannot be empty';
    }
    if (name.length > _maxFolderNameLength) {
      return 'Folder name cannot exceed $_maxFolderNameLength characters';
    }
    if (!RegExp(_folderNamePattern).hasMatch(name)) {
      return 'Folder name can only contain letters, numbers, spaces, dashes, and underscores';
    }
    return null;
  }

  Future<void> createFolder(String name) async {
    final validationError = validateFolderName(name);
    if (validationError != null) {
      state = state.copyWith(createError: validationError);
      return;
    }

    state = state.copyWith(isCreatingFolder: true, createError: null);

    try {
      final currentPath = _ref.read(currentFolderPathProvider);
      await _repository.createFolder(
        parentPath: currentPath,
        name: name,
      );
      await refresh();
      state = state.copyWith(isCreatingFolder: false, createError: null);
    } on DuplicateFolderNameError catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Folder already exists',
      );
    } on InvalidFolderNameError catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Invalid folder name',
      );
    } on FolderNotFoundError catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Parent folder not found',
      );
    } on ServerError catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Server error. Please try again.',
      );
    } on NetworkError catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'An error occurred. Please try again.',
      );
    }
  }
}
