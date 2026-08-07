import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/foundation.dart';

@immutable
class FilesState {
  final bool isLoading;
  final FolderWithContents? folder;
  final String? error;
  final bool isCreatingFolder;
  final String? createError;

  const FilesState({
    this.isLoading = false,
    this.folder,
    this.error,
    this.isCreatingFolder = false,
    this.createError,
  });

  const FilesState.loading() : this(isLoading: true);

  FilesState.loaded(FolderWithContents folder)
      : this(folder: folder, isLoading: false);

  FilesState.error(String error) : this(error: error, isLoading: false);

  bool get hasError => error != null;
  bool get isEmpty => !isLoading && folder != null && folder!.isEmpty;

  FilesState copyWith({
    bool? isLoading,
    FolderWithContents? folder,
    String? error,
    bool? isCreatingFolder,
    String? createError,
  }) {
    return FilesState(
      isLoading: isLoading ?? this.isLoading,
      folder: folder ?? this.folder,
      error: error ?? this.error,
      isCreatingFolder: isCreatingFolder ?? this.isCreatingFolder,
      createError: createError ?? this.createError,
    );
  }
}
