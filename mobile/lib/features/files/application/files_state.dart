import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/foundation.dart';

@immutable
class FilesState {
  final bool isLoading;
  final FolderWithContents? folder;
  final String? error;

  const FilesState({
    this.isLoading = false,
    this.folder,
    this.error,
  });

  const FilesState.loading() : this(isLoading: true);

  FilesState.loaded(FolderWithContents folder)
      : this(folder: folder, isLoading: false);

  FilesState.error(String error) : this(error: error, isLoading: false);

  bool get hasError => error != null;
  bool get isEmpty => !isLoading && folder != null && folder!.isEmpty;
}
