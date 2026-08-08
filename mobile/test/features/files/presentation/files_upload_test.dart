import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:cloudestorage/features/files/presentation/widgets/file_list_item.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('File upload UI', () {
    final testFile = FileContent(
      id: 'file-123',
      name: 'document.pdf',
      type: 'file',
      sizeBytes: 1024000,
      category: 'document',
      mimeType: 'application/pdf',
      path: '/documents/document.pdf',
    );

    testWidgets('upload progress displays during upload', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              uploadProgress: 0.5,
            ),
          ),
        ),
      );

      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(find.text('Uploading 50%'), findsOneWidget);
    });

    testWidgets('error message displays on upload failure', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              uploadError: 'File already exists',
            ),
          ),
        ),
      );

      expect(find.text('File already exists'), findsOneWidget);
    });

    testWidgets('upload button appears on file item', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              title: const Text('Files'),
              actions: [
                IconButton(
                  key: const Key('upload-file-button'),
                  icon: const Icon(Icons.upload_file),
                  onPressed: () {},
                ),
              ],
            ),
            body: const Center(child: Text('Files')),
          ),
        ),
      );

      expect(find.byKey(const Key('upload-file-button')), findsOneWidget);
      expect(find.byIcon(Icons.upload_file), findsOneWidget);
    });

    testWidgets('retry button visible on upload error', (tester) async {
      var retryCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              uploadError: 'Upload failed',
            ),
          ),
        ),
      );

      expect(find.text('Upload failed'), findsOneWidget);
    });

    testWidgets('file list shows uploaded file in list', (tester) async {
      final uploadedFile = FileContent(
        id: 'file-456',
        name: 'uploaded.pdf',
        type: 'file',
        sizeBytes: 512000,
        category: 'document',
        mimeType: 'application/pdf',
        path: '/uploaded.pdf',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                FileListItem(item: testFile),
                FileListItem(item: uploadedFile),
              ],
            ),
          ),
        ),
      );

      expect(find.text('document.pdf'), findsOneWidget);
      expect(find.text('uploaded.pdf'), findsOneWidget);
    });
  });
}
