import 'dart:io';

import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_state.dart';
import 'package:cloudestorage/features/files/data/file_transfer_service.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';

final filesRepositoryProvider = Provider<FilesRepository>((ref) {
  return FilesRepository(ref.watch(apiClientProvider));
});

final fileTransferServiceProvider = Provider<FileTransferService>((ref) {
  return FileTransferService();
});

// Every provider below watches `currentUserIdProvider` so its state is rebuilt
// when the signed-in identity changes. These are not autoDispose and would
// otherwise survive a sign-out, letting the next account briefly render the
// previous one's folder and file names before the first response arrives.
final currentFolderPathProvider = StateProvider<String>((ref) {
  ref.watch(currentUserIdProvider);
  return 'root';
});

final folderContentsProvider =
    FutureProvider.family<FolderWithContents, String>((ref, path) async {
      ref.watch(currentUserIdProvider);
      final repository = ref.watch(filesRepositoryProvider);
      return repository.getFolder(path: path);
    });

final currentFolderContentsProvider = FutureProvider<FolderWithContents>((ref) {
  final currentPath = ref.watch(currentFolderPathProvider);
  return ref.watch(folderContentsProvider(currentPath).future);
});

final filesControllerProvider =
    StateNotifierProvider<FilesController, FilesState>((ref) {
      ref.watch(currentUserIdProvider);
      return FilesController(
        ref.watch(filesRepositoryProvider),
        ref.watch(fileTransferServiceProvider),
        ref,
      );
    });

class FilesController extends StateNotifier<FilesState> {
  final FilesRepository _repository;
  final FileTransferService _fileTransferService;
  final Ref _ref;
  final List<String> _navigationStack = ['root'];

  static const String _folderNamePattern = r'^[a-zA-Z0-9\s\-_]+$';
  static const String _fileNamePattern = r'^[a-zA-Z0-9\s\-_.]+$';
  static const int _maxFolderNameLength = 255;

  FilesController(this._repository, this._fileTransferService, this._ref)
    : super(const FilesState());

