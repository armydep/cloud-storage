import 'package:cloudestorage/features/search/domain/search_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('SearchResultItem', () {
    test('parses JSON matching search-svc\'s SearchResultItem schema', () {
      final json = {
        'id': 'file-1',
        'name': 'report.pdf',
        'folder_path': 'root.reports',
        'mime_type': 'application/pdf',
        'category': 'document',
        'size_bytes': 1024,
        'created_at': '2026-08-17T12:00:00Z',
      };

      final item = SearchResultItem.fromJson(json);

      expect(item.id, 'file-1');
      expect(item.name, 'report.pdf');
      expect(item.folderPath, 'root.reports');
      expect(item.mimeType, 'application/pdf');
      expect(item.category, 'document');
      expect(item.sizeBytes, 1024);
      expect(item.createdAt, DateTime.parse('2026-08-17T12:00:00Z'));
    });

    test('toFileContent produces a file row usable by FileListItem', () {
      final item = SearchResultItem(
        id: 'file-1',
        name: 'report.pdf',
        folderPath: 'root.reports',
        mimeType: 'application/pdf',
        category: 'document',
        sizeBytes: 1024,
        createdAt: DateTime.parse('2026-08-17T12:00:00Z'),
      );

      final content = item.toFileContent();

      expect(content.id, 'file-1');
      expect(content.name, 'report.pdf');
      expect(content.isFile, true);
      expect(content.isFolder, false);
      expect(content.path, 'root.reports');
      expect(content.category, 'document');
      expect(content.mimeType, 'application/pdf');
      expect(content.sizeBytes, 1024);
    });
  });

  group('SearchPage', () {
    test('parses results and next_cursor', () {
      final json = {
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
        'next_cursor': 'opaque-cursor',
      };

      final page = SearchPage.fromJson(json);

      expect(page.results.length, 1);
      expect(page.nextCursor, 'opaque-cursor');
    });

    test('defaults to empty results and a null cursor', () {
      final page = SearchPage.fromJson({'results': [], 'next_cursor': null});

      expect(page.results, isEmpty);
      expect(page.nextCursor, isNull);
    });
  });
}
