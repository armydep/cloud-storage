import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FileContent and FolderWithContents models', () {
    group('FileContent', () {
      test('correctly parses JSON for file', () {
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

      test('correctly parses JSON for folder', () {
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

      test('formats bytes correctly', () {
        expect(FileContent(id: '1', name: 'a', type: 'file', sizeBytes: 512).displaySize, '512 B');
        expect(FileContent(id: '2', name: 'b', type: 'file', sizeBytes: 1024).displaySize, '1.0 KB');
        expect(FileContent(id: '3', name: 'c', type: 'file', sizeBytes: 1024 * 1024).displaySize, '1.0 MB');
        expect(FileContent(id: '4', name: 'd', type: 'file', sizeBytes: 1024 * 1024 * 1024).displaySize, '1.0 GB');
      });

      test('equality compares id, name, and type', () {
        final file1 = FileContent(id: '1', name: 'file.txt', type: 'file');
        final file2 = FileContent(id: '1', name: 'file.txt', type: 'file');
        final file3 = FileContent(id: '2', name: 'file.txt', type: 'file');

        expect(file1, equals(file2));
        expect(file1, isNot(equals(file3)));
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
        expect(folder.path, 'root');
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
        expect(folder.folders.length, 0);
        expect(folder.files.length, 0);
      });

      test('separates folders and files correctly', () {
        final json = {
          'id': '123',
          'name': 'root',
          'path': 'root',
          'created_at': '2026-08-07T00:00:00Z',
          'contents': [
            {
              'id': '1',
              'name': 'Folder1',
              'type': 'folder',
              'path': 'root.Folder1',
            },
            {
              'id': '2',
              'name': 'file1.txt',
              'type': 'file',
              'size_bytes': 100,
            },
            {
              'id': '3',
              'name': 'Folder2',
              'type': 'folder',
              'path': 'root.Folder2',
            },
            {
              'id': '4',
              'name': 'file2.txt',
              'type': 'file',
              'size_bytes': 200,
            },
          ],
        };

        final folder = FolderWithContents.fromJson(json);

        expect(folder.folders.length, 2);
        expect(folder.files.length, 2);
        expect(folder.folders[0].name, 'Folder1');
        expect(folder.folders[1].name, 'Folder2');
        expect(folder.files[0].name, 'file1.txt');
        expect(folder.files[1].name, 'file2.txt');
      });
    });
  });
}