  Future<void> loadFolder(String path) async {
    final currentPath = _ref.read(currentFolderPathProvider);
    state = state.copyWith(
      isLoading: true,
      clearError: true,
      clearFolder: currentPath != path,
    );
    _ref.read(currentFolderPathProvider.notifier).state = path;

    try {
      final folder = await _repository.getFolder(path: path);
      state = state.copyWith(
        isLoading: false,
        folder: folder,
        clearError: true,
      );
    } on FolderNotFoundError {
      state = state.copyWith(isLoading: false, error: 'Folder not found');
    } on ServerError {
      state = state.copyWith(
        isLoading: false,
        error: 'Server error. Please try again.',
      );
    } on NetworkError {
      state = state.copyWith(
        isLoading: false,
        error: 'Network error. Please check your connection.',
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'An error occurred. Please try again.',
      );
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

  Future<void> downloadFile(String fileId, String fileName) async {
    state = state.clearDownloadState(fileId);
    state = state.updateDownloadProgress(fileId, 0.0);

    try {
      final urlResponse = await _repository.getDownloadUrl(fileId: fileId);
      final filePath = await _fileTransferService.download(
        fileId: fileId,
        url: urlResponse.url,
        fileName: fileName,
        onProgress: (progress) {
          if (mounted) {
            state = state.updateDownloadProgress(fileId, progress);
          }
        },
      );
      state = state.setDownloadedFilePath(fileId, filePath);
      state = state.updateDownloadProgress(fileId, 1.0);
    } on FileNotFoundError {
      state = state.setDownloadError(
        fileId,
        'File not found or you do not have permission',
      );
    } on ServerError {
      state = state.setDownloadError(
        fileId,
        'File download failed. Please try again later.',
      );
    } on NetworkError {
      state = state.setDownloadError(
        fileId,
        'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      // Log the actual error for debugging
      debugPrint('Download error for $fileId: $e');
      state = state.setDownloadError(
        fileId,
        'Download failed. Please try again.',
      );
    }
  }

  Future<void> cancelDownload(String fileId) async {
    state = state.clearDownloadState(fileId);
  }

  Future<void> openDownloadedFile(String filePath) async {
    await _fileTransferService.open(filePath);
  }

  Future<void> selectAndUploadFile() async {
    debugPrint('selectAndUploadFile: Starting file selection');

    final status = await Permission.storage.request();
    debugPrint('selectAndUploadFile: Storage permission status = $status');
    if (!status.isGranted) {
      throw Exception('Storage permission required to select files');
    }

    debugPrint('selectAndUploadFile: Opening file picker');
    final result = await openFile(
      acceptedTypeGroups: <XTypeGroup>[
        XTypeGroup(label: 'All files', extensions: <String>['*']),
      ],
    );
    debugPrint('selectAndUploadFile: File picker result = $result');
    if (result == null) {
      debugPrint('selectAndUploadFile: User cancelled file selection');
      return;
    }

    final filePath = result.path;
    final fileName = result.name;
    final fileSize = await result.length();
    debugPrint(
      'selectAndUploadFile: Selected file - name=$fileName, '
      'path=$filePath, size=$fileSize',
    );

    final validationError = validateFileName(fileName);
    if (validationError != null) {
      debugPrint('selectAndUploadFile: Validation error = $validationError');
      throw Exception(validationError);
    }

    debugPrint('selectAndUploadFile: Starting upload');
    await uploadFile(filePath, fileName, fileSize.toInt());
    debugPrint('selectAndUploadFile: Upload completed');
  }

  Future<void> uploadFile(
    String filePath,
    String fileName,
    int fileSize,
  ) async {
    state = state.clearUploadState(fileName);
    state = state.updateUploadProgress(fileName, 0.0);

    try {
      final file = File(filePath);
      final blobHash = await _computeSha256(file);
      final mimeType = _getMimeType(fileName);
      final category = _getCategory(mimeType);

      final currentPath = _ref.read(currentFolderPathProvider);
      final urlResponse = await _repository.presignUpload(
        folderPath: currentPath,
        name: fileName,
        blobHash: blobHash,
        mimeType: mimeType,
        category: category,
        sizeBytes: fileSize,
      );

      if (urlResponse.uploadRequired) {
        final uploadUrl = urlResponse.url;
        if (uploadUrl == null || uploadUrl.isEmpty) {
          throw ApiError('Upload URL was not provided');
        }
        await _uploadToPresignedUrl(
          fileName,
          file,
          mimeType,
          uploadUrl,
          urlResponse.headers,
        );
      }

      await _repository.completeUpload(
        folderPath: currentPath,
        name: fileName,
        blobHash: blobHash,
        mimeType: mimeType,
        category: category,
        sizeBytes: fileSize,
      );

      await refresh();
      state = state.updateUploadProgress(fileName, 1.0);
    } on DuplicateFolderNameError {
      state = state.setUploadError(fileName, 'File already exists');
    } on InvalidFolderNameError {
      state = state.setUploadError(fileName, 'Invalid file name or size');
    } on FolderNotFoundError {
      state = state.setUploadError(fileName, 'Folder not found');
    } on ServerError {
      state = state.setUploadError(
        fileName,
        'Upload failed. Please try again later.',
      );
    } on NetworkError {
      state = state.setUploadError(
        fileName,
        'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      debugPrint('Upload error for $fileName: $e');
      state = state.setUploadError(
        fileName,
        'Upload failed. Please try again.',
      );
    }
  }

  Future<String> _computeSha256(File file) async {
    final bytes = await file.readAsBytes();
    return sha256.convert(bytes).toString();
  }

  Future<void> _uploadToPresignedUrl(
    String fileName,
    File file,
    String mimeType,
    String url,
    Map<String, String> headers,
  ) async {
    try {
      final dio = Dio();
      final fileBytes = await file.readAsBytes();
      await dio.put(
        url,
        data: fileBytes,
        options: Options(
          contentType: headers['Content-Type'] ?? mimeType,
          headers: headers,
        ),
        onSendProgress: (count, total) {
          if (total > 0) {
            state = state.updateUploadProgress(fileName, count / total);
          }
        },
      );
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.unknown) {
        throw NetworkError(
          'Connection lost. Please check your network and try again.',
        );
      }
      rethrow;
    }
  }

  String _getMimeType(String fileName) {
    final ext = fileName.split('.').last.toLowerCase();
    const mimeTypes = {
      'pdf': 'application/pdf',
      'txt': 'text/plain',
      'doc': 'application/msword',
      'docx':
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'xls': 'application/vnd.ms-excel',
      'xlsx':
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'ppt': 'application/vnd.ms-powerpoint',
      'pptx':
          'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'webp': 'image/webp',
      'mp3': 'audio/mpeg',
      'wav': 'audio/wav',
      'mp4': 'video/mp4',
      'webm': 'video/webm',
      'zip': 'application/zip',
      'rar': 'application/x-rar-compressed',
      '7z': 'application/x-7z-compressed',
    };
    return mimeTypes[ext] ?? 'application/octet-stream';
  }

  String _getCategory(String mimeType) {
    if (mimeType.startsWith('image/')) return 'image';
    if (mimeType.startsWith('video/')) return 'video';
    if (mimeType.startsWith('audio/')) return 'audio';
    if (mimeType.contains('spreadsheet') || mimeType.contains('excel')) {
      return 'spreadsheet';
    }
    if (mimeType.contains('zip') ||
        mimeType.contains('rar') ||
        mimeType.contains('7z')) {
      return 'archive';
    }
    return 'document';
  }

  Future<void> cancelUpload(String fileName) async {
    state = state.clearUploadState(fileName);
  }

  String? validateFileName(String name) {
    if (name.isEmpty) {
      return 'File name cannot be empty';
    }
    if (name.length > 255) {
      return 'File name cannot exceed 255 characters';
    }
    if (!RegExp(_fileNamePattern).hasMatch(name)) {
      return 'File name can only contain letters, numbers, spaces, dashes, underscores, and dots';
    }
    return null;
  }

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

    state = state.copyWith(isCreatingFolder: true, clearCreateError: true);

    try {
      final currentPath = _ref.read(currentFolderPathProvider);
      await _repository.createFolder(parentPath: currentPath, name: name);
      await refresh();
      state = state.copyWith(isCreatingFolder: false, clearCreateError: true);
    } on DuplicateFolderNameError {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Folder already exists',
      );
    } on InvalidFolderNameError {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Invalid folder name',
      );
    } on FolderNotFoundError {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Parent folder not found',
      );
    } on ServerError {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'Server error. Please try again.',
      );
    } on NetworkError {
      state = state.copyWith(
        isCreatingFolder: false,
        createError:
            'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      state = state.copyWith(
        isCreatingFolder: false,
        createError: 'An error occurred. Please try again.',
      );
    }
  }

  Future<void> shareFile({
    required String fileId,
    required String recipientEmail,
  }) async {
    state = state.copyWith(isSharing: true, clearShareError: true);

    try {
      await _repository.createFileShare(
        fileId: fileId,
        recipientEmail: recipientEmail,
      );
      state = state.copyWith(isSharing: false, clearShareError: true);
    } on FileNotFoundError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'File not found or you do not have permission',
      );
    } on ShareRecipientNotFoundError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'No account exists for that email address.',
      );
    } on ShareRecipientInactiveError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'That user account is inactive.',
      );
    } on CannotShareWithOwnerError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'You cannot share a file with yourself.',
      );
    } on DuplicateFileShareError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'This file is already shared with that user.',
      );
    } on ServerError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'File sharing failed. Please try again later.',
      );
    } on NetworkError {
      state = state.copyWith(
        isSharing: false,
        shareError: 'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      debugPrint('Share error for $fileId: $e');
      state = state.copyWith(
        isSharing: false,
        shareError: 'File sharing failed. Please try again.',
      );
    }
  }

  Future<void> loadFileShares(String fileId) async {
    state = state.copyWith(isLoadingShares: true, clearSharesError: true);

    try {
      final shares = await _repository.getFileShares(fileId: fileId);
      state = state.copyWith(
        shares: shares,
        isLoadingShares: false,
        clearSharesError: true,
      );
    } on FileNotFoundError {
      state = state.copyWith(
        isLoadingShares: false,
        sharesError: 'File not found or you do not have permission',
      );
    } on ServerError {
      state = state.copyWith(
        isLoadingShares: false,
        sharesError: 'Recipients could not be loaded.',
      );
    } on NetworkError {
      state = state.copyWith(
        isLoadingShares: false,
        sharesError:
            'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      debugPrint('Load shares error for $fileId: $e');
      state = state.copyWith(
        isLoadingShares: false,
        sharesError: 'Recipients could not be loaded.',
      );
    }
  }

  Future<void> revokeFileShare({
    required String fileId,
    required String shareId,
  }) async {
    state = state.startRevokingShare(shareId);

    try {
      await _repository.revokeFileShare(fileId: fileId, shareId: shareId);
      final remaining = state.shares
          .where((share) => share.id != shareId)
          .toList();
      state = state.copyWith(shares: remaining).finishRevokingShare(shareId);
    } on FileShareNotFoundError catch (e) {
      state = state.setRevokeShareError(shareId, e.message);
    } on FileNotFoundError catch (e) {
      state = state.setRevokeShareError(shareId, e.message);
    } on ServerError catch (e) {
      state = state.setRevokeShareError(shareId, e.message);
    } on NetworkError catch (e) {
      state = state.setRevokeShareError(shareId, e.message);
    } catch (e) {
      debugPrint('Revoke share error for $shareId: $e');
      state = state.setRevokeShareError(
        shareId,
        'Access could not be revoked. Try again.',
      );
    }
  }

  Future<bool> deleteFile(String fileId) async {
    if (state.isDeleting(fileId)) {
      return false;
    }

    state = state.clearDownloadState(fileId).startDeleting(fileId);

    try {
      await _repository.deleteFile(fileId: fileId);
      await refresh();
      state = state.finishDeleting(fileId);
      return true;
    } on FileNotFoundError {
      state = state.setDeleteError(
        fileId,
        'File not found or you do not have permission',
      );
    } on ServerError {
      state = state.setDeleteError(
        fileId,
        'File delete failed. Please try again later.',
      );
    } on NetworkError {
      state = state.setDeleteError(
        fileId,
        'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      state = state.setDeleteError(fileId, 'Delete failed. Please try again.');
    }

    return false;
  }

  Future<bool> deleteFolder(String folderId) async {
    if (state.isDeleting(folderId)) {
      return false;
    }

    state = state.startDeleting(folderId);

    try {
      await _repository.deleteFolder(folderId: folderId);
      await refresh();
      state = state.finishDeleting(folderId);
      return true;
    } on FolderNotFoundError {
      state = state.setDeleteError(
        folderId,
        'Folder not found or you do not have permission',
      );
    } on ServerError {
      state = state.setDeleteError(
        folderId,
        'Folder delete failed. Please try again later.',
      );
    } on NetworkError {
      state = state.setDeleteError(
        folderId,
        'Connection lost. Please check your network and try again.',
      );
    } catch (e) {
      state = state.setDeleteError(
        folderId,
        'Delete failed. Please try again.',
      );
    }

    return false;
  }
}
