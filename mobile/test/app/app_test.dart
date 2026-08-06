import 'package:cloudestorage/app/app.dart';
import 'package:cloudestorage/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows the mobile scaffold', (tester) async {
    final config = AppConfig.fromApiBaseUrl('https://api.example.com');

    await tester.pumpWidget(CloudStorageApp(config: config));

    expect(find.text('Cloude Storage'), findsOneWidget);
    expect(find.text('Mobile foundation is ready'), findsOneWidget);
    expect(find.text('API endpoint: api.example.com'), findsOneWidget);
  });
}
