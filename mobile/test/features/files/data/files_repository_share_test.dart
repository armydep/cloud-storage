import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FilesRepository.createFileShare', () {
    test('posts the expected request shape with auth header', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      await repository.createFileShare(
        fileId: 'file-123',
        recipientEmail: 'friend@example.com',
      );

      expect(mockApiClient.lastPostPath, '/api/v1/files/file-123/shares');
      expect(mockApiClient.lastPostAuthenticated, isTrue);
      expect(mockApiClient.lastPostBody, {
        'recipient_email': 'friend@example.com',
      });
    });

    test('returns a FileShare parsed from the response', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      final share = await repository.createFileShare(
        fileId: 'file-123',
        recipientEmail: 'friend@example.com',
      );

      expect(share.id, 'share-1');
      expect(share.fileId, 'file-123');
      expect(share.recipientEmail, 'friend@example.com');
      expect(share.createdAt, DateTime.parse('2026-01-01T00:00:00Z'));
    });

    test(
      'throws ShareRecipientNotFoundError on 404 "Recipient not found"',
      () async {
        final mockApiClient = _MockApiClient();
        mockApiClient.nextException = const ApiException(
          message: 'Not found',
          statusCode: 404,
          detail: 'Recipient not found',
        );
        final repository = FilesRepository(mockApiClient);

        expect(
          () => repository.createFileShare(
            fileId: 'file-123',
            recipientEmail: 'nobody@example.com',
          ),
          throwsA(isA<ShareRecipientNotFoundError>()),
        );
      },
    );

    test('throws FileNotFoundError on 404 without recipient detail', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Not found',
        statusCode: 404,
        detail: 'File not found',
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.createFileShare(
          fileId: 'missing-file',
          recipientEmail: 'friend@example.com',
        ),
        throwsA(isA<FileNotFoundError>()),
      );
    });

    test(
      'throws ShareRecipientInactiveError on 422 "Recipient is inactive"',
      () async {
        final mockApiClient = _MockApiClient();
        mockApiClient.nextException = const ApiException(
          message: 'Unprocessable',
          statusCode: 422,
          detail: 'Recipient is inactive',
        );
        final repository = FilesRepository(mockApiClient);

        expect(
          () => repository.createFileShare(
            fileId: 'file-123',
            recipientEmail: 'inactive@example.com',
          ),
          throwsA(isA<ShareRecipientInactiveError>()),
        );
      },
    );

    test('throws CannotShareWithOwnerError on 422 self-share detail', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Unprocessable',
        statusCode: 422,
        detail: 'A file cannot be shared with its owner',
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.createFileShare(
          fileId: 'file-123',
          recipientEmail: 'me@example.com',
        ),
        throwsA(isA<CannotShareWithOwnerError>()),
      );
    });

    test('throws DuplicateFileShareError on 409', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Conflict',
        statusCode: 409,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.createFileShare(
          fileId: 'file-123',
          recipientEmail: 'friend@example.com',
        ),
        throwsA(isA<DuplicateFileShareError>()),
      );
    });

    test('throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Server error',
        statusCode: 500,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.createFileShare(
          fileId: 'file-123',
          recipientEmail: 'friend@example.com',
        ),
        throwsA(isA<ServerError>()),
      );
    });

    test('throws NetworkError on network failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.createFileShare(
          fileId: 'file-123',
          recipientEmail: 'friend@example.com',
        ),
        throwsA(isA<NetworkError>()),
      );
    });
  });

  group('FilesRepository.getFileShares', () {
    test('gets the expected authenticated endpoint', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      await repository.getFileShares(fileId: 'file-123');

      expect(mockApiClient.lastGetPath, '/api/v1/files/file-123/shares');
      expect(mockApiClient.lastGetAuthenticated, isTrue);
    });

    test('returns a list of FileShare parsed from the response', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextGetJson = {
        'data': [
          {
            'id': 'share-1',
            'file_id': 'file-123',
            'recipient_email': 'friend@example.com',
            'created_at': '2026-01-01T00:00:00Z',
          },
          {
            'id': 'share-2',
            'file_id': 'file-123',
            'recipient_email': 'other@example.com',
            'created_at': '2026-01-02T00:00:00Z',
          },
        ],
        'count': 2,
      };
      final repository = FilesRepository(mockApiClient);

      final shares = await repository.getFileShares(fileId: 'file-123');

      expect(shares, hasLength(2));
      expect(shares.first.recipientEmail, 'friend@example.com');
      expect(shares.last.recipientEmail, 'other@example.com');
    });

    test('returns an empty list when there is no data key', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextGetJson = {};
      final repository = FilesRepository(mockApiClient);

      final shares = await repository.getFileShares(fileId: 'file-123');

      expect(shares, isEmpty);
    });

    test('throws FileNotFoundError on 404', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Not found',
        statusCode: 404,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.getFileShares(fileId: 'missing-file'),
        throwsA(isA<FileNotFoundError>()),
      );
    });

    test('throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Server error',
        statusCode: 500,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.getFileShares(fileId: 'file-123'),
        throwsA(isA<ServerError>()),
      );
    });

    test('throws NetworkError on network failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.getFileShares(fileId: 'file-123'),
        throwsA(isA<NetworkError>()),
      );
    });
  });

  group('FilesRepository.revokeFileShare', () {
    test('calls expected authenticated delete endpoint', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      await repository.revokeFileShare(fileId: 'file-123', shareId: 'share-1');

      expect(
        mockApiClient.lastDeletePath,
        '/api/v1/files/file-123/shares/share-1',
      );
      expect(mockApiClient.lastDeleteAuthenticated, isTrue);
    });

    test('completes successfully on 204', () async {
      final mockApiClient = _MockApiClient();
      final repository = FilesRepository(mockApiClient);

      await expectLater(
        repository.revokeFileShare(fileId: 'file-123', shareId: 'share-1'),
        completes,
      );
    });

    test(
      'throws FileShareNotFoundError on 404 "File share not found"',
      () async {
        final mockApiClient = _MockApiClient();
        mockApiClient.nextException = const ApiException(
          message: 'Not found',
          statusCode: 404,
          detail: 'File share not found',
        );
        final repository = FilesRepository(mockApiClient);

        expect(
          () => repository.revokeFileShare(
            fileId: 'file-123',
            shareId: 'missing-share',
          ),
          throwsA(isA<FileShareNotFoundError>()),
        );
      },
    );

    test('throws FileNotFoundError on 404 without share detail', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Not found',
        statusCode: 404,
        detail: 'File not found',
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () => repository.revokeFileShare(
          fileId: 'missing-file',
          shareId: 'share-1',
        ),
        throwsA(isA<FileNotFoundError>()),
      );
    });

    test('throws ServerError on 500', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Server error',
        statusCode: 500,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () =>
            repository.revokeFileShare(fileId: 'file-123', shareId: 'share-1'),
        throwsA(isA<ServerError>()),
      );
    });

    test('throws NetworkError on network failure', () async {
      final mockApiClient = _MockApiClient();
      mockApiClient.nextException = const ApiException(
        message: 'Network error',
        isNetworkError: true,
      );
      final repository = FilesRepository(mockApiClient);

      expect(
        () =>
            repository.revokeFileShare(fileId: 'file-123', shareId: 'share-1'),
        throwsA(isA<NetworkError>()),
      );
    });
  });
}

