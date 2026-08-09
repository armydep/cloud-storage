import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesRepository.deleteFile', () {
    test('calls expected authenticated delete endpoint', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      await repository.deleteFile(fileId: 'file-123');

      expect(mockApiClient.lastDeletePath, '/api/v1/files/file-123');
      expect(mockApiClient.lastDeleteAuthenticated, isTrue);
    });

    test('completes successfully on 204', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      await expectLater(
        repository.deleteFile(fileId: 'file-123'),
        completes,
      );
    });

    test('throws FileNotFoundError on 404', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'File not found',
        statusCode: 404,
      );

      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.deleteFile(fileId: 'missing-file'),
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
        () => repository.deleteFile(fileId: 'file-123'),
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
        () => repository.deleteFile(fileId: 'file-123'),
        throwsA(isA<NetworkError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  ApiException? nextException;
  String? lastDeletePath;
  bool? lastDeleteAuthenticated;

  @override
  Future<void> delete(
    String path, {
    bool authenticated = false,
  }) async {
    lastDeletePath = path;
    lastDeleteAuthenticated = authenticated;
    if (nextException != null) {
      throw nextException!;
    }
  }

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    bool authenticated = false,
    Map<String, String>? queryParameters,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> postForm(
    String path, {
    required Map<String, String> fields,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> postJson(
    String path, {
    bool authenticated = false,
    String? authenticationToken,
    Map<String, dynamic>? body,
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
