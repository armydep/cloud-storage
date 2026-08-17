import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/foundation.dart';

@immutable
class FilesState {
  final bool isLoading;
  final FolderWithContents? folder;
  final String? error;
  final bool isCreatingFolder;
  final String? createError;
  final bool isSharing;
  final String? shareError;
  final List<FileShare> shares;
  final bool isLoadingShares;
  final String? sharesError;
  final Set<String> revokingShares;
  final Map<String, String?> revokeShareError;
  final Map<String, double> downloadProgress;
  final Map<String, String?> downloadError;
  final Set<String> completedDownloads;
  final Map<String, String> downloadedFilePaths;
  final Map<String, double> uploadProgress;
  final Map<String, String?> uploadError;
  final Set<String> completedUploads;
  final Set<String> deletingFiles;
  final Map<String, String?> deleteError;

  const FilesState({
    this.isLoading = false,
    this.folder,
    this.error,
    this.isCreatingFolder = false,
    this.createError,
    this.isSharing = false,
    this.shareError,
    this.shares = const [],
    this.isLoadingShares = false,
    this.sharesError,
    this.revokingShares = const {},
    this.revokeShareError = const {},
    this.downloadProgress = const {},
    this.downloadError = const {},
    this.completedDownloads = const {},
    this.downloadedFilePaths = const {},
    this.uploadProgress = const {},
    this.uploadError = const {},
    this.completedUploads = const {},
    this.deletingFiles = const {},
    this.deleteError = const {},
  });

  const FilesState.loading() : this(isLoading: true);

  const FilesState.loaded(FolderWithContents folder)
    : this(folder: folder, isLoading: false);

  const FilesState.error(String error) : this(error: error, isLoading: false);

  bool get hasError => error != null;
  bool get isEmpty => !isLoading && folder != null && folder!.isEmpty;

  double? getDownloadProgress(String fileId) => downloadProgress[fileId];
  String? getDownloadError(String fileId) => downloadError[fileId];
  String? getDownloadedFilePath(String fileId) => downloadedFilePaths[fileId];
  bool isDownloading(String fileId) => downloadProgress.containsKey(fileId);
  bool isDownloadComplete(String fileId) => completedDownloads.contains(fileId);

  double? getUploadProgress(String fileName) => uploadProgress[fileName];
  String? getUploadError(String fileName) => uploadError[fileName];
  bool isUploading(String fileName) => uploadProgress.containsKey(fileName);
  bool isUploadComplete(String fileName) => completedUploads.contains(fileName);
  bool isDeleting(String fileId) => deletingFiles.contains(fileId);
  String? getDeleteError(String fileId) => deleteError[fileId];

  bool isRevokingShare(String shareId) => revokingShares.contains(shareId);
  String? getRevokeShareError(String shareId) => revokeShareError[shareId];

  FilesState copyWith({
    bool? isLoading,
    FolderWithContents? folder,
    bool clearFolder = false,
    String? error,
    bool clearError = false,
    bool? isCreatingFolder,
    String? createError,
    bool clearCreateError = false,
    bool? isSharing,
    String? shareError,
    bool clearShareError = false,
    List<FileShare>? shares,
    bool? isLoadingShares,
    String? sharesError,
    bool clearSharesError = false,
    Set<String>? revokingShares,
    Map<String, String?>? revokeShareError,
    Map<String, double>? downloadProgress,
    Map<String, String?>? downloadError,
    Set<String>? completedDownloads,
    Map<String, String>? downloadedFilePaths,
    Map<String, double>? uploadProgress,
    Map<String, String?>? uploadError,
    Set<String>? completedUploads,
    Set<String>? deletingFiles,
    Map<String, String?>? deleteError,
  }) {
    return FilesState(
      isLoading: isLoading ?? this.isLoading,
      folder: clearFolder ? null : (folder ?? this.folder),
      error: clearError ? null : (error ?? this.error),
      isCreatingFolder: isCreatingFolder ?? this.isCreatingFolder,
      createError: clearCreateError ? null : (createError ?? this.createError),
      isSharing: isSharing ?? this.isSharing,
      shareError: clearShareError ? null : (shareError ?? this.shareError),
      shares: shares ?? this.shares,
      isLoadingShares: isLoadingShares ?? this.isLoadingShares,
      sharesError: clearSharesError ? null : (sharesError ?? this.sharesError),
      revokingShares: revokingShares ?? this.revokingShares,
      revokeShareError: revokeShareError ?? this.revokeShareError,
      downloadProgress: downloadProgress ?? this.downloadProgress,
      downloadError: downloadError ?? this.downloadError,
      completedDownloads: completedDownloads ?? this.completedDownloads,
      downloadedFilePaths: downloadedFilePaths ?? this.downloadedFilePaths,
      uploadProgress: uploadProgress ?? this.uploadProgress,
      uploadError: uploadError ?? this.uploadError,
      completedUploads: completedUploads ?? this.completedUploads,
      deletingFiles: deletingFiles ?? this.deletingFiles,
      deleteError: deleteError ?? this.deleteError,
    );
  }

