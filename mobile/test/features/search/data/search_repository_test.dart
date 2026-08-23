import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show ApiError, NetworkError, ServerError;
import 'package:cloudestorage/features/search/data/search_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SearchRepository.searchFiles', () {
    test('calls /api/v1/search/files with folder_path and limit only by '
        'default', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {'results': [], 'next_cursor': null};

      final repository = SearchRepository(mockApiClient);
      await repository.searchFiles(folderPath: 'root.docs');

      expect(mockApiClient.lastGetPath, '/api/v1/search/files');
      expect(mockApiClient.lastQueryParameters, {
        'folder_path': 'root.docs',
        'limit': '25',
      });
    });

    test('includes q, category and cursor only when provided', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {'results': [], 'next_cursor': null};

      final repository = SearchRepository(mockApiClient);
      await repository.searchFiles(
        folderPath: 'root.docs',
        query: 'report',
        category: 'document',
        limit: 10,
        cursor: 'opaque-cursor',
      );

      expect(mockApiClient.lastQueryParameters, {
        'folder_path': 'root.docs',
        'limit': '10',
        'q': 'report',
        'category': 'document',
        'cursor': 'opaque-cursor',
      });
    });

    test('omits an empty query string rather than sending q=""', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {'results': [], 'next_cursor': null};

      final repository = SearchRepository(mockApiClient);
      await repository.searchFiles(folderPath: 'root.docs', query: '');

      expect(mockApiClient.lastQueryParameters!.containsKey('q'), false);
    });

    test('parses a successful response into a SearchPage', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextResponse = {
        'results': [
          {
            'id': 'file-1',
            'name': 'a.pdf',
            'folder_path': 'root',
            'mime_type': 'application/pdf',
            'category': 'document',
            'size_bytes': 1,
            'created_at': '2026-08-17T00:00:00Z',
          },
        ],
        'next_cursor': 'next',
      };

      final repository = SearchRepository(mockApiClient);
      final page = await repository.searchFiles(folderPath: 'root');

      expect(page.results.length, 1);
      expect(page.nextCursor, 'next');
    });

    test(
      'throws ServerError on 503 -- unavailable, not an empty result',
      () async {
        final mockApiClient = _MockApiClient();
        mockApiClient.nextException = const ApiException(
          message: 'Service unavailable',
          statusCode: 503,
        );

        final repository = SearchRepository(mockApiClient);
        expect(
          () => repository.searchFiles(folderPath: 'root'),
          throwsA(isA<ServerError>()),
        );
      },
    );

    test('throws NetworkError on a connection failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );

      final repository = SearchRepository(mockApiClient);
      expect(
        () => repository.searchFiles(folderPath: 'root'),
        throwsA(isA<NetworkError>()),
      );
    });

    test('throws ApiError on a 422', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Invalid folder_path',
        statusCode: 422,
      );

      final repository = SearchRepository(mockApiClient);
      expect(
        () => repository.searchFiles(folderPath: 'root'),
        throwsA(isA<ApiError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  Map<String, dynamic>? nextResponse;
  ApiException? nextException;
  String? lastGetPath;
  Map<String, String>? lastQueryParameters;

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    bool authenticated = false,
    Map<String, String>? queryParameters,
  }) async {
    lastGetPath = path;
    lastQueryParameters = queryParameters;
    if (nextException != null) {
      throw nextException!;
    }
    return nextResponse ?? {};
  }

  @override
  Future<void> delete(String path, {bool authenticated = false}) async {
    throw UnimplementedError();
  }

  @override
  Future<void> postEmpty(String path, {bool authenticated = false}) async {
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> patchJson(
    String path, {
    bool authenticated = false,
    Map<String, dynamic>? body,
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
