import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:cloudestorage/features/files/presentation/file_detail_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FileDetailScreen', () {
    late FileContent testFile;

    setUp(() {
      testFile = FileContent(
        id: 'file-123',
        name: 'document.pdf',
        type: 'file',
        sizeBytes: 1024000,
        category: 'document',
        mimeType: 'application/pdf',
        path: '/documents/document.pdf',
        createdAt: DateTime(2026, 8, 8, 14, 30, 0),
        ownerEmail: 'user@example.com',
      );
    });

    testWidgets('displays file name as title', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.text('File Details'), findsOneWidget);
      expect(find.text('document.pdf'), findsOneWidget);
    });

    testWidgets('displays file size in human-readable format', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.text('Size'), findsOneWidget);
      expect(find.byType(SelectableText), findsWidgets);
    });

    testWidgets('displays creation date with time', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.text('Aug 8, 2026 at 2:30 PM'), findsOneWidget);
    });

    testWidgets('displays MIME type', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.text('application/pdf'), findsOneWidget);
    });

    testWidgets('displays owner email', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.text('user@example.com'), findsOneWidget);
    });

    testWidgets('shows Unknown when created_at is null', (tester) async {
      final fileWithoutCreatedAt = FileContent(
        id: 'file-456',
        name: 'image.jpg',
        type: 'file',
        sizeBytes: 2048000,
        category: 'image',
        mimeType: 'image/jpeg',
        createdAt: null,
        ownerEmail: 'user@example.com',
      );

      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: fileWithoutCreatedAt)),
      );

      expect(find.text('Created'), findsOneWidget);
      expect(find.text('Unknown'), findsWidgets);
    });

    testWidgets('shows Unknown when owner_email is null', (tester) async {
      final fileWithoutOwner = FileContent(
        id: 'file-789',
        name: 'video.mp4',
        type: 'file',
        sizeBytes: 50000000,
        category: 'video',
        mimeType: 'video/mp4',
        createdAt: DateTime(2026, 8, 8, 14, 30, 0),
        ownerEmail: null,
      );

      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: fileWithoutOwner)),
      );

      final unknownTexts = find.text('Unknown');
      expect(unknownTexts, findsWidgets);
    });

    testWidgets('shows Unknown when mime_type is null', (tester) async {
      final fileWithoutMimeType = FileContent(
        id: 'file-999',
        name: 'unknown.file',
        type: 'file',
        sizeBytes: 512000,
        mimeType: null,
        createdAt: DateTime(2026, 8, 8, 14, 30, 0),
        ownerEmail: 'user@example.com',
      );

      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: fileWithoutMimeType)),
      );

      final unknownTexts = find.text('Unknown');
      expect(unknownTexts, findsWidgets);
    });

    testWidgets('shows Unknown for size when size_bytes is null', (
      tester,
    ) async {
      final fileWithoutSize = FileContent(
        id: 'file-000',
        name: 'empty.txt',
        type: 'file',
        sizeBytes: null,
        mimeType: 'text/plain',
        createdAt: DateTime(2026, 8, 8, 14, 30, 0),
        ownerEmail: 'user@example.com',
      );

      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: fileWithoutSize)),
      );

      final unknownTexts = find.text('Unknown');
      expect(unknownTexts, findsWidgets);
    });

    testWidgets('close button dismisses screen', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.byIcon(Icons.close), findsOneWidget);
      await tester.tap(find.byIcon(Icons.close));
      await tester.pumpAndSettle();

      expect(find.byType(FileDetailScreen), findsNothing);
    });

    testWidgets('scrolls when content exceeds screen', (tester) async {
      tester.view.physicalSize = const Size(800, 400);
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.byType(SingleChildScrollView), findsOneWidget);
    });

    testWidgets('detail sections are selectable', (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: FileDetailScreen(file: testFile)),
      );

      expect(find.byType(SelectableText), findsWidgets);
    });
  });
}