  FilesState updateDownloadProgress(String fileId, double progress) {
    final newProgress = Map<String, double>.from(downloadProgress);
    if (progress >= 1.0) {
      newProgress.remove(fileId);
      final newCompleted = Set<String>.from(completedDownloads);
      newCompleted.add(fileId);
      return copyWith(
        downloadProgress: newProgress,
        completedDownloads: newCompleted,
      );
    } else {
      newProgress[fileId] = progress;
      return copyWith(downloadProgress: newProgress);
    }
  }

  FilesState setDownloadError(String fileId, String? error) {
    final newError = Map<String, String?>.from(downloadError);
    if (error == null) {
      newError.remove(fileId);
    } else {
      newError[fileId] = error;
    }
    final newProgress = Map<String, double>.from(downloadProgress);
    newProgress.remove(fileId);
    return copyWith(downloadProgress: newProgress, downloadError: newError);
  }

  FilesState clearDownloadState(String fileId) {
    final newProgress = Map<String, double>.from(downloadProgress);
    newProgress.remove(fileId);
    final newError = Map<String, String?>.from(downloadError);
    newError.remove(fileId);
    final newPaths = Map<String, String>.from(downloadedFilePaths);
    newPaths.remove(fileId);
    return copyWith(
      downloadProgress: newProgress,
      downloadError: newError,
      downloadedFilePaths: newPaths,
    );
  }

  FilesState setDownloadedFilePath(String fileId, String filePath) {
    final newPaths = Map<String, String>.from(downloadedFilePaths);
    newPaths[fileId] = filePath;
    return copyWith(downloadedFilePaths: newPaths);
  }

  FilesState updateUploadProgress(String fileName, double progress) {
    final newProgress = Map<String, double>.from(uploadProgress);
    if (progress >= 1.0) {
      newProgress.remove(fileName);
      final newCompleted = Set<String>.from(completedUploads);
      newCompleted.add(fileName);
      return copyWith(
        uploadProgress: newProgress,
        completedUploads: newCompleted,
      );
    } else {
      newProgress[fileName] = progress;
      return copyWith(uploadProgress: newProgress);
    }
  }

  FilesState setUploadError(String fileName, String? error) {
    final newError = Map<String, String?>.from(uploadError);
    if (error == null) {
      newError.remove(fileName);
    } else {
      newError[fileName] = error;
    }
    final newProgress = Map<String, double>.from(uploadProgress);
    newProgress.remove(fileName);
    return copyWith(uploadProgress: newProgress, uploadError: newError);
  }

  FilesState clearUploadState(String fileName) {
    final newProgress = Map<String, double>.from(uploadProgress);
    newProgress.remove(fileName);
    final newError = Map<String, String?>.from(uploadError);
    newError.remove(fileName);
    return copyWith(uploadProgress: newProgress, uploadError: newError);
  }

  FilesState startDeleting(String fileId) {
    final newDeleting = Set<String>.from(deletingFiles)..add(fileId);
    final newError = Map<String, String?>.from(deleteError)..remove(fileId);
    return copyWith(deletingFiles: newDeleting, deleteError: newError);
  }

  FilesState finishDeleting(String fileId) {
    final newDeleting = Set<String>.from(deletingFiles)..remove(fileId);
    final newError = Map<String, String?>.from(deleteError)..remove(fileId);
    return copyWith(deletingFiles: newDeleting, deleteError: newError);
  }

  FilesState setDeleteError(String fileId, String error) {
    final newDeleting = Set<String>.from(deletingFiles)..remove(fileId);
    final newError = Map<String, String?>.from(deleteError);
    newError[fileId] = error;
    return copyWith(deletingFiles: newDeleting, deleteError: newError);
  }

  FilesState startRevokingShare(String shareId) {
    final newRevoking = Set<String>.from(revokingShares)..add(shareId);
    final newError = Map<String, String?>.from(revokeShareError)
      ..remove(shareId);
    return copyWith(revokingShares: newRevoking, revokeShareError: newError);
  }

  FilesState finishRevokingShare(String shareId) {
    final newRevoking = Set<String>.from(revokingShares)..remove(shareId);
    final newError = Map<String, String?>.from(revokeShareError)
      ..remove(shareId);
    return copyWith(revokingShares: newRevoking, revokeShareError: newError);
  }

  FilesState setRevokeShareError(String shareId, String error) {
    final newRevoking = Set<String>.from(revokingShares)..remove(shareId);
    final newError = Map<String, String?>.from(revokeShareError);
    newError[shareId] = error;
    return copyWith(revokingShares: newRevoking, revokeShareError: newError);
  }
}