class _MockApiClient implements ApiClient {
  ApiException? nextException;
  String? lastPostPath;
  bool? lastPostAuthenticated;
  Map<String, dynamic>? lastPostBody;
  String? lastGetPath;
  bool? lastGetAuthenticated;
  Map<String, dynamic> nextGetJson = const {'data': <dynamic>[], 'count': 0};
  String? lastDeletePath;
  bool? lastDeleteAuthenticated;

  @override
  Future<Map<String, dynamic>> postJson(
    String path, {
    bool authenticated = false,
    String? authenticationToken,
    Map<String, dynamic>? body,
  }) async {
    lastPostPath = path;
    lastPostAuthenticated = authenticated;
    lastPostBody = body;
    if (nextException != null) {
      throw nextException!;
    }
    return {
      'id': 'share-1',
      'file_id': 'file-123',
      'recipient_email': body?['recipient_email'],
      'created_at': '2026-01-01T00:00:00Z',
    };
  }

  @override
  Future<void> delete(String path, {bool authenticated = false}) async {
    lastDeletePath = path;
    lastDeleteAuthenticated = authenticated;
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
    lastGetPath = path;
    lastGetAuthenticated = authenticated;
    if (nextException != null) {
      throw nextException!;
    }
    return nextGetJson;
  }

  @override
  Future<Map<String, dynamic>> postForm(
    String path, {
    required Map<String, String> fields,
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
    throw UnimplementedError();
  }

  @override
  Uri resolve(String path, {Map<String, String>? queryParameters}) {
    throw UnimplementedError();
  }

  @override
  void close() {}
}
