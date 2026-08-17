import 'dart:convert';

import 'package:cloudestorage/core/network/api_client.dart';
import 'package:cloudestorage/features/auth/application/auth_controller.dart';
import 'package:cloudestorage/features/auth/application/auth_providers.dart';
import 'package:cloudestorage/features/auth/application/auth_state.dart';
import 'package:cloudestorage/features/auth/data/auth_repository.dart';
import 'package:cloudestorage/features/auth/data/auth_session.dart';
import 'package:cloudestorage/features/auth/domain/current_user.dart';
import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/application/shared_files_providers.dart';
import 'package:cloudestorage/features/files/data/files_repository.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../../support/fake_token_storage.dart';

/// Lets a test drive auth state directly, without a login round trip.
class _ControllableAuthController extends AuthController {
  _ControllableAuthController(super.repository, super.session)
    : super(restoreOnCreate: false);

  void signInAs(String id) {
    state = AuthState.authenticated(
      CurrentUser(
        id: id,
        email: '$id@example.com',
        isActive: true,
        isSuperuser: false,
      ),
    );
  }

  void signOut() => state = const AuthState.unauthenticated();
}

void main() {
  // These cover account isolation at the provider graph directly, rather than
  // relying on the router happening to unmount the widget tree on logout.
  // Without the currentUserIdProvider watch in the providers under test, both
  // fail: the second account observes the first account's data until its own
  // request completes.
  group('per-account provider state', () {
    late ProviderContainer container;
    late _ControllableAuthController auth;

    ProviderContainer buildContainer(MockClient client) {
      final session = AuthSession(FakeTokenStorage(token: 'token'));
      addTearDown(session.dispose);
      final apiClient = ApiClient(
        Uri.parse('https://api.example.com/'),
        httpClient: client,
        authSession: session,
      );
      auth = _ControllableAuthController(
        AuthRepository(apiClient, session),
        session,
      );
      final built = ProviderContainer(
        overrides: [
          authControllerProvider.overrideWith((ref) => auth),
          filesRepositoryProvider.overrideWithValue(FilesRepository(apiClient)),
        ],
      );
      addTearDown(built.dispose);
      return built;
    }

    test('shared files do not carry over to the next account', () async {
      final client = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'data': [
              {
                'id': 'file-1',
                'name': 'first-account-secret.pdf',
                'mime_type': 'application/pdf',
                'category': 'document',
                'size_bytes': 2048,
                'owner_email': 'sharer@example.com',
                'shared_at': '2026-08-06T12:00:00Z',
              },
            ],
            'count': 1,
          }),
          200,
        );
      });
      container = buildContainer(client);
      // autoDispose would tear the notifier down between reads otherwise.
      final subscription = container.listen(
        sharedFilesControllerProvider,
        (_, _) {},
      );
      addTearDown(subscription.close);

      auth.signInAs('user-a');
      await container.read(sharedFilesControllerProvider.notifier).load();
      expect(
        container.read(sharedFilesControllerProvider).files.single.name,
        'first-account-secret.pdf',
      );

      auth.signOut();
      auth.signInAs('user-b');

      expect(
        container.read(sharedFilesControllerProvider).files,
        isEmpty,
        reason:
            'the second account must not observe shared files belonging to '
            'the first account, even before its own load completes',
      );
    });

    test('folder contents do not carry over to the next account', () async {
      final client = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'id': 'folder-1',
            'name': 'root',
            'path': 'root',
            'created_at': '2026-08-07T00:00:00Z',
            'contents': [
              {
                'id': 'file-1',
                'name': 'first-account-file.pdf',
                'type': 'file',
                'size_bytes': 1024,
                'mime_type': 'application/pdf',
              },
            ],
          }),
          200,
        );
      });
      container = buildContainer(client);
      final subscription = container.listen(filesControllerProvider, (_, _) {});
      addTearDown(subscription.close);

      auth.signInAs('user-a');
      await container.read(filesControllerProvider.notifier).loadFolder('root');
      expect(container.read(filesControllerProvider).folder, isNotNull);

      auth.signOut();
      auth.signInAs('user-b');

      expect(
        container.read(filesControllerProvider).folder,
        isNull,
        reason:
            'the second account must not render folder and file names '
            'belonging to the first account while its request is in flight',
      );
    });
  });
}
