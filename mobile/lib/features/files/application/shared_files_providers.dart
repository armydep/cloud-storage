import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/shared_files_state.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// autoDispose alone only clears this when the last listener goes away, which
// on sign-out depends on the router unmounting the shell route. Watching the
// identity makes the reset explicit and independent of navigation structure.
final sharedFilesControllerProvider =
    StateNotifierProvider.autoDispose<SharedFilesController, SharedFilesState>((
      ref,
    ) {
      ref.watch(currentUserIdProvider);
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
    } catch (error, stackTrace) {
      // Anything that is neither ServerError nor NetworkError lands here —
      // notably ApiError for 401/403, and TypeError/FormatException from
      // SharedFile.fromJson on a schema mismatch. The user-facing message
      // stays generic, but swallowing the cause left a retry loop with no
      // diagnostics. Matches the logging in FilesController.downloadFile.
      debugPrint('Shared files load failed: $error\n$stackTrace');
      if (!mounted || generation != _loadGeneration) return;
      state = SharedFilesState(
        files: existingFiles,
        error: 'An error occurred. Please try again.',
      );
    }
  }

  Future<void> refresh() => load();
}
