import 'package:cloudestorage/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppConfig', () {
    test('accepts and normalizes an HTTP API base URL', () {
      final config = AppConfig.fromApiBaseUrl('http://localhost:8000/api');

      expect(config.apiBaseUri, Uri.parse('http://localhost:8000/api/'));
    });

    test('rejects a relative API base URL', () {
      expect(
        () => AppConfig.fromApiBaseUrl('/api/v1'),
        throwsA(isA<FormatException>()),
      );
    });

    test('rejects query parameters in the API base URL', () {
      expect(
        () => AppConfig.fromApiBaseUrl('https://example.com?token=secret'),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
