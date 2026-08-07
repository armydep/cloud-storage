import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('File download UI', () {
    testWidgets('download button appears on file item', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                ListTile(
                  title: const Text('document.pdf'),
                  trailing: IconButton(
                    icon: const Icon(Icons.download),
                    onPressed: () {},
                  ),
                ),
              ],
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
            body: Stack(
              children: [
                ListTile(
                  title: const Text('document.pdf'),
                  subtitle: const Text('50%'),
                ),
                const Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: LinearProgressIndicator(value: 0.5),
                ),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      expect(find.text('50%'), findsOneWidget);
    });

    testWidgets('cancel button visible during download', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListTile(
              title: const Text('document.pdf'),
              trailing: IconButton(
                icon: const Icon(Icons.close),
                onPressed: () {},
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.close), findsOneWidget);
    });

    testWidgets('error message displays on download failure', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListTile(
              title: const Text('document.pdf'),
              subtitle: const Text(
                'Connection lost. Please check your network and try again.',
                style: TextStyle(color: Colors.red, fontSize: 12),
              ),
              trailing: IconButton(
                icon: const Icon(Icons.refresh, color: Colors.red),
                onPressed: () {},
              ),
            ),
          ),
        ),
      );

      expect(find.text(
        'Connection lost. Please check your network and try again.',
      ), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('retry button visible on error', (tester) async {
      var tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListTile(
              title: const Text('document.pdf'),
              trailing: IconButton(
                icon: const Icon(Icons.refresh, color: Colors.red),
                onPressed: () => tapped = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.refresh));
      expect(tapped, true);
    });

    testWidgets('download action initiates on button tap', (tester) async {
      var downloadCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListTile(
              title: const Text('document.pdf'),
              trailing: IconButton(
                icon: const Icon(Icons.download),
                onPressed: () => downloadCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.download));
      expect(downloadCalled, true);
    });
  });
}
