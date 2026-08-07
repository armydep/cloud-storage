import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';

import 'files_repository_test.mocks.dart';

@GenerateMocks([ApiClient])
void main() {
  group('FilesRepository', () {
    late MockApiClient mockApiClient;
    late FilesRepository repository;

    setUp(() {
      mockApiClient = MockApiClient();
      repository = FilesRepository(mockApiClient);
    });

    group('FileContent', () {
      test('correctly parses JSON', () {
        final json = {
          'id': '123',
          'name': 'file.txt',
          'type': 'file',
          'size_bytes': 1024,
          'category': 'document',
          'mime_type': 'text/plain',
        };

        final content = FileContent.fromJson(json);

        expect(content.id, '123');
        expect(content.name, 'file.txt');
        expect(content.isFile, true);
        expect(content.isFolder, false);
        expect(content.sizeBytes, 1024);
        expect(content.displaySize, '1.0 KB');
      });

      test('formats bytes correctly', () {
        expect(FileContent(id: '1', name: 'a', type: 'file', sizeBytes: 512).displaySize, '512 B');
        expect(FileContent(id: '2', name: 'b', type: 'file', sizeBytes: 1024).displaySize, '1.0 KB');
        expect(FileContent(id: '3', name: 'c', type: 'file', sizeBytes: 1024 * 1024).displaySize, '1.0 MB');
        expect(FileContent(id: '4', name: 'd', type: 'file', sizeBytes: 1024 * 1024 * 1024).displaySize, '1.0 GB');
      });

      test('handles folder content', () {
        final json = {
          'id': '456',
          'name': 'Documents',
          'type': 'folder',
          'path': 'root.Documents',
        };

        final content = FileContent.fromJson(json);

        expect(content.isFolder, true);
        expect(content.isFile, false);
        expect(content.path, 'root.Documents');
      });
    });

    group('FolderWithContents', () {
      test('correctly parses JSON', () {
        final json = {
          'id': '123',
          'name': 'root',
          'path': 'root',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [
            {
              'id': '1',
              'name': 'Documents',
              'type': 'folder',
              'path': 'root.Documents',
            },
            {
              'id': '2',
              'name': 'file.txt',
              'type': 'file',
              'size_bytes': 1024,
              'category': 'document',
              'mime_type': 'text/plain',
            },
          ],
        };

        final folder = FolderWithContents.fromJson(json);

        expect(folder.id, '123');
        expect(folder.name, 'root');
        expect(folder.contents.length, 2);
        expect(folder.folders.length, 1);
        expect(folder.files.length, 1);
        expect(folder.isEmpty, false);
      });

      test('handles empty folder', () {
        final json = {
          'id': '123',
          'name': 'empty',
          'path': 'root.empty',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [],
        };

        final folder = FolderWithContents.fromJson(json);

        expect(folder.isEmpty, true);
        expect(folder.contents.length, 0);
      });
    });

    group('getFolder', () {
      test('calls API with correct endpoint and authentication', () async {
        const path = 'root';
        final mockResponse = {
          'id': '123',
          'name': 'root',
          'path': 'root',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [],
        };

        when(mockApiClient.getJson(
          '/api/v1/files',
          authenticated: true,
          queryParameters: {'path': path},
        )).thenAnswer((_) async => mockResponse);

        await repository.getFolder(path: path);

        verify(mockApiClient.getJson(
          '/api/v1/files',
          authenticated: true,
          queryParameters: {'path': path},
        )).called(1);
      });

      test('returns FolderWithContents on success', () async {
        const path = 'root';
        final mockResponse = {
          'id': '123',
          'name': 'root',
          'path': 'root',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [
            {
              'id': '1',
              'name': 'Documents',
              'type': 'folder',
              'path': 'root.Documents',
            },
          ],
        };

        when(mockApiClient.getJson(
          any,
          authenticated: anyNamed('authenticated'),
          queryParameters: anyNamed('queryParameters'),
        )).thenAnswer((_) async => mockResponse);

        final result = await repository.getFolder(path: path);

        expect(result, isA<FolderWithContents>());
        expect(result.name, 'root');
      });

      test('throws FolderNotFoundError on 404', () async {
        when(mockApiClient.getJson(
          any,
          authenticated: anyNamed('authenticated'),
          queryParameters: anyNamed('queryParameters'),
        )).thenThrow(
          const ApiException(message: 'Not found', statusCode: 404),
        );

        expect(
          () => repository.getFolder(path: 'root'),
          throwsA(isA<FolderNotFoundError>()),
        );
      });

      test('throws ServerError on 500', () async {
        when(mockApiClient.getJson(
          any,
          authenticated: anyNamed('authenticated'),
          queryParameters: anyNamed('queryParameters'),
        )).thenThrow(
          const ApiException(message: 'Server error', statusCode: 500),
        );

        expect(
          () => repository.getFolder(path: 'root'),
          throwsA(isA<ServerError>()),
        );
      });

      test('throws NetworkError on network exception', () async {
        when(mockApiClient.getJson(
          any,
          authenticated: anyNamed('authenticated'),
          queryParameters: anyNamed('queryParameters'),
        )).thenThrow(
          const ApiException(
            message: 'Network error',
            isNetworkError: true,
          ),
        );

        expect(
          () => repository.getFolder(path: 'root'),
          throwsA(isA<NetworkError>()),
        );
      });
    });
  });
}
