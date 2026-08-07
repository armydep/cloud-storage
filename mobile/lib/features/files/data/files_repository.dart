import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';

class FilesRepository {
  final ApiClient apiClient;

  FilesRepository(this.apiClient);

  Future<FolderWithContents> getFolder({required String path}) async {
    try {
      final json = await apiClient.getJson(
        '/api/v1/files',
        authenticated: true,
        queryParameters: {'path': path},
      );

      return FolderWithContents.fromJson(json);
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw FolderNotFoundError('Folder not found');
      } else if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('Server error. Please try again.');
      } else if (e.isNetworkError) {
        throw NetworkError('Network error. Please check your connection.');
      } else {
        throw ApiError(e.message);
      }
    }
  }

  Future<FileContent> createFolder({
    required String parentPath,
    required String name,
  }) async {
    try {
      final json = await apiClient.postJson(
        '/api/v1/files/folders',
        authenticated: true,
        body: {
          'parent_path': parentPath,
          'name': name,
        },
      );

      return FileContent.fromJson({...json, 'type': 'folder'});
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw FolderNotFoundError('Parent folder not found');
      } else if (e.statusCode == 409) {
        throw DuplicateFolderNameError('Folder already exists');
      } else if (e.statusCode == 422) {
        throw InvalidFolderNameError('Invalid folder name');
      } else if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('Server error. Please try again.');
      } else if (e.isNetworkError) {
        throw NetworkError('Connection lost. Please check your network and try again.');
      } else {
        throw ApiError(e.message);
      }
    }
  }

  Future<DownloadUrlResponse> getDownloadUrl({required String fileId}) async {
    try {
      final json = await apiClient.postJson(
        '/api/v1/files/$fileId/presign-download',
        authenticated: true,
      );

      return DownloadUrlResponse.fromJson(json);
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw FileNotFoundError('File not found or you do not have permission');
      } else if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('File download failed. Please try again later.');
      } else if (e.isNetworkError) {
        throw NetworkError('Connection lost. Please check your network and try again.');
      } else {
        throw ApiError(e.message);
      }
    }
  }

  Future<UploadUrlResponse> presignUpload({
    required String folderPath,
    required String name,
    required String blobHash,
    required String mimeType,
    required String category,
    required int sizeBytes,
  }) async {
    try {
      final json = await apiClient.postJson(
        '/api/v1/files/presign-upload',
        authenticated: true,
        body: {
          'folder_path': folderPath,
          'name': name,
          'blob_hash': blobHash,
          'mime_type': mimeType,
          'category': category,
          'size_bytes': sizeBytes,
        },
      );

      return UploadUrlResponse.fromJson(json);
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw FolderNotFoundError('Parent folder not found');
      } else if (e.statusCode == 409) {
        throw DuplicateFolderNameError('File already exists');
      } else if (e.statusCode == 422) {
        throw InvalidFolderNameError('Invalid file name or size');
      } else if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('Upload failed. Please try again later.');
      } else if (e.isNetworkError) {
        throw NetworkError('Connection lost. Please check your network and try again.');
      } else {
        throw ApiError(e.message);
      }
    }
  }

  Future<FileContent> completeUpload({
    required String folderPath,
    required String name,
    required String blobHash,
    required String mimeType,
    required String category,
    required int sizeBytes,
  }) async {
    try {
      final json = await apiClient.postJson(
        '/api/v1/files/complete-upload',
        authenticated: true,
        body: {
          'folder_path': folderPath,
          'name': name,
          'blob_hash': blobHash,
          'mime_type': mimeType,
          'category': category,
          'size_bytes': sizeBytes,
        },
      );

      return FileContent.fromJson({...json, 'type': 'file'});
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        throw FolderNotFoundError('Parent folder not found');
      } else if (e.statusCode == 409) {
        throw DuplicateFolderNameError('File already exists');
      } else if (e.statusCode == 422) {
        throw InvalidFolderNameError('Invalid file');
      } else if (e.statusCode != null && e.statusCode! >= 500) {
        throw ServerError('Upload completion failed. Please try again later.');
      } else if (e.isNetworkError) {
        throw NetworkError('Connection lost. Please check your network and try again.');
      } else {
        throw ApiError(e.message);
      }
    }
  }
}

class FolderNotFoundError implements Exception {
  final String message;
  FolderNotFoundError(this.message);

  @override
  String toString() => message;
}

class ApiError implements Exception {
  final String message;
  ApiError(this.message);

  @override
  String toString() => message;
}

class ServerError implements Exception {
  final String message;
  ServerError(this.message);

  @override
  String toString() => message;
}

class NetworkError implements Exception {
  final String message;
  NetworkError(this.message);

  @override
  String toString() => message;
}

class DuplicateFolderNameError implements Exception {
  final String message;
  DuplicateFolderNameError(this.message);

  @override
  String toString() => message;
}

class InvalidFolderNameError implements Exception {
  final String message;
  InvalidFolderNameError(this.message);

  @override
  String toString() => message;
}

class FileNotFoundError implements Exception {
  final String message;
  FileNotFoundError(this.message);

  @override
  String toString() => message;
}

class DownloadUrlResponse {
  final String url;
  final int expiresInSeconds;

  DownloadUrlResponse({
    required this.url,
    required this.expiresInSeconds,
  });

  factory DownloadUrlResponse.fromJson(Map<String, dynamic> json) {
    return DownloadUrlResponse(
      url: json['download_url'] as String,
      expiresInSeconds: json['expires_in'] as int? ?? 3600,
    );
  }
}

class UploadUrlResponse {
  final String url;
  final String method;
  final int expiresInSeconds;

  UploadUrlResponse({
    required this.url,
    required this.method,
    required this.expiresInSeconds,
  });

  factory UploadUrlResponse.fromJson(Map<String, dynamic> json) {
    return UploadUrlResponse(
      url: json['upload_url'] as String,
      method: json['method'] as String? ?? 'PUT',
      expiresInSeconds: json['expires_in'] as int? ?? 3600,
    );
  }
}
