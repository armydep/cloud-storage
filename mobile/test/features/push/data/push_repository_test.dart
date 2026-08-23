import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart'
    show ApiError, NetworkError, ServerError;
import 'package:cloudestorage/features/push/data/push_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('PushRepository.registerToken', () {
    test(
      'posts to the device-tokens endpoint with token and platform',
      () async {
        final mockApiClient = _MockApiClient();

        final repository = PushRepository(mockApiClient);
        await repository.registerToken(token: 'fcm-token', platform: 'android');

        expect(mockApiClient.lastPostPath, '/api/v1/push/device-tokens');
        expect(mockApiClient.lastRequestBody, {
          'token': 'fcm-token',
          'platform': 'android',
        });
      },
    );

    test('throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Server error',
        statusCode: 500,
      );

      final repository = PushRepository(mockApiClient);
      expect(
        () => repository.registerToken(token: 'fcm-token', platform: 'android'),
        throwsA(isA<ServerError>()),
      );
    });

    test('throws NetworkError on a connection failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );

      final repository = PushRepository(mockApiClient);
      expect(
        () => repository.registerToken(token: 'fcm-token', platform: 'android'),
        throwsA(isA<NetworkError>()),
      );
    });
  });

  group('PushRepository.unregisterToken', () {
    test('deletes by the URL-encoded token', () async {
      final mockApiClient = _MockApiClient();

      final repository = PushRepository(mockApiClient);
      await repository.unregisterToken('fcm/token+with special=chars');

      expect(
        mockApiClient.lastDeletePath,
        '/api/v1/push/device-tokens/${Uri.encodeComponent('fcm/token+with special=chars')}',
      );
    });

    test('throws ApiError on an unexpected client error', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Something else',
        statusCode: 422,
      );

      final repository = PushRepository(mockApiClient);
      expect(
        () => repository.unregisterToken('fcm-token'),
        throwsA(isA<ApiError>()),
      );
    });
  });

  group('PushRepository.setPushEnabled', () {
    test('patches /users/me with push_enabled', () async {
      final mockApiClient = _MockApiClient();

      final repository = PushRepository(mockApiClient);
      await repository.setPushEnabled(true);

      expect(mockApiClient.lastPatchPath, '/api/v1/users/me');
      expect(mockApiClient.lastRequestBody, {'push_enabled': true});
    });

    test('throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Server error',
        statusCode: 500,
      );

      final repository = PushRepository(mockApiClient);
      expect(
        () => repository.setPushEnabled(false),
        throwsA(isA<ServerError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  Map<String, dynamic>? nextResponse;
  ApiException? nextException;
  String? lastPostPath;
  String? lastDeletePath;
  String? lastPatchPath;
  Map<String, dynamic>? lastRequestBody;

  @override
  Future<void> delete(String path, {bool authenticated = false}) async {
    lastDeletePath = path;
    if (nextException != null) {
      throw nextException!;
    }
  }

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    bool authenticated = false,
    Map<String, String>? queryParameters,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<void> postEmpty(String path, {bool authenticated = false}) async {
    throw UnimplementedError();
  }

  @override
  Future<Map<String, dynamic>> patchJson(
    String path, {
    bool authenticated = false,
    Map<String, dynamic>? body,
  }) async {
    lastPatchPath = path;
    lastRequestBody = body;
    if (nextException != null) {
      throw nextException!;
    }
    return nextResponse ?? {};
  }

  @override
  Future<Map<String, dynamic>> postJson(
    String path, {
    bool authenticated = false,
    String? authenticationToken,
    Map<String, dynamic>? body,
  }) async {
    lastPostPath = path;
    lastRequestBody = body;
    if (nextException != null) {
      throw nextException!;
    }
    return nextResponse ?? {};
  }

  @override
  Future<Map<String, dynamic>> postForm(
    String path, {
    required Map<String, String> fields,
  }) async {
    throw UnimplementedError();
  }

  @override
  Uri resolve(String path, {Map<String, String>? queryParameters}) {
    throw UnimplementedError();
  }

  @override
  void close() {}
}
