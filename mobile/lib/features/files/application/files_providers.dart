import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/files/application/files_state.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:open_file/open_file.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'dart:io';

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
  static const String _fileNamePattern = r'^[a-zA-Z0-9\s\-_.]+$';
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

  Future<void> downloadFile(String fileId, String fileName) async {
    state = state.clearDownloadState(fileId);
    state = state.updateDownloadProgress(fileId, 0.0);

    try {
      final urlResponse = await _repository.getDownloadUrl(fileId: fileId);
      final filePath = await _downloadAndSaveFile(fileId, fileName, urlResponse.url);
      state = state.setDownloadedFilePath(fileId, filePath);
      state = state.updateDownloadProgress(fileId, 1.0);
    } on FileNotFoundError catch (e) {
      state = state.setDownloadError(fileId, 'File not found or you do not have permission');
    } on ServerError catch (e) {
      state = state.setDownloadError(fileId, 'File download failed. Please try again later.');
    } on NetworkError catch (e) {
      state = state.setDownloadError(fileId, 'Connection lost. Please check your network and try again.');
    } catch (e) {
      // Log the actual error for debugging
      print('Download error for $fileId: $e');
      state = state.setDownloadError(fileId, 'Download failed. Please try again.');
    }
  }

  Future<String> _downloadAndSaveFile(String fileId, String fileName, String url) async {
    try {
      final dio = Dio();
      final downloadsDir = await getDownloadsDirectory();
      if (downloadsDir == null) {
        throw Exception('Downloads directory not available');
      }

      print('Downloading $fileName to ${downloadsDir.path}');
      final filePath = '${downloadsDir.path}/$fileName';
      await dio.download(
        url,
        filePath,
        onReceiveProgress: (count, total) {
          if (total > 0) {
            state = state.updateDownloadProgress(fileId, count / total);
          }
        },
      );
      print('Download completed: $filePath');
      return filePath;
    } catch (e) {
      print('_downloadAndSaveFile error: $e');
      rethrow;
    }
  }

  Future<void> cancelDownload(String fileId) async {
    state = state.clearDownloadState(fileId);
  }

  Future<void> openDownloadedFile(String filePath) async {
    final result = await OpenFile.open(filePath);
    if (result.type != ResultType.done) {
      throw Exception('Failed to open file: ${result.message}');
    }
  }

  Future<void> selectAndUploadFile() async {
    final status = await Permission.storage.request();
    if (!status.isGranted) {
      throw Exception('Storage permission required to select files');
    }

    final result = await openFile(
      acceptedTypeGroups: <XTypeGroup>[
        XTypeGroup(
          label: 'All files',
          extensions: <String>['*'],
        ),
      ],
    );
    if (result == null) {
      return;
    }

    final filePath = result.path;
    final fileName = result.name;
    final fileSize = await result.length();

    final validationError = validateFileName(fileName);
    if (validationError != null) {
      throw Exception(validationError);
    }

    await uploadFile(filePath, fileName, fileSize.toInt());
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

      await _uploadToPresignedUrl(fileName, file, urlResponse.url);

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
    } on DuplicateFolderNameError catch (e) {
      state = state.setUploadError(fileName, 'File already exists');
    } on InvalidFolderNameError catch (e) {
      state = state.setUploadError(fileName, 'Invalid file name or size');
    } on FolderNotFoundError catch (e) {
      state = state.setUploadError(fileName, 'Folder not found');
    } on ServerError catch (e) {
      state = state.setUploadError(fileName, 'Upload failed. Please try again later.');
    } on NetworkError catch (e) {
      state = state.setUploadError(fileName, 'Connection lost. Please check your network and try again.');
    } catch (e) {
      print('Upload error for $fileName: $e');
      state = state.setUploadError(fileName, 'Upload failed. Please try again.');
    }
  }

  Future<String> _computeSha256(File file) async {
    final bytes = await file.readAsBytes();
    return sha256.convert(bytes).toString();
  }

  Future<void> _uploadToPresignedUrl(
    String fileName,
    File file,
    String url,
  ) async {
    try {
      final dio = Dio();
      await dio.put(
        url,
        data: file.openRead(),
        options: Options(
          contentType: 'application/octet-stream',
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
        throw NetworkError('Connection lost. Please check your network and try again.');
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
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'xls': 'application/vnd.ms-excel',
      'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'ppt': 'application/vnd.ms-powerpoint',
      'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
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
    if (mimeType.contains('spreadsheet') || mimeType.contains('excel')) return 'spreadsheet';
    if (mimeType.contains('zip') || mimeType.contains('rar') || mimeType.contains('7z')) {
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
      await _repository.createFolder(
        parentPath: currentPath,
        name: name,
      );
      await refresh();
      state = state.copyWith(isCreatingFolder: false, clearCreateError: true);
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
