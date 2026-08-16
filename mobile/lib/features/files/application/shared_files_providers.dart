import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/shared_files_state.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final sharedFilesControllerProvider =
    StateNotifierProvider.autoDispose<SharedFilesController, SharedFilesState>((
      ref,
    ) {
      return SharedFilesController(ref.watch(filesRepositoryProvider));
    });

class SharedFilesController extends StateNotifier<SharedFilesState> {
  final FilesRepository _repository;
  int _loadGeneration = 0;

  SharedFilesController(this._repository) : super(const SharedFilesState());

  Future<void> load() async {
    final generation = ++_loadGeneration;
    final existingFiles = state.files;
    state = SharedFilesState(isLoading: true, files: existingFiles);
    try {
      final files = await _repository.getSharedFiles();
      if (!mounted || generation != _loadGeneration) return;
      state = SharedFilesState(files: files);
    } on ServerError {
      if (!mounted || generation != _loadGeneration) return;
      state = SharedFilesState(
        files: existingFiles,
        error: 'Server error. Please try again.',
      );
    } on NetworkError {
      if (!mounted || generation != _loadGeneration) return;
      state = SharedFilesState(
        files: existingFiles,
        error: 'Network error. Please check your connection.',
      );
    } catch (_) {
      if (!mounted || generation != _loadGeneration) return;
      state = SharedFilesState(
        files: existingFiles,
        error: 'An error occurred. Please try again.',
      );
    }
  }

  Future<void> refresh() => load();
}
