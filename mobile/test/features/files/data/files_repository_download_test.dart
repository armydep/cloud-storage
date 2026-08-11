import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesRepository.getDownloadUrl', () {
    test('calls correct presign-download endpoint', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'download_url': 'https://minio:9000/bucket/sha256/abc123',
        'expires_in': 3600,
      };

      final repository = FilesRepository(mockApiClient);
      await repository.getDownloadUrl(fileId: 'file-123');

      expect(
        mockApiClient.lastPostPath,
        '/api/v1/files/file-123/presign-download',
      );
    });

    test('returns DownloadUrlResponse on success (200)', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'download_url': 'https://minio:9000/bucket/sha256/abc123',
        'expires_in': 3600,
      };

      final repository = FilesRepository(mockApiClient);
      final result = await repository.getDownloadUrl(fileId: 'file-123');

      expect(result.url, 'https://minio:9000/bucket/sha256/abc123');
      expect(result.expiresInSeconds, 3600);
    });

    test('throws FileNotFoundError on 404', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'File not found',
        statusCode: 404,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.getDownloadUrl(fileId: 'file-nonexistent'),
        throwsA(isA<FileNotFoundError>()),
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
        () => repository.getDownloadUrl(fileId: 'file-123'),
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
        () => repository.getDownloadUrl(fileId: 'file-123'),
        throwsA(isA<NetworkError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  Map<String, dynamic>? nextResponse;
  ApiException? nextException;
  String? lastPostPath;

  @override
  Future<void> delete(String path, {bool authenticated = false}) async {
    throw UnimplementedError();
  }

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
  Future<void> postEmpty(String path, {bool authenticated = false}) async {
    throw UnimplementedError();
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
