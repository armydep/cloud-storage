import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/foundation.dart';

@immutable
class SharedFilesState {
  final bool isLoading;
  final List<SharedFile> files;
  final String? error;

  const SharedFilesState({
    this.isLoading = false,
    this.files = const [],
    this.error,
  });

  bool get isEmpty => !isLoading && error == null && files.isEmpty;
}
