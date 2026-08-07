import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:cloudestorage/features/files/presentation/widgets/file_list_item.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('File download UI', () {
    final testFile = FileContent(
      id: 'file-123',
      name: 'document.pdf',
      type: 'file',
      sizeBytes: 1024000,
      category: 'document',
      mimeType: 'application/pdf',
      path: '/documents/document.pdf',
    );

    testWidgets('download button appears on file item', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              onDownload: () {},
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.download), findsOneWidget);
      expect(find.text('document.pdf'), findsOneWidget);
    });

    testWidgets('progress bar displays during download', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              downloadProgress: 0.5,
              onCancel: () {},
            ),
          ),
        ),
      );

      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(find.text('50%'), findsOneWidget);
    });

    testWidgets('cancel button visible during download', (tester) async {
      var cancelCalled = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              downloadProgress: 0.3,
              onCancel: () => cancelCalled = true,
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.close), findsOneWidget);
      await tester.tap(find.byIcon(Icons.close));
      expect(cancelCalled, true);
    });

    testWidgets('error message displays on download failure', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              downloadError: 'Connection lost. Please check your network and try again.',
              onDownload: () {},
            ),
          ),
        ),
      );

      expect(find.text('Connection lost. Please check your network and try again.'), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('retry button visible on error', (tester) async {
      var retryCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              downloadError: 'Download failed',
              onDownload: () => retryCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.refresh));
      expect(retryCalled, true);
    });

    testWidgets('download action initiates on button tap', (tester) async {
      var downloadCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FileListItem(
              item: testFile,
              onDownload: () => downloadCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.download));
      expect(downloadCalled, true);
    });
  });
}
