import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesRepository', () {
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
  });
}
