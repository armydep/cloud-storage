import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesRepository.presignUpload', () {
    test('calls correct presign-upload endpoint', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'upload_url': 'https://minio:9000/bucket/sha256/abc123',
        'method': 'PUT',
        'expires_in': 3600,
      };

      final repository = FilesRepository(mockApiClient);
      await repository.presignUpload(
        parentPath: 'root',
        fileName: 'document.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 102400,
      );

      expect(mockApiClient.lastPostPath, '/api/v1/files/presign-upload');
    });

    test('returns UploadUrlResponse on success (200)', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'upload_url': 'https://minio:9000/bucket/sha256/abc123',
        'method': 'PUT',
        'expires_in': 3600,
      };

      final repository = FilesRepository(mockApiClient);
      final result = await repository.presignUpload(
        parentPath: 'root',
        fileName: 'document.pdf',
        mimeType: 'application/pdf',
        sizeBytes: 102400,
      );

      expect(result.url, 'https://minio:9000/bucket/sha256/abc123');
      expect(result.method, 'PUT');
      expect(result.expiresInSeconds, 3600);
    });

    test('throws FolderNotFoundError on 404', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Folder not found',
        statusCode: 404,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.presignUpload(
          parentPath: 'nonexistent',
          fileName: 'document.pdf',
          mimeType: 'application/pdf',
          sizeBytes: 102400,
        ),
        throwsA(isA<FolderNotFoundError>()),
      );
    });

    test('throws InvalidFolderNameError on 422', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Invalid file name',
        statusCode: 422,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.presignUpload(
          parentPath: 'root',
          fileName: 'invalid/name',
          mimeType: 'application/pdf',
          sizeBytes: 102400,
        ),
        throwsA(isA<InvalidFolderNameError>()),
      );
    });

    test('throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Server error',
        statusCode: 500,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.presignUpload(
          parentPath: 'root',
          fileName: 'document.pdf',
          mimeType: 'application/pdf',
          sizeBytes: 102400,
        ),
        throwsA(isA<ServerError>()),
      );
    });

    test('throws NetworkError on network failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.presignUpload(
          parentPath: 'root',
          fileName: 'document.pdf',
          mimeType: 'application/pdf',
          sizeBytes: 102400,
        ),
        throwsA(isA<NetworkError>()),
      );
    });
  });

  group('FilesRepository.completeUpload', () {
    test('returns FileContent on success (201)', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'id': 'file-123',
        'name': 'document.pdf',
        'size_bytes': 102400,
        'mime_type': 'application/pdf',
        'path': '/document.pdf',
        'category': 'document',
      };

      final repository = FilesRepository(mockApiClient);
      final result = await repository.completeUpload(fileId: 'file-123');

      expect(result.name, 'document.pdf');
      expect(result.sizeBytes, 102400);
      expect(result.isFile, true);
    });

    test('throws FileNotFoundError on 404', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'File not found',
        statusCode: 404,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.completeUpload(fileId: 'nonexistent'),
        throwsA(isA<FileNotFoundError>()),
      );
    });

    test('throws DuplicateFolderNameError on 409', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'File already exists',
        statusCode: 409,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.completeUpload(fileId: 'file-123'),
        throwsA(isA<DuplicateFolderNameError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  Map<String, dynamic>? nextResponse;
  ApiException? nextException;
  String? lastPostPath;

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    bool authenticated = false,
    Map<String, String>? queryParameters,
  }) async {
    if (nextException != null) {
      throw nextException!;
    }
    return nextResponse ?? {};
  }

  @override
  Future<Map<String, dynamic>> postJson(
    String path, {
    bool authenticated = false,
    String? authenticationToken,
    Map<String, dynamic>? body,
  }) async {
    lastPostPath = path;
    if (nextException != null) {
      throw nextException!;
    }
    return nextResponse ?? {};
  }

  @override
  Future<Map<String, dynamic>> postForm(
    String path, {
    required Map<String, String> fields,
  }) async {
    throw UnimplementedError();
  }

  @override
  Uri resolve(String path, {Map<String, String>? queryParameters}) {
    throw UnimplementedError();
  }

  @override
  void close() {}
}
