import 'package:cloudestorage/core/network/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('resolves API paths below the configured base URI', () async {
    late http.Request capturedRequest;
    final httpClient = MockClient((request) async {
      capturedRequest = request;
      return http.Response('{}', 200);
    });
    final apiClient = ApiClient(
      Uri.parse('https://example.com/api/'),
      httpClient: httpClient,
    );

    final response = await apiClient.get(
      '/v1/files',
      headers: const {'Accept': 'application/json'},
    );

    expect(response.statusCode, 200);
    expect(capturedRequest.url, Uri.parse('https://example.com/api/v1/files'));
    expect(capturedRequest.headers['Accept'], 'application/json');

    apiClient.close();
  });
}
