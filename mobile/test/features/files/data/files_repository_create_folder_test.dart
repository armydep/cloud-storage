import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesRepository.createFolder', () {
    test('createFolder returns FileContent on success (201)', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'id': 'folder-123',
        'name': 'New Folder',
        'type': 'folder',
        'path': 'root.NewFolder',
        'size_bytes': null,
        'category': null,
        'mime_type': null,
      };

      final repository = FilesRepository(mockApiClient);
      final result = await repository.createFolder(
        parentPath: 'root',
        name: 'New Folder',
      );

      expect(result.id, 'folder-123');
      expect(result.name, 'New Folder');
      expect(result.isFolder, true);
      expect(mockApiClient.lastRequestBody?['parent_path'], 'root');
      expect(mockApiClient.lastRequestBody?['name'], 'New Folder');
    });

    test('createFolder throws DuplicateFolderNameError on 409', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Folder already exists',
        statusCode: 409,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.createFolder(parentPath: 'root', name: 'Existing'),
        throwsA(isA<DuplicateFolderNameError>()),
      );
    });

    test('createFolder throws InvalidFolderNameError on 422', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Invalid folder name',
        statusCode: 422,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.createFolder(parentPath: 'root', name: 'Invalid\0Name'),
        throwsA(isA<InvalidFolderNameError>()),
      );
    });

    test('createFolder throws FolderNotFoundError on 404', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Parent folder not found',
        statusCode: 404,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.createFolder(parentPath: 'root.NonExistent', name: 'New'),
        throwsA(isA<FolderNotFoundError>()),
      );
    });

    test('createFolder throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = ApiException(
        message: 'Server error',
        statusCode: 500,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.createFolder(parentPath: 'root', name: 'New'),
        throwsA(isA<ServerError>()),
      );
    });

    test('createFolder throws NetworkError on network failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );

      final repository = FilesRepository(mockApiClient);
      expect(
        () => repository.createFolder(parentPath: 'root', name: 'New'),
        throwsA(isA<NetworkError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  Map<String, dynamic>? nextResponse;
  ApiException? nextException;
  Map<String, dynamic>? lastRequestBody;

  @override
  Future<void> delete(
    String path, {
    bool authenticated = false,
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
    lastRequestBody = body;
    if (nextException != null) {
      throw nextException!;
    }
    return nextResponse ?? {};
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
  Uri resolve(String path, {Map<String, String>? queryParameters}) {
    throw UnimplementedError();
  }

  @override
  void close() {}
}
