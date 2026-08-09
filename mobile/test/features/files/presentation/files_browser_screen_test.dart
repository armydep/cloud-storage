import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:cloudestorage/features/files/presentation/widgets/file_list_item.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FileListItem', () {
    testWidgets('displays folder with correct icon', (
      WidgetTester tester,
    ) async {
      final folder = FileContent(
        id: '1',
        name: 'Documents',
        type: 'folder',
        path: 'root.Documents',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: FileListItem(item: folder)),
        ),
      );

      expect(find.text('Documents'), findsOneWidget);
      expect(find.byIcon(Icons.folder_outlined), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsOneWidget);
    });

    testWidgets('displays file with size', (WidgetTester tester) async {
      final file = FileContent(
        id: '2',
        name: 'file.txt',
        type: 'file',
        sizeBytes: 1024,
        category: 'document',
        mimeType: 'text/plain',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: FileListItem(item: file)),
        ),
      );

      expect(find.text('file.txt'), findsOneWidget);
      expect(find.text('1.0 KB'), findsOneWidget);
      expect(find.byIcon(Icons.description), findsOneWidget);
    });

    testWidgets('displays correct icon for different file categories', (
      WidgetTester tester,
    ) async {
      final categories = {
        'image': Icons.image,
        'video': Icons.videocam,
        'audio': Icons.audio_file,
        'document': Icons.description,
        'archive': Icons.folder_zip,
      };

      for (final entry in categories.entries) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: FileListItem(
                item: FileContent(
                  id: '1',
                  name: 'file',
                  type: 'file',
                  category: entry.key,
                ),
              ),
            ),
          ),
        );

        expect(find.byIcon(entry.value), findsOneWidget);
      }
    });

    testWidgets('calls onTap when folder is tapped', (
      WidgetTester tester,
    ) async {
      var tapped = false;
      final folder = FileContent(
        id: '1',
        name: 'Documents',
        type: 'folder',
        path: 'root.Documents',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(item: folder, onTap: () => tapped = true),
          ),
        ),
      );

      await tester.tap(find.byType(ListTile));
      expect(tapped, true);
    });
  });
}
